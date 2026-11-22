import argparse
import concurrent.futures
import importlib.util
import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
import uuid

GATEWAY = os.getenv("GATEWAY_URL", "http://localhost:3000").rstrip("/")
SKIP_DOCKER_FAULTS = False


def http_json(path, method="GET", body=None, token=None, headers_extra=None, timeout=12):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if headers_extra:
        headers.update(headers_extra)
    req = urllib.request.Request(GATEWAY + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None), dict(resp.headers)
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return err.code, parsed, dict(err.headers)


def register_user(role, tag):
    email = f"e2e_{tag}_{uuid.uuid4().hex[:6]}@test.local"
    status, data, _ = http_json(
        "/api/auth/register",
        method="POST",
        body={"email": email, "password": "TestPassword#2026", "role": role, "fullName": f"E2E {role} {tag}"},
    )
    assert status == 201 and data and data.get("token"), f"Register failed: {status} {data}"
    return email, data["token"], data["user"]


def poll_trip(trip_id, token, expected_statuses, timeout=15.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        status, data, _ = http_json(f"/api/trips/{trip_id}", token=token)
        if status == 200 and isinstance(data, dict):
            last = data
            if data.get("status") in expected_statuses:
                return data
        time.sleep(0.4)
    return last


def poll_driver_status(token, expected, timeout=15.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        status, data, _ = http_json("/api/location/me", token=token)
        if status == 200 and isinstance(data, dict):
            last = data
            if data.get("status") == expected:
                return data
        time.sleep(0.4)
    return last


def isolated_coords(slot):
    # Each test uses a distinct geographic region (>100km apart) so active drivers never collide across tests.
    return round(11.0 + 0.8 * slot, 6), round(105.0 + 0.5 * slot, 6)


class TestRideHailingDS03(unittest.TestCase):
    # --- 8 FUNCTIONAL TESTS ---
    def test_F01_register_login_and_me(self):
        email, token, user = register_user("rider", "f01")
        self.assertEqual(user["role"], "Rider")
        status, login_data, headers = http_json(
            "/api/auth/login", method="POST", body={"email": email, "password": "TestPassword#2026"}
        )
        self.assertEqual(status, 200)
        self.assertTrue(login_data.get("token"))
        self.assertTrue(headers.get("X-Correlation-ID") or headers.get("x-correlation-id"))
        st_me, me_data, _ = http_json("/api/auth/me", token=token)
        self.assertEqual(st_me, 200)
        self.assertEqual(me_data["user"]["id"], user["id"])

    def test_F02_driver_location_update_and_read(self):
        _, drv_token, drv = register_user("driver", "f02")
        lat, lng = isolated_coords(1)
        st, body, _ = http_json(
            "/api/location", method="POST", token=drv_token,
            body={"driver_id": drv["id"], "latitude": lat, "longitude": lng},
        )
        self.assertEqual(st, 200)
        self.assertEqual(body.get("status"), "success")
        me_st, me_body, _ = http_json("/api/location/me", token=drv_token)
        self.assertEqual(me_st, 200)
        self.assertEqual(me_body["status"], "AVAILABLE")
        self.assertEqual(me_body["location"]["coordinates"], [lng, lat])
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F03_driver_online_offline_toggle(self):
        _, drv_token, drv = register_user("driver", "f03")
        lat, lng = isolated_coords(2)
        st, _, _ = http_json(
            "/api/location", method="POST", token=drv_token,
            body={"driver_id": drv["id"], "latitude": lat, "longitude": lng},
        )
        self.assertEqual(st, 200)
        st_off, off_body, _ = http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})
        self.assertEqual(st_off, 200)
        self.assertEqual(off_body["driver_status"], "OFFLINE")
        st_on, on_body, _ = http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "AVAILABLE"})
        self.assertEqual(st_on, 200)
        self.assertEqual(on_body["driver_status"], "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F04_create_trip_and_async_match_to_MATCHED(self):
        _, drv_token, drv = register_user("driver", "f04")
        _, rdr_token, _ = register_user("rider", "f04")
        lat, lng = isolated_coords(3)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        st, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
        )
        self.assertEqual(st, 200)
        matched = poll_trip(created["tripId"], rdr_token, {"MATCHED"})
        self.assertEqual(matched["status"], "MATCHED")
        self.assertEqual(str(matched["driverId"]), str(drv["id"]))
        # Clean up
        http_json(f"/api/trips/{created['tripId']}/cancel", method="PUT", token=rdr_token, body={"reason": "CLEANUP"})
        poll_driver_status(drv_token, "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F05_driver_reject_trip_and_saga_release(self):
        _, drv_token, drv = register_user("driver", "f05")
        _, rdr_token, _ = register_user("rider", "f05")
        lat, lng = isolated_coords(4)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        st, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
        )
        self.assertEqual(st, 200)
        matched = poll_trip(created["tripId"], drv_token, {"MATCHED"})
        self.assertEqual(matched["status"], "MATCHED")
        rej_st, rej_body, _ = http_json(
            f"/api/trips/{created['tripId']}/reject", method="PUT", token=drv_token, body={"reason": "DRIVER_REJECTED"}
        )
        self.assertEqual(rej_st, 200)
        self.assertEqual(rej_body["status"], "CANCELED")
        self.assertEqual(rej_body["cancelReason"], "DRIVER_REJECTED")
        released = poll_driver_status(drv_token, "AVAILABLE")
        self.assertEqual(released["status"], "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F06_full_trip_lifecycle_accept_start_complete_and_fare(self):
        _, drv_token, _ = register_user("driver", "f06")
        _, rdr_token, _ = register_user("rider", "f06")
        lat, lng = isolated_coords(5)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        st, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.015, "destLong": lng + 0.015, "vehicleType": "MOTORBIKE"},
        )
        self.assertEqual(st, 200)
        trip_id = created["tripId"]
        matched = poll_trip(trip_id, drv_token, {"MATCHED"})
        self.assertEqual(matched["status"], "MATCHED")

        acc_st, acc, _ = http_json(f"/api/trips/{trip_id}/accept", method="PUT", token=drv_token)
        self.assertEqual(acc_st, 200)
        self.assertEqual(acc["status"], "ACCEPTED")

        sta_st, sta, _ = http_json(f"/api/trips/{trip_id}/start", method="PUT", token=drv_token)
        self.assertEqual(sta_st, 200)
        self.assertEqual(sta["status"], "STARTED")

        com_st, com, _ = http_json(f"/api/trips/{trip_id}/complete", method="PUT", token=drv_token)
        self.assertEqual(com_st, 200)
        self.assertEqual(com["status"], "COMPLETED")
        self.assertEqual(com["paymentStatus"], "PAID_SIMULATED")
        self.assertGreater(float(com["fareAmount"]), 15000.0)

        released = poll_driver_status(drv_token, "AVAILABLE")
        self.assertEqual(released["status"], "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F07_passenger_cancel_active_trip_releases_driver(self):
        _, drv_token, _ = register_user("driver", "f07")
        _, rdr_token, _ = register_user("rider", "f07")
        lat, lng = isolated_coords(6)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        _, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
        )
        trip_id = created["tripId"]
        poll_trip(trip_id, rdr_token, {"MATCHED"})
        can_st, can_body, _ = http_json(
            f"/api/trips/{trip_id}/cancel", method="PUT", token=rdr_token, body={"reason": "PASSENGER_CANCELED"}
        )
        self.assertEqual(can_st, 200)
        self.assertEqual(can_body["status"], "CANCELED")
        released = poll_driver_status(drv_token, "AVAILABLE")
        self.assertEqual(released["status"], "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_F08_no_driver_available_triggers_saga_compensation(self):
        _, rdr_token, _ = register_user("rider", "f08")
        lat, lng = isolated_coords(7)
        st, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
        )
        self.assertEqual(st, 200)
        final_trip = poll_trip(created["tripId"], rdr_token, {"CANCELED"})
        self.assertEqual(final_trip["status"], "CANCELED")
        self.assertEqual(final_trip["cancelReason"], "TIMEOUT_NO_DRIVERS")

    # --- 2 CONCURRENCY & CONFLICT TESTS ---

    def test_C01_two_passengers_concurrently_request_single_driver_no_double_booking(self):
        _, drv_token, drv = register_user("driver", "c01")
        _, r1_token, _ = register_user("rider", "c01a")
        _, r2_token, _ = register_user("rider", "c01b")
        lat, lng = isolated_coords(8)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        payload = {"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"}

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(http_json, "/api/trips", "POST", payload, r1_token)
            f2 = pool.submit(http_json, "/api/trips", "POST", payload, r2_token)
            st1, t1, _ = f1.result()
            st2, t2, _ = f2.result()

        self.assertEqual(st1, 200)
        self.assertEqual(st2, 200)
        res1 = poll_trip(t1["tripId"], r1_token, {"MATCHED", "CANCELED"})
        res2 = poll_trip(t2["tripId"], r2_token, {"MATCHED", "CANCELED"})
        statuses = sorted([res1["status"], res2["status"]])
        # Exactly one passenger gets the driver; the other gets compensated to CANCELED (never double-assigned).
        self.assertEqual(statuses, ["CANCELED", "MATCHED"], f"Unexpected concurrency outcome: {res1} vs {res2}")
        winner = res1 if res1["status"] == "MATCHED" else res2
        winner_token = r1_token if winner is res1 else r2_token
        self.assertEqual(str(winner["driverId"]), str(drv["id"]))

        http_json(f"/api/trips/{winner['tripId']}/cancel", method="PUT", token=winner_token, body={"reason": "CLEANUP"})
        poll_driver_status(drv_token, "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_C02_concurrent_accept_and_cancel_maintains_consistency(self):
        _, drv_token, _ = register_user("driver", "c02")
        _, rdr_token, _ = register_user("rider", "c02")
        lat, lng = isolated_coords(9)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        _, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
        )
        trip_id = created["tripId"]
        poll_trip(trip_id, drv_token, {"MATCHED"})

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            f_acc = pool.submit(http_json, f"/api/trips/{trip_id}/accept", "PUT", None, drv_token)
            f_can = pool.submit(http_json, f"/api/trips/{trip_id}/cancel", "PUT", {"reason": "RACE_CANCEL"}, rdr_token)
            st_acc, _, _ = f_acc.result()
            st_can, _, _ = f_can.result()

        self.assertIn(st_acc, {200, 400, 409})
        self.assertIn(st_can, {200, 400, 409})
        st_final, final_trip, _ = http_json(f"/api/trips/{trip_id}", token=rdr_token)
        self.assertEqual(st_final, 200)
        self.assertIn(final_trip["status"], {"ACCEPTED", "CANCELED"})
        if final_trip["status"] == "ACCEPTED":
            http_json(f"/api/trips/{trip_id}/cancel", method="PUT", token=rdr_token, body={"reason": "CLEANUP"})
        poll_driver_status(drv_token, "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    # --- 2 FAULT TOLERANCE & RECOVERY TESTS ---

    def test_R01_matching_worker_crash_and_kafka_recovery(self):
        if SKIP_DOCKER_FAULTS:
            self.skipTest("Skipped Docker container fault injection (--skip-docker-faults)")
        _, drv_token, drv = register_user("driver", "r01")
        _, rdr_token, _ = register_user("rider", "r01")
        lat, lng = isolated_coords(10)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})

        subprocess.run(["docker", "compose", "stop", "matching_worker"], check=True, capture_output=True)
        try:
            st, created, _ = http_json(
                "/api/trips", method="POST", token=rdr_token,
                body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01, "vehicleType": "MOTORBIKE"},
            )
            self.assertEqual(st, 200)
            time.sleep(2.5)
            _, pending_trip, _ = http_json(f"/api/trips/{created['tripId']}", token=rdr_token)
            self.assertEqual(pending_trip["status"], "PENDING")
        finally:
            subprocess.run(["docker", "compose", "start", "matching_worker"], check=True, capture_output=True)

        recovered = poll_trip(created["tripId"], rdr_token, {"MATCHED"}, timeout=25.0)
        self.assertEqual(recovered["status"], "MATCHED")
        self.assertEqual(str(recovered["driverId"]), str(drv["id"]))

        http_json(f"/api/trips/{created['tripId']}/cancel", method="PUT", token=rdr_token, body={"reason": "CLEANUP"})
        poll_driver_status(drv_token, "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    def test_R02_poison_pill_dlq_and_deduplication_resilience(self):
        if SKIP_DOCKER_FAULTS:
            self.skipTest("Skipped Docker Kafka/Mongo fault injection (--skip-docker-faults)")
        # Inject poison pill + duplicate event and verify Analytics DLQ captures poison pill and deduplicates duplicate.
        subprocess.run([sys.executable, "scripts/mock_trip.py", "--mode", "poison-pill"], check=True, capture_output=True)
        subprocess.run([sys.executable, "scripts/mock_trip.py", "--mode", "duplicate-event"], check=True, capture_output=True)
        time.sleep(3.0)
        res = subprocess.run(
            ["docker", "compose", "exec", "-T", "mongodb", "mongosh", "--quiet", "--eval",
             "JSON.stringify({dlq: db.getSiblingDB('DataWarehouseDB').DeadLetterQueue.countDocuments({}), fact: db.getSiblingDB('DataWarehouseDB').Fact_Events.countDocuments({})})"],
            text=True, capture_output=True, check=True,
        )
        counts = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertGreaterEqual(counts["dlq"], 1, "Expected Analytics DeadLetterQueue to record poison-pill event")
        self.assertGreaterEqual(counts["fact"], 1, "Expected Analytics Fact_Events to remain operational after poison-pill")

    # --- 2 SECURITY & INVALID-DATA TESTS ---

    def test_S01_authentication_rbac_and_ownership_enforcement(self):
        # 1. Unauthenticated -> 401
        st_unauth, _, _ = http_json("/api/trips")
        self.assertEqual(st_unauth, 401)

        # 2. Rider calling driver-only location endpoint -> 403
        _, r1_token, r1 = register_user("rider", "s01a")
        _, r2_token, _ = register_user("rider", "s01b")
        st_role, _, _ = http_json("/api/location", method="POST", token=r1_token, body={"latitude": 21.0, "longitude": 105.8})
        self.assertEqual(st_role, 403)

        # 3. Spoofing another passengerId -> 403
        lat, lng = isolated_coords(11)
        st_spoof, _, _ = http_json(
            "/api/trips", method="POST", token=r1_token,
            body={"passengerId": str(r1["id"] + 999), "pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01},
        )
        self.assertEqual(st_spoof, 403)

        # 4. Cross-user trip inspection -> 403
        st_ok, created, _ = http_json(
            "/api/trips", method="POST", token=r1_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01},
        )
        self.assertEqual(st_ok, 200)
        st_cross, _, _ = http_json(f"/api/trips/{created['tripId']}", token=r2_token)
        self.assertEqual(st_cross, 403)

    def test_S02_input_validation_and_guarded_state_transitions(self):
        # 1. Short password -> 400
        st_pw, _, _ = http_json(
            "/api/auth/register", method="POST",
            body={"email": f"short_{uuid.uuid4().hex[:6]}@test.local", "password": "123", "role": "rider"},
        )
        self.assertEqual(st_pw, 400)

        # 2. Duplicate registration -> 409
        email, drv_token, _ = register_user("driver", "s02")
        st_dup, _, _ = http_json(
            "/api/auth/register", method="POST",
            body={"email": email, "password": "TestPassword#2026", "role": "driver"},
        )
        self.assertEqual(st_dup, 409)

        # 3. Invalid GPS coordinate -> 422
        st_gps, _, _ = http_json("/api/location", method="POST", token=drv_token, body={"latitude": 999.0, "longitude": 105.0})
        self.assertEqual(st_gps, 422)

        # 4. Invalid status transition while BUSY -> 409
        _, rdr_token, _ = register_user("rider", "s02")
        lat, lng = isolated_coords(12)
        http_json("/api/location", method="POST", token=drv_token, body={"latitude": lat, "longitude": lng})
        _, created, _ = http_json(
            "/api/trips", method="POST", token=rdr_token,
            body={"pickupLat": lat, "pickupLong": lng, "destLat": lat + 0.01, "destLong": lng + 0.01},
        )
        poll_trip(created["tripId"], drv_token, {"MATCHED"})
        st_busy, _, _ = http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})
        self.assertEqual(st_busy, 409)

        http_json(f"/api/trips/{created['tripId']}/cancel", method="PUT", token=rdr_token, body={"reason": "CLEANUP"})
        poll_driver_status(drv_token, "AVAILABLE")
        http_json("/api/location/status", method="PUT", token=drv_token, body={"status": "OFFLINE"})

    # --- 1 PERFORMANCE & SCALABILITY EXPERIMENT ---

    def test_P01_performance_and_scalability_experiment(self):
        # Load scripts/driver_simulator.py by path so IDE static analyzers resolve cleanly.
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "driver_simulator.py"))
        spec = importlib.util.spec_from_file_location("driver_simulator", script_path)
        driver_simulator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver_simulator)

        lat, lng = isolated_coords(13)
        summary = driver_simulator.run_benchmark(GATEWAY, driver_count=6, total_requests=24, concurrency=6, base_lat=lat, base_lng=lng)
        self.assertGreaterEqual(summary["gps_updates"]["success_rate_pct"], 95.0)
        self.assertGreaterEqual(summary["concurrent_bookings"]["success_rate_pct"], 95.0)


def main():
    global GATEWAY, SKIP_DOCKER_FAULTS
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gateway", default=GATEWAY)
    parser.add_argument("--skip-docker-faults", action="store_true")
    args, remaining = parser.parse_known_args()
    GATEWAY = args.gateway.rstrip("/")
    SKIP_DOCKER_FAULTS = args.skip_docker_faults
    unittest.main(argv=[sys.argv[0]] + remaining, verbosity=2)


if __name__ == "__main__":
    main()

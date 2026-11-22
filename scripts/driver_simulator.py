import argparse
import concurrent.futures
import json
import logging
import math
import random
import statistics
import time
import urllib.error
import urllib.request
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s | NODE: Driver-Simulator | %(levelname)s | %(message)s")


def http_json(url, method="GET", body=None, token=None, timeout=10):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None), (time.perf_counter() - started) * 1000.0
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return err.code, parsed, (time.perf_counter() - started) * 1000.0


def provision_user(gateway, email, password, role, full_name):
    status, data, _ = http_json(
        f"{gateway}/api/auth/register",
        method="POST",
        body={"email": email, "password": password, "role": role, "fullName": full_name},
    )
    if status == 201 and data and data.get("token"):
        return data["token"], data["user"]
    if status == 409:
        status, data, _ = http_json(
            f"{gateway}/api/auth/login",
            method="POST",
            body={"email": email, "password": password},
        )
        if status == 200 and data and data.get("token"):
            return data["token"], data["user"]
    raise RuntimeError(f"Failed to provision {role} {email}: status={status} body={data}")


def percentile(values, p):
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil((p / 100.0) * len(ordered)) - 1))
    return ordered[idx]


def run_simulate(gateway, count, duration, interval, min_lat, max_lat, min_lng, max_lng, prefix):
    run_id = prefix or uuid.uuid4().hex[:6]
    drivers = []
    logging.info("Provisioning %d simulated drivers through %s ...", count, gateway)
    for i in range(count):
        email = f"sim_{run_id}_drv_{i}@sim.local"
        token, user = provision_user(gateway, email, "SimPass#2026", "driver", f"Sim Driver {i}")
        drivers.append({
            "id": user["id"],
            "token": token,
            "lat": random.uniform(min_lat, max_lat),
            "lng": random.uniform(min_lng, max_lng),
        })
    logging.info("Provisioned %d drivers. Sending GPS updates for %ss (interval=%ss)...", len(drivers), duration, interval)

    deadline = time.monotonic() + duration if duration > 0 else float("inf")
    sent, ok = 0, 0
    try:
        while time.monotonic() < deadline:
            for d in drivers:
                d["lat"] = min(max_lat, max(min_lat, d["lat"] + random.uniform(-0.0002, 0.0002)))
                d["lng"] = min(max_lng, max(min_lng, d["lng"] + random.uniform(-0.0002, 0.0002)))
                status, _, ms = http_json(
                    f"{gateway}/api/location",
                    method="POST",
                    token=d["token"],
                    body={"driver_id": d["id"], "latitude": round(d["lat"], 6), "longitude": round(d["lng"], 6)},
                )
                sent += 1
                if status == 200:
                    ok += 1
                else:
                    logging.warning("Driver %s GPS update failed: HTTP %s (%.1fms)", d["id"], status, ms)
            logging.info("Tick complete: ok=%d/%d", ok, sent)
            if time.monotonic() < deadline:
                time.sleep(interval)
    except KeyboardInterrupt:
        logging.info("Stopped by user.")
    finally:
        # Leave simulated drivers OFFLINE so they do not hijack manual UI demos.
        for d in drivers:
            http_json(f"{gateway}/api/location/status", method="PUT", token=d["token"], body={"status": "OFFLINE"})
        logging.info("Cleanup complete: set %d simulated drivers to OFFLINE. Total GPS updates: %d/%d", len(drivers), ok, sent)


def run_benchmark(gateway, driver_count, total_requests, concurrency, base_lat, base_lng):
    run_id = uuid.uuid4().hex[:6]
    logging.info("Benchmark setup: %d drivers, %d GPS requests (concurrency=%d) against %s",
                 driver_count, total_requests, concurrency, gateway)
    drivers = []
    for i in range(driver_count):
        token, user = provision_user(gateway, f"bench_{run_id}_d{i}@sim.local", "BenchPass#2026", "driver", f"Bench Driver {i}")
        drivers.append({"id": user["id"], "token": token})

    latencies = []
    successes = 0
    started_all = time.perf_counter()

    def send_one(idx):
        d = drivers[idx % len(drivers)]
        lat = round(base_lat + random.uniform(-0.005, 0.005), 6)
        lng = round(base_lng + random.uniform(-0.005, 0.005), 6)
        status, _, ms = http_json(
            f"{gateway}/api/location",
            method="POST",
            token=d["token"],
            body={"driver_id": d["id"], "latitude": lat, "longitude": lng},
        )
        return status == 200, ms

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        for ok, ms in pool.map(send_one, range(total_requests)):
            latencies.append(ms)
            if ok:
                successes += 1

    elapsed = max(0.001, time.perf_counter() - started_all)

    # Also measure concurrent trip booking requests (distinct riders, 1:1 with drivers)
    rider_count = min(driver_count, max(2, concurrency))
    riders = [
        provision_user(gateway, f"bench_{run_id}_r{i}@sim.local", "BenchPass#2026", "rider", f"Bench Rider {i}")
        for i in range(rider_count)
    ]
    trip_latencies = []
    trip_ok = 0
    trip_ids = []
    trip_start = time.perf_counter()

    def book_one(idx):
        token, user = riders[idx]
        status, body, ms = http_json(
            f"{gateway}/api/trips",
            method="POST",
            token=token,
            body={
                "pickupLat": round(base_lat + 0.0001 * idx, 6),
                "pickupLong": round(base_lng + 0.0001 * idx, 6),
                "destLat": round(base_lat + 0.015, 6),
                "destLong": round(base_lng + 0.015, 6),
                "vehicleType": "MOTORBIKE",
            },
        )
        return status == 200, body.get("tripId") if isinstance(body, dict) else None, token, ms

    with concurrent.futures.ThreadPoolExecutor(max_workers=rider_count) as pool:
        for ok, tid, token, ms in pool.map(book_one, range(rider_count)):
            trip_latencies.append(ms)
            if ok and tid:
                trip_ok += 1
                trip_ids.append((tid, token))
    trip_elapsed = max(0.001, time.perf_counter() - trip_start)

    # Clean up benchmark trips & drivers so demo stays clean.
    time.sleep(2.0)
    for tid, token in trip_ids:
        http_json(f"{gateway}/api/trips/{tid}/cancel", method="PUT", token=token, body={"reason": "BENCHMARK_CLEANUP"})
    time.sleep(1.0)
    for d in drivers:
        http_json(f"{gateway}/api/location/status", method="PUT", token=d["token"], body={"status": "OFFLINE"})

    summary = {
        "gateway": gateway,
        "gps_updates": {
            "total": total_requests,
            "success": successes,
            "success_rate_pct": round(100.0 * successes / max(1, total_requests), 2),
            "elapsed_s": round(elapsed, 3),
            "throughput_rps": round(total_requests / elapsed, 2),
            "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p50_ms": round(percentile(latencies, 50), 2),
            "p95_ms": round(percentile(latencies, 95), 2),
        },
        "concurrent_bookings": {
            "total": rider_count,
            "success": trip_ok,
            "success_rate_pct": round(100.0 * trip_ok / max(1, rider_count), 2),
            "elapsed_s": round(trip_elapsed, 3),
            "throughput_rps": round(rider_count / trip_elapsed, 2),
            "avg_ms": round(statistics.mean(trip_latencies), 2) if trip_latencies else 0.0,
            "p95_ms": round(percentile(trip_latencies, 95), 2),
        },
    }
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Ride-Hailing Driver Simulator & Scalability Benchmark")
    parser.add_argument("--gateway", default="http://localhost:3000", help="API Gateway base URL")
    parser.add_argument("--mode", choices=["simulate", "benchmark"], default="simulate")
    parser.add_argument("--drivers", type=int, default=5, help="Number of simulated drivers")
    parser.add_argument("--duration", type=float, default=15.0, help="Simulate duration in seconds (0 = infinite)")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between GPS ticks")
    parser.add_argument("--requests", type=int, default=40, help="Total GPS requests in benchmark mode")
    parser.add_argument("--concurrency", type=int, default=8, help="Concurrent workers in benchmark mode")
    # Default bounding box covers the 7 central Hanoi districts matching frontend/src/places.js:
    # lat in [20.9800, 21.0600], lng in [105.7700, 105.8700]
    parser.add_argument("--lat", type=float, default=21.0200, help="Center latitude (default: Hanoi center)")
    parser.add_argument("--lng", type=float, default=105.8200, help="Center longitude (default: Hanoi center)")
    parser.add_argument("--lat-span", type=float, default=0.04, help="Half-span for latitude (default +/-0.04 -> 20.98..21.06)")
    parser.add_argument("--lng-span", type=float, default=0.05, help="Half-span for longitude (default +/-0.05 -> 105.77..105.87)")
    parser.add_argument("--prefix", default="", help="Optional account prefix")
    args = parser.parse_args()

    gateway = args.gateway.rstrip("/")
    if args.mode == "benchmark":
        run_benchmark(gateway, args.drivers, args.requests, args.concurrency, args.lat, args.lng)
    else:
        run_simulate(
            gateway, args.drivers, args.duration, args.interval,
            args.lat - args.lat_span, args.lat + args.lat_span,
            args.lng - args.lng_span, args.lng + args.lng_span,
            args.prefix,
        )


if __name__ == "__main__":
    main()

import argparse
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s | NODE: Fault-Injector | %(levelname)s | %(message)s")


def produce_via_kafka_container(topic, key, payload_str, container="kafka"):
    # Uses the Kafka container directly so no local librdkafka/confluent-kafka wheel is required on Windows.
    cmd = [
        "docker", "compose", "exec", "-T", container,
        "kafka-console-producer",
        "--bootstrap-server", "kafka:29092",
        "--topic", topic,
        "--property", "parse.key=true",
        "--property", "key.separator=|",
    ]
    line = f"{key}|{payload_str}\n"
    res = subprocess.run(cmd, input=line, text=True, capture_output=True, check=False)
    if res.returncode != 0:
        raise RuntimeError(f"Kafka produce failed: {res.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description="Kafka Fault Injection Tool for DLQ and Idempotency Testing")
    parser.add_argument(
        "--mode",
        choices=["poison-pill", "duplicate-event", "raw-request"],
        default="poison-pill",
        help="Fault injection scenario",
    )
    parser.add_argument("--topic", default="trip.requested", help="Target Kafka topic")
    parser.add_argument("--allow-orphan", action="store_true", help="Required for raw-request mode")
    args = parser.parse_args()

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if args.mode == "poison-pill":
        # Malformed envelope triggers Analytics DeadLetterQueue and Matching invalid-event skip without crashing consumers.
        bad_key = f"poison_{uuid.uuid4().hex[:6]}"
        bad_payload = json.dumps({"broken": True, "reason": "fault-injection-missing-metadata-and-payload"})
        produce_via_kafka_container(args.topic, bad_key, bad_payload)
        logging.info("Injected poison-pill into %s (key=%s). Check Analytics DataWarehouseDB.DeadLetterQueue.", args.topic, bad_key)
        return

    if args.mode == "duplicate-event":
        # Sends the exact same event_id twice to prove deduplication in Analytics/Matching/Booking.
        event_id = f"dup_{uuid.uuid4().hex[:8]}"
        trip_id = f"trip_dup_{uuid.uuid4().hex[:6]}"
        event = {
            "metadata": {
                "event_id": event_id,
                "correlation_id": trip_id,
                "event_type": "TRIP_CANCELLED",
                "timestamp": now,
                "source": "fault-injector",
            },
            "payload": {
                "trip_id": trip_id,
                "passenger_id": "0",
                "driver_id": None,
                "cancel_reason": "DUPLICATE_TEST",
            },
        }
        raw = json.dumps(event)
        produce_via_kafka_container("trip.cancelled", trip_id, raw)
        produce_via_kafka_container("trip.cancelled", trip_id, raw)
        logging.info("Injected duplicate event_id=%s twice into trip.cancelled. Verify only 1 record in Fact_Events.", event_id)
        return

    if not args.allow_orphan:
        raise SystemExit("Refusing raw-request without --allow-orphan: use POST /api/trips via API Gateway for real trips.")

    trip_id = f"trip_mock_{uuid.uuid4().hex[:6]}"
    fake_trip = {
        "metadata": {
            "event_id": f"req_{uuid.uuid4().hex[:8]}",
            "correlation_id": trip_id,
            "event_type": "TRIP_REQUESTED",
            "timestamp": now,
            "source": "mock-booking",
        },
        "payload": {
            "trip_id": trip_id,
            "passenger_id": "usr_mock",
            "pickup_lat": 16.0544,
            "pickup_long": 108.2022,
            "destination_lat": 16.0644,
            "destination_long": 108.2122,
            "vehicle_type": "MOTORBIKE",
        },
    }
    produce_via_kafka_container("trip.requested", trip_id, json.dumps(fake_trip))
    logging.info("Injected raw trip.requested for %s.", trip_id)


if __name__ == "__main__":
    main()

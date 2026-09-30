import os
import json
import uuid
import random
import logging
from datetime import datetime
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NODE: Mock-Booking | %(levelname)s | %(message)s'
)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:9092")
producer = Producer({'bootstrap.servers': KAFKA_BROKER})
trip_id = f"trip_ABC{uuid.uuid4().hex[:6]}"

MIN_LAT, MAX_LAT = 20.9800, 21.0600
MIN_LNG, MAX_LNG = 105.7700, 105.8700

random_pickup_lat = round(random.uniform(MIN_LAT, MAX_LAT), 6)
random_pickup_long = round(random.uniform(MIN_LNG, MAX_LNG), 6)
random_dest_lat = round(random.uniform(MIN_LAT, MAX_LAT), 6)
random_dest_long = round(random.uniform(MIN_LNG, MAX_LNG), 6)

fake_trip = {
    "metadata": {
        "event_id": f"req_{uuid.uuid4().hex[:8]}",
        "correlation_id": trip_id,
        "event_type": "TRIP_REQUESTED",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "booking-service"
    },
    "payload": {
        "trip_id": trip_id,
        "passenger_id": f"usr_{random.randint(100, 999)}", 
        "pickup_lat": random_pickup_lat,
        "pickup_long": random_pickup_long,
        "destination_lat": random_dest_lat,
        "destination_long": random_dest_long,
        "vehicle_type": random.choice(["MOTORBIKE", "CAR"]) 
    }
}

producer.produce('trip.requested', json.dumps(fake_trip).encode('utf-8'))
producer.flush()

logging.info(f"Hành khách {fake_trip['payload']['passenger_id']} yêu cầu xe tại [{random_pickup_lat}, {random_pickup_long}]")
logging.info(f"Đã đẩy sự kiện TRIP_REQUESTED cho cuốc {trip_id} lên Kafka!")
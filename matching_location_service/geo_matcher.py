import os
import json
import sys
import uuid
import logging
from datetime import datetime
from confluent_kafka import Consumer, Producer
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NODE: Matching-Worker | %(levelname)s | %(message)s'
)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

try:
    client = MongoClient(MONGO_URI)
    db = client["RideHailingDB"]
    live_locations = db["LiveLocations"]

    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'matching_group_v2',
        'auto.offset.reset': 'latest'
    })
    consumer.subscribe(['trip.requested'])

    producer = Producer({'bootstrap.servers': KAFKA_BROKER})
    logging.info("MATCHING SERVICE ĐÃ SẴN SÀNG.")
except Exception as e:
    logging.error(f"Lỗi kết nối hạ tầng: {e}")
    sys.exit(1)

try:
    while True:
        msg = consumer.poll(1.0)
        
        if msg is None:
            continue
        if msg.error():
            continue 

        req = json.loads(msg.value().decode('utf-8'))
        event_id = req['metadata']['event_id']          
        trip_id = req['metadata']['correlation_id']     
        rider_lat = req['payload']['pickup_lat']
        rider_lng = req['payload']['pickup_long']       
        dest_lat = req['payload'].get('destination_lat')
        dest_lng = req['payload'].get('destination_long')

        logging.info(f"EVENT: TRIP_REQUESTED | Nhận cuốc [ {trip_id} ] tại [{rider_lat}, {rider_lng}]")

        # KHÓA LŨY ĐẲNG (Idempotency)
        try:
            db["ProcessedTrips"].insert_one({"_id": event_id, "processed_at": datetime.utcnow()})
        except DuplicateKeyError:
            logging.warning(f"IDEMPOTENCY SKIP | Đã bỏ qua sự kiện lặp {event_id} của cuốc {trip_id}")
            continue 

        # VÒNG SƠ KHẢO
        candidates = list(live_locations.find({
            "status": "AVAILABLE",
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [rider_lng, rider_lat] 
                    },
                    "$maxDistance": 3000
                }
            }
        }).limit(5))

        # VÒNG CHUNG KẾT (Tính ETA)
        best_driver_id = None
        lowest_eta = float('inf') 

        for driver in candidates:
            driver_lng = driver['location']['coordinates'][0]
            driver_lat = driver['location']['coordinates'][1]
            
            dx_meters = abs(driver_lng - rider_lng) * 111000 
            dy_meters = abs(driver_lat - rider_lat) * 111000 
            
            manhattan_distance = dx_meters + dy_meters 
            estimated_seconds = (manhattan_distance / 9.7) + 45
            
            if estimated_seconds < lowest_eta:
                lowest_eta = estimated_seconds
                best_driver_id = driver['driver_id']

        # ĐÓNG GÓI OUTPUT
        timestamp_now = datetime.utcnow().isoformat() + "Z"
        
        if best_driver_id:
            # KHÓA BI QUAN (Pessimistic Locking)
            live_locations.update_one({"driver_id": best_driver_id}, {"$set": {"status": "BUSY"}})
            
            event = {
                "metadata": {
                    "event_id": f"mat_{uuid.uuid4().hex[:8]}",
                    "correlation_id": trip_id,
                    "event_type": "DRIVER_MATCHED",
                    "timestamp": timestamp_now,
                    "source": "matching-service"
                },
                "payload": {
                    "trip_id": trip_id,
                    "driver_id": str(best_driver_id),
                    "distance_to_pickup_km": round(manhattan_distance / 1000, 2), 
                    "estimated_time_arrival_mins": int(lowest_eta // 60),
                    "destination_lat": dest_lat,
                    "destination_long": dest_lng
                }
            }
            producer.produce('driver.matched', json.dumps(event).encode('utf-8'))
            logging.info(f"EVENT: DRIVER_MATCHED | Đã chốt Xe {best_driver_id} cho cuốc {trip_id} (ETA: {int(lowest_eta)}s)")
        else:
            event = {
                "metadata": {
                    "event_id": f"fai_{uuid.uuid4().hex[:8]}",
                    "correlation_id": trip_id,
                    "event_type": "MATCHING_FAILED",
                    "timestamp": timestamp_now,
                    "source": "matching-service"
                },
                "payload": {
                    "trip_id": trip_id,
                    "reason": "TIMEOUT_NO_DRIVERS"
                }
            }
            producer.produce('matching.failed', json.dumps(event).encode('utf-8'))
            logging.error(f"EVENT: MATCHING_FAILED | Không tìm thấy xe cho cuốc {trip_id}")
        
        producer.flush()

except KeyboardInterrupt:
    logging.info("Đang ngắt kết nối Kafka và MongoDB...")
finally:
    consumer.close()
    client.close()
    logging.info("Đã đóng Matching Service")
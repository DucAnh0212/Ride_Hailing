import os
import json
import logging
from datetime import datetime
from confluent_kafka import Consumer
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

# Cấu hình Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NODE: Analytics-DW | %(levelname)s | %(message)s'
)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:9092")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

try:
    # KẾT NỐI DATA WAREHOUSE 
    client = MongoClient(MONGO_URI)
    dwh_db = client["DataWarehouseDB"] 
    fact_events = dwh_db["Fact_Events"]
    dlq_collection = dwh_db["DeadLetterQueue"] # Hàng đợi thư chết
    
    # Khởi tạo Kafka Consumer
    consumer = Consumer({
        'bootstrap.servers': KAFKA_BROKER,
        'group.id': 'analytics_data_lake_group',
        'auto.offset.reset': 'earliest' # Đọc lại từ đầu để vét sạch data lịch sử
    })
    
    # Lắng nghe (Subscribe) toàn bộ các topic hiện có
    consumer.subscribe(['trip.requested', 'driver.matched', 'matching.failed'])
    
    logging.info("ANALYTICS ELT WORKER ĐÃ SẴN SÀNG HÚT DỮ LIỆU VỀ DATA WAREHOUSE.")
except Exception as e:
    logging.error(f"Lỗi khởi tạo hạ tầng: {e}")
    exit(1)

try:
    while True:
        msg = consumer.poll(1.0)
        
        if msg is None:
            continue
        if msg.error():
            logging.error(f"Kafka Error: {msg.error()}")
            continue

        raw_value = msg.value().decode('utf-8')
        topic_name = msg.topic()

        try:
            # 1. EXTRACT 
            event_data = json.loads(raw_value)
            # Kiểm tra tính toàn vẹn của JSON Contract (Envelope Pattern)
            if 'metadata' not in event_data or 'payload' not in event_data:
                raise ValueError("JSON thiếu khối metadata hoặc payload")

            event_id = event_data['metadata']['event_id']
            
            # 2. TRANSFORM 
            dwh_record = {
                "_id": event_id, # Dùng event_id làm Khóa chính để lọc trùng (Deduplication)
                "topic_source": topic_name,
                "ingested_at": datetime.utcnow(),
                "correlation_id": event_data['metadata'].get('correlation_id'),
                "event_type": event_data['metadata'].get('event_type'),
                "event_timestamp": event_data['metadata'].get('timestamp'),
                "raw_payload": event_data['payload']
            }

            # 3. LOAD 
            fact_events.insert_one(dwh_record)
            logging.info(f"INGESTED | Lưu thành công sự kiện {event_data['metadata'].get('event_type')} (ID: {event_id})")

        except DuplicateKeyError:
            # XỬ LÝ LỌC TRÙNG LẶP (DEDUPLICATION)
            logging.warning(f"DEDUPLICATED | Bỏ qua sự kiện bị lặp {event_id}")
            
        except Exception as e:
            # XỬ LÝ HÀNG ĐỢI THƯ CHẾT (DEAD-LETTER QUEUE)
            error_record = {
                "failed_at": datetime.utcnow(),
                "topic": topic_name,
                "raw_message": raw_value,
                "error_reason": str(e)
            }
            dlq_collection.insert_one(error_record)
            logging.error(f"DEAD-LETTER QUEUE | Đẩy message lỗi vào DLQ. Lý do: {e}")

except KeyboardInterrupt:
    logging.info("Nhận tín hiệu dừng luồng Analytics từ người dùng.")
finally:
    consumer.close()
    client.close()
    logging.info("Đã tắt luồng Analytics.")
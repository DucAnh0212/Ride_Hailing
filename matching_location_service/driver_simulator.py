import os
import sys
import random
import pyodbc
import logging
import time
import requests
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s | SIMULATOR | %(levelname)s | %(message)s')

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)

API_URL = os.getenv("LOCATION_API_URL", "http://127.0.0.1:8000/api/location")

# 2. Lấy cấu hình SQL từ file .env gốc
sql_host = os.getenv("SQL_SERVER_HOST", "localhost")
sql_port = os.getenv("SQL_SERVER_PORT", "14333") 
sql_user = os.getenv("SQL_SERVER_USER", "sa")
sql_pass = os.getenv("SQL_SERVER_PASSWORD", "")

logging.info(f"Đang kết nối SQL Server tại {sql_host}:{sql_port}...")

try:
    # 3. Kết nối an toàn
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={sql_host},{sql_port};DATABASE=RideHailingDB;UID={sql_user};PWD={sql_pass};TrustServerCertificate=yes;"
    sql_conn = pyodbc.connect(conn_str)
    cursor = sql_conn.cursor()
    
    cursor.execute("SELECT UserID FROM Users WHERE Role = 'Driver'")
    driver_ids = [row[0] for row in cursor.fetchall()]
    
    logging.info(f"Đã tải thành công {len(driver_ids)} tài xế từ DB.")
    
except Exception as e:
    logging.error(f"Lỗi kết nối DB trong Simulator: {e}")
    exit(1)

NUM_DRIVERS = len(driver_ids)

MIN_LAT, MAX_LAT = 20.9800, 21.0600
MIN_LNG, MAX_LNG = 105.7700, 105.8700

drivers_state = {}
for driver_id in driver_ids:
    drivers_state[driver_id] = {
        "lat": random.uniform(MIN_LAT, MAX_LAT),
        "lng": random.uniform(MIN_LNG, MAX_LNG)
    }

try:
    while True:
        active_drivers = random.sample(driver_ids, min(50, NUM_DRIVERS))
        
        for driver_id in active_drivers:
            delta_lat = random.uniform(-0.0001, 0.0001)
            delta_lng = random.uniform(-0.0001, 0.0001)
            
            next_lat = drivers_state[driver_id]["lat"] + delta_lat
            next_lng = drivers_state[driver_id]["lng"] + delta_lng
            
            # Cập nhật tọa độ
            if not (MIN_LAT <= next_lat <= MAX_LAT):
                delta_lat = -delta_lat  
            if not (MIN_LNG <= next_lng <= MAX_LNG):
                delta_lng = -delta_lng  
                
            drivers_state[driver_id]["lat"] += delta_lat
            drivers_state[driver_id]["lng"] += delta_lng
            
            payload = {
                "driver_id": driver_id,
                "latitude": round(drivers_state[driver_id]["lat"], 6),
                "longitude": round(drivers_state[driver_id]["lng"], 6)
            }
            
            try:
                response = requests.post(API_URL, json=payload, timeout=5)
                logging.info(f"Xe {driver_id} đã di chuyển tới [{payload['latitude']}, {payload['longitude']}]")
            except requests.exceptions.Timeout:
                logging.warning(f"Xe {driver_id}: Mạng chậm, API timeout.")
            except Exception as e:
                logging.error(f"Xe {driver_id}: Lỗi gửi tọa độ - {e}")
                
        time.sleep(0.5)

except KeyboardInterrupt:
    time.sleep(1)
    print("Đã tắt Simulator!")
    sys.exit(0)
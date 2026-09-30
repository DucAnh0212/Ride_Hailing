import requests
import random
import time
import sys

API_URL = "http://127.0.0.1:8000/api/location"
NUM_DRIVERS = 500

MIN_LAT, MAX_LAT = 20.9800, 21.0600
MIN_LNG, MAX_LNG = 105.7700, 105.8700

drivers_state = {}
for i in range(1, NUM_DRIVERS + 1):
    drivers_state[i] = {
        "lat": random.uniform(MIN_LAT, MAX_LAT),
        "lng": random.uniform(MIN_LNG, MAX_LNG)
    }

try:
    while True:
        active_drivers = random.sample(range(1, NUM_DRIVERS + 1), 20)
        
        for driver_id in active_drivers:
            delta_lat = random.uniform(-0.0001, 0.0001)
            delta_lng = random.uniform(-0.0001, 0.0001)
            
            next_lat = drivers_state[driver_id]["lat"] + delta_lat
            next_lng = drivers_state[driver_id]["lng"] + delta_lng
            
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
                requests.post(API_URL, json=payload, timeout=1)
                print(f"Xe {driver_id} di chuyển tới [{payload['latitude']}, {payload['longitude']}]")
            except Exception:
                pass 
                
        time.sleep(0.5)

except KeyboardInterrupt:
    time.sleep(1)
    print("Đã tắt Simulator!")
    sys.exit(0) 
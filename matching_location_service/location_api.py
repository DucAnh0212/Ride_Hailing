import os
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

# Cấu hình Logging 
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NODE: Location-API | %(levelname)s | %(message)s'
)

app = FastAPI()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

try:
    client = MongoClient(MONGO_URI)
    db = client["RideHailingDB"]
    live_locations = db["LiveLocations"]
    
    # Đảm bảo index được tạo
    live_locations.create_index([("location", "2dsphere")])
    live_locations.create_index("driver_id", unique=True)
    logging.info("Kết nối MongoDB thành công. Đã khởi tạo 2dsphere index.")
except Exception as e:
    logging.error(f"Lỗi kết nối CSDL: {e}")

class LocationData(BaseModel):
    driver_id: int
    latitude: float
    longitude: float

@app.post("/api/location")
async def update_location(data: LocationData):
    try:
        geojson_point = {
            "type": "Point",
            "coordinates": [data.longitude, data.latitude]
        }
        
        live_locations.update_one(
            {"driver_id": data.driver_id},
            {
                "$set": {
                    "location": geojson_point,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "status": "AVAILABLE" 
                }
            },
            upsert=True
        )
        return {"status": "success", "message": "Location updated"}
    except Exception as e:
        logging.error(f"Lỗi cập nhật tọa độ xe {data.driver_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
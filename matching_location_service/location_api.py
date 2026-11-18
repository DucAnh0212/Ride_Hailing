import os
import logging
from datetime import datetime
from typing import Literal
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

class DriverStatusData(BaseModel):
    driver_id: int
    status: Literal["AVAILABLE", "OFFLINE"]


@app.put("/api/location/status")
async def update_driver_status(data: DriverStatusData):
    # Internal online/offline operation. Only Matching may acquire/release BUSY.
    identity = {"driver_id": {"$in": [data.driver_id, str(data.driver_id)]}}
    updated = live_locations.update_one(
        {**identity, "status": {"$in": ["AVAILABLE", "OFFLINE"]},
         "active_trip_id": {"$exists": False}},
        {"$set": {"status": data.status, "updated_at": datetime.utcnow()}}
    )
    if updated.matched_count == 0:
        if live_locations.find_one(identity) is None:
            raise HTTPException(status_code=404, detail="Driver location not found")
        raise HTTPException(status_code=409, detail="Driver has an active reservation or is BUSY")
    return {"status": "success", "driver_id": data.driver_id, "driver_status": data.status}


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
@app.get("/api/location/{driver_id}")
async def get_location(driver_id: int):
    # Internal endpoint; Gateway restricts access to the authenticated driver's ID.
    driver = live_locations.find_one({"driver_id": driver_id}, {"_id": 0})
    if not driver:
        return {"driver_id": driver_id, "status": "OFFLINE", "location": None, "active_trip_id": None}
    return {"driver_id": driver_id, "status": driver.get("status", "OFFLINE"),
            "location": driver.get("location"), "active_trip_id": driver.get("active_trip_id"),
            "updated_at": driver.get("updated_at")}

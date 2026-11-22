import os
import logging
from datetime import datetime
from typing import Literal
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | NODE: Location-API | %(levelname)s | %(message)s'
)

app = FastAPI()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "LocationDB")

try:
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    live_locations = db["LiveLocations"]

    live_locations.create_index([("location", "2dsphere")])
    live_locations.create_index("driver_id", unique=True)
    live_locations.create_index("active_trip_id", unique=True, sparse=True)
    logging.info("Connected MongoDB db=%s with 2dsphere/driver/trip indexes.", MONGO_DB)
except Exception as e:
    logging.error(f"Lỗi kết nối CSDL: {e}")


class LocationData(BaseModel):
    driver_id: int
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)


class DriverStatusData(BaseModel):
    driver_id: int
    status: Literal["AVAILABLE", "OFFLINE"]


class ReserveDriverRequest(BaseModel):
    trip_id: str = Field(..., min_length=1)
    pickup_lat: float = Field(..., ge=-90.0, le=90.0)
    pickup_long: float = Field(..., ge=-180.0, le=180.0)
    max_distance_m: int = Field(default=3000, ge=100, le=50000)
    limit: int = Field(default=5, ge=1, le=20)


class ReleaseDriverRequest(BaseModel):
    trip_id: str = Field(..., min_length=1)


def _manhattan_meters(driver_doc, lat: float, lng: float) -> float:
    coordinates = driver_doc["location"]["coordinates"]
    return (abs(coordinates[0] - lng) + abs(coordinates[1] - lat)) * 111000.0


@app.get("/health")
async def health():
    return {"status": "UP", "service": "location-service", "database": MONGO_DB}


@app.put("/api/location/status")
async def update_driver_status(data: DriverStatusData):
    # Online/offline toggle. Only Matching may acquire/release BUSY via /internal/drivers/*.
    identity = {"driver_id": {"$in": [data.driver_id, str(data.driver_id)]}}
    updated = live_locations.update_one(
        {**identity, "status": {"$in": ["AVAILABLE", "OFFLINE"]},
         "active_trip_id": {"$exists": False}},
        {"$set": {"status": data.status, "updated_at": datetime.utcnow()}}
    )
    if updated.matched_count == 0:
        if live_locations.find_one(identity) is None:
            raise HTTPException(status_code=404, detail="Tài xế chưa gửi vị trí nên chưa thể đổi trạng thái")
        raise HTTPException(status_code=409, detail="Tài xế đang bận giữ chuyến nên không thể đổi trạng thái")
    logging.info("STATUS | driver=%s status=%s", data.driver_id, data.status)
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
    driver = live_locations.find_one({"driver_id": driver_id}, {"_id": 0})
    if not driver:
        return {"driver_id": driver_id, "status": "OFFLINE", "location": None, "active_trip_id": None}
    return {"driver_id": driver_id, "status": driver.get("status", "OFFLINE"),
            "location": driver.get("location"), "active_trip_id": driver.get("active_trip_id"),
            "updated_at": driver.get("updated_at")}


@app.post("/internal/drivers/reserve")
async def reserve_driver(req: ReserveDriverRequest):
    # Internal service-to-service API for Matching Worker so Matching never accesses LocationDB directly.
    best = live_locations.find_one({"status": "BUSY", "active_trip_id": req.trip_id})
    if best is None:
        candidates = list(live_locations.find({
            "status": "AVAILABLE",
            "location": {
                "$near": {
                    "$geometry": {"type": "Point", "coordinates": [req.pickup_long, req.pickup_lat]},
                    "$maxDistance": req.max_distance_m
                }
            }
        }).limit(req.limit))
        for driver in sorted(candidates, key=lambda d: _manhattan_meters(d, req.pickup_lat, req.pickup_long)):
            best = live_locations.find_one_and_update(
                {"driver_id": driver["driver_id"], "status": "AVAILABLE"},
                {"$set": {"status": "BUSY", "active_trip_id": req.trip_id, "updated_at": datetime.utcnow()}}
            )
            if best is not None:
                break
    if best is None:
        return {"matched": False}
    meters = _manhattan_meters(best, req.pickup_lat, req.pickup_long)
    logging.info("RESERVE | trip=%s driver=%s distance_m=%.1f", req.trip_id, best["driver_id"], meters)
    return {
        "matched": True,
        "driver_id": str(best["driver_id"]),
        "distance_to_pickup_km": round(meters / 1000.0, 2),
        "estimated_time_arrival_mins": int(((meters / 9.7) + 45) // 60)
    }


@app.post("/internal/drivers/release")
async def release_driver(req: ReleaseDriverRequest):
    res = live_locations.update_many(
        {"status": "BUSY", "active_trip_id": req.trip_id},
        {"$set": {"status": "AVAILABLE", "updated_at": datetime.utcnow()},
         "$unset": {"active_trip_id": ""}}
    )
    logging.info("RELEASE | trip=%s released=%s", req.trip_id, res.modified_count)
    return {"released": res.modified_count}


@app.get("/internal/drivers/busy")
async def list_busy_drivers():
    cursor = live_locations.find(
        {"status": "BUSY", "active_trip_id": {"$exists": True}},
        {"_id": 0, "driver_id": 1, "active_trip_id": 1}
    )
    return list(cursor)

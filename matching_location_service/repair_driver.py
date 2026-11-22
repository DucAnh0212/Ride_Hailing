import argparse
import os
import uuid
from datetime import datetime
import requests
from bson import json_util
from pymongo import MongoClient


def repair(db, trips, driver_id, expected_trip, apply=False):
    history = [t for t in trips if str(t.get('driverId')) == str(driver_id)]
    if not history or not any(t['tripId'] == expected_trip and t['status'] in ('COMPLETED', 'CANCELED') for t in history):
        raise RuntimeError('Expected terminal trip not confirmed by Booking')
    if any(t['status'] not in ('COMPLETED', 'CANCELED') for t in history):
        raise RuntimeError('Driver still has a non-terminal trip; refusing repair')
    before = db['LiveLocations'].find_one({'driver_id': driver_id})
    if not before or before['status'] != 'BUSY' or 'active_trip_id' in before:
        raise RuntimeError('Not an untagged legacy BUSY driver; refusing repair')
    result = {'driver_id': driver_id, 'expected_trip': expected_trip, 'before': before, 'apply': apply}
    if apply:
        audit_id = 'legacy-repair-' + uuid.uuid4().hex
        db['DriverRepairs'].insert_one({'_id': audit_id, **result, 'recorded_at': datetime.utcnow(), 'state': 'PREPARED'})
        match = {'_id': before['_id'], 'status': 'BUSY', 'active_trip_id': {'$exists': False}, 'updated_at': before.get('updated_at')}
        changed = db['LiveLocations'].update_one(match, {'$set': {'status': 'AVAILABLE'}}).modified_count
        db['DriverRepairs'].update_one({'_id': audit_id}, {'$set': {'state': 'APPLIED' if changed else 'CONFLICT'}})
        if changed != 1:
            raise RuntimeError('Driver changed concurrently; no repair applied')
        result.update({'audit_id': audit_id, 'after': db['LiveLocations'].find_one({'driver_id': driver_id})})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--driver-id', type=int, required=True)
    parser.add_argument('--expected-trip', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    response = requests.get(os.getenv('BOOKING_SERVICE_URL', 'http://localhost:8080') + '/api/trips', timeout=10)
    response.raise_for_status()
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
    try:
        print(json_util.dumps(repair(client[os.getenv('MONGO_DB', 'LocationDB')], response.json(), args.driver_id, args.expected_trip, args.apply), indent=2))
    finally:
        client.close()

from datetime import datetime
import requests

TERMINAL = {'COMPLETED', 'CANCELED'}


class LocationClient:
    def __init__(self, base_url, timeout=5):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()

    def reserve(self, trip_id, pickup_lat, pickup_long, max_distance_m=3000, limit=5):
        response = self.session.post(
            f'{self.base_url}/internal/drivers/reserve',
            json={
                'trip_id': trip_id,
                'pickup_lat': pickup_lat,
                'pickup_long': pickup_long,
                'max_distance_m': max_distance_m,
                'limit': limit,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def release(self, trip_id):
        response = self.session.post(
            f'{self.base_url}/internal/drivers/release',
            json={'trip_id': trip_id},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return int(response.json().get('released', 0))

    def list_busy(self):
        response = self.session.get(
            f'{self.base_url}/internal/drivers/busy',
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            raise ValueError('Unexpected Location busy response')
        return data


def finished(db, trip_id):
    return db['FinishedTrips'].find_one({'_id': trip_id}) is not None


def finish_trip(db, location_client, trip_id, status):
    if not isinstance(trip_id, str) or not trip_id or status not in TERMINAL:
        raise ValueError('Invalid terminal trip')
    # Tombstone before release: cancel-before-request and repeated events are safe.
    db['FinishedTrips'].update_one(
        {'_id': trip_id},
        {'$setOnInsert': {'status': status, 'finished_at': datetime.utcnow()}},
        upsert=True,
    )
    return location_client.release(trip_id)


def reconcile(db, location_client, trips):
    if not isinstance(trips, list) or any(
        not isinstance(t, dict) or 'tripId' not in t or 'status' not in t for t in trips
    ):
        raise ValueError('Unexpected Booking response')
    busy_drivers = location_client.list_busy()
    if not busy_drivers:
        return 0
    by_id = {t['tripId']: t for t in trips}
    released = 0
    for driver in busy_drivers:
        trip = by_id.get(driver.get('active_trip_id'))
        if trip and trip['status'] in TERMINAL:
            released += finish_trip(db, location_client, trip['tripId'], trip['status'])
    return released

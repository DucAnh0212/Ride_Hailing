"""Reservation lifecycle. Never release a driver by driver_id alone.

BEFORE: BUSY had no owning trip and no terminal-event consumer.
AFTER: active_trip_id guards every release; FinishedTrips prevents late matching.
See docs/driver-wait-fix-20261117 for the original source and rollback.
"""
from datetime import datetime

TERMINAL = {'COMPLETED', 'CANCELED'}


def finished(db, trip_id):
    return db['FinishedTrips'].find_one({'_id': trip_id}) is not None


def finish_trip(db, trip_id, status):
    if not isinstance(trip_id, str) or not trip_id or status not in TERMINAL:
        raise ValueError('Invalid terminal trip')
    # Tombstone before release: cancel-before-request and repeated events are safe.
    db['FinishedTrips'].update_one({'_id': trip_id}, {'$setOnInsert': {
        'status': status, 'finished_at': datetime.utcnow()}}, upsert=True)
    return db['LiveLocations'].update_many(
        {'status': 'BUSY', 'active_trip_id': trip_id},
        {'$set': {'status': 'AVAILABLE', 'updated_at': datetime.utcnow()},
         '$unset': {'active_trip_id': ''}}
    ).modified_count


def reconcile(db, trips):
    """Repair only tagged reservations confirmed terminal by Booking.

    Legacy untagged BUSY records require the explicit audited repair script.
    """
    if not isinstance(trips, list) or any(not isinstance(t, dict) or 'tripId' not in t or 'status' not in t for t in trips):
        raise ValueError('Unexpected Booking response')
    by_id = {t['tripId']: t for t in trips}
    released = 0
    for driver in db['LiveLocations'].find({'status': 'BUSY', 'active_trip_id': {'$exists': True}}):
        trip = by_id.get(driver['active_trip_id'])
        if trip and trip['status'] in TERMINAL:
            released += finish_trip(db, trip['tripId'], trip['status'])
    return released

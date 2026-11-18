import os
import json
import uuid
import time
import logging
from datetime import datetime
import requests
from confluent_kafka import Consumer, Producer
from pymongo import MongoClient
from dotenv import load_dotenv
from driver_lifecycle import finished, finish_trip, reconcile

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | NODE: Matching-Worker | %(levelname)s | %(message)s')


class Matcher:
    def __init__(self, db, producer):
        self.db = db
        self.drivers = db['LiveLocations']
        self.producer = producer

    def publish(self, topic, event):
        errors = []
        self.producer.produce(topic, key=event['metadata']['correlation_id'],
                              value=json.dumps(event).encode('utf-8'),
                              on_delivery=lambda error, message: errors.append(error) if error else None)
        if self.producer.flush(10) or errors:
            raise RuntimeError('Kafka delivery not acknowledged; offset will not be committed')

    def handle(self, topic, event):
        metadata, payload = event['metadata'], event['payload']
        event_id, trip_id = metadata['event_id'], payload['trip_id']
        if not isinstance(event_id, str) or not event_id or not isinstance(trip_id, str) or not trip_id:
            raise ValueError('Missing event/trip ID')
        if metadata['correlation_id'] != trip_id:
            raise ValueError('Correlation ID differs from trip ID')
        # FIX: terminal events release ONLY the reservation owned by this trip.
        if topic in ('trip.completed', 'trip.cancelled'):
            count = finish_trip(self.db, trip_id, 'COMPLETED' if topic == 'trip.completed' else 'CANCELED')
            logging.info('RELEASE | trip=%s released=%s', trip_id, count)
            return
        if topic != 'trip.requested' or finished(self.db, trip_id):
            return
        cached = self.db['MatchingResults'].find_one({'_id': trip_id})
        if cached:
            self.publish(cached['topic'], cached['event'])
            return
        # Keep compatibility with events already processed by the pre-fix worker.
        if self.db['ProcessedTrips'].find_one({'_id': event_id}):
            return
        lat, lng = payload['pickup_lat'], payload['pickup_long']
        # A crash after reservation but before publishing can reuse the same lock.
        best = self.drivers.find_one({'status': 'BUSY', 'active_trip_id': trip_id})
        def distance(driver):
            coordinates = driver['location']['coordinates']
            return (abs(coordinates[0] - lng) + abs(coordinates[1] - lat)) * 111000
        if best is None:
            candidates = list(self.drivers.find({'status': 'AVAILABLE', 'location': {'$near': {
                '$geometry': {'type': 'Point', 'coordinates': [lng, lat]}, '$maxDistance': 3000}}}).limit(5))
            # Same ETA ranking as before; reserve only the best available candidate.
            for driver in sorted(candidates, key=distance):
                best = self.drivers.find_one_and_update(
                    {'driver_id': driver['driver_id'], 'status': 'AVAILABLE'},
                    {'$set': {'status': 'BUSY', 'active_trip_id': trip_id}})
                if best is not None:
                    break
        # A cancellation can be processed by another worker during selection.
        if finished(self.db, trip_id):
            finish_trip(self.db, trip_id, 'CANCELED')
            return
        if best is not None:
            meters = distance(best)
            output_topic, event_type = 'driver.matched', 'DRIVER_MATCHED'
            output = {'trip_id': trip_id, 'driver_id': str(best['driver_id']),
                      'distance_to_pickup_km': round(meters / 1000, 2),
                      'estimated_time_arrival_mins': int(((meters / 9.7) + 45) // 60),
                      'destination_lat': payload.get('destination_lat'),
                      'destination_long': payload.get('destination_long')}
        else:
            output_topic, event_type = 'matching.failed', 'MATCHING_FAILED'
            output = {'trip_id': trip_id, 'reason': 'TIMEOUT_NO_DRIVERS'}
        result = {'metadata': {'event_id': uuid.uuid4().hex, 'correlation_id': trip_id,
                              'event_type': event_type, 'timestamp': datetime.utcnow().isoformat() + 'Z',
                              'source': 'matching-service'}, 'payload': output}
        # Persist output before publish; retries replay the same event ID.
        self.db['MatchingResults'].update_one({'_id': trip_id}, {'$setOnInsert': {
            'topic': output_topic, 'event': result}}, upsert=True)
        cached = self.db['MatchingResults'].find_one({'_id': trip_id})
        self.publish(cached['topic'], cached['event'])
        self.db['ProcessedTrips'].update_one({'_id': event_id}, {'$setOnInsert': {
            'processed_at': datetime.utcnow()}}, upsert=True)
        logging.info('%s | trip=%s driver=%s', event_type, trip_id, output.get('driver_id'))


def main():
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
    db = client['RideHailingDB']
    db['LiveLocations'].create_index([('location', '2dsphere')])
    db['LiveLocations'].create_index('driver_id', unique=True)
    db['LiveLocations'].create_index('active_trip_id', unique=True, sparse=True)
    broker = os.getenv('KAFKA_BROKER', '127.0.0.1:9092')
    # Existing committed trip.requested offsets are preserved by the same group.
    consumer = Consumer({'bootstrap.servers': broker, 'group.id': 'matching_group_v2',
                         'auto.offset.reset': 'earliest', 'enable.auto.commit': False})
    consumer.subscribe(['trip.requested', 'trip.completed', 'trip.cancelled'])
    matcher = Matcher(db, Producer({'bootstrap.servers': broker}))
    last_reconcile = 0
    logging.info('Matching ready: requested/completed/cancelled; trip-owned reservations')
    try:
        while True:
            if time.monotonic() - last_reconcile >= 15:
                last_reconcile = time.monotonic()
                try:
                    if db['LiveLocations'].find_one({'status': 'BUSY', 'active_trip_id': {'$exists': True}}):
                        response = requests.get(os.getenv('BOOKING_SERVICE_URL', 'http://localhost:8080') + '/api/trips', timeout=5)
                        response.raise_for_status()
                        count = reconcile(db, response.json())
                        if count:
                            logging.info('RECONCILE | released=%s', count)
                except Exception as error:
                    logging.warning('Reconcile deferred: %s', error)
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            try:
                matcher.handle(msg.topic(), json.loads(msg.value().decode('utf-8')))
            except (ValueError, KeyError, TypeError, UnicodeDecodeError) as error:
                logging.error('Invalid event skipped on %s: %s', msg.topic(), error)
            # Database/Kafka errors escape and restart the worker with uncommitted offset.
            consumer.commit(message=msg, asynchronous=False)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        client.close()


if __name__ == '__main__':
    main()

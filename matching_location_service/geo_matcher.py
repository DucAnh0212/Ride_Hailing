import os
import json
import signal
import uuid
import time
import logging
from datetime import datetime
import requests
from confluent_kafka import Consumer, Producer
from pymongo import MongoClient
from dotenv import load_dotenv
from driver_lifecycle import LocationClient, finished, finish_trip, reconcile

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | NODE: Matching-Worker | %(levelname)s | %(message)s')


class Matcher:
    def __init__(self, db, producer, location_client):
        self.db = db
        self.producer = producer
        self.location_client = location_client

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
        # Terminal events release ONLY the reservation owned by this trip.
        if topic in ('trip.completed', 'trip.cancelled'):
            count = finish_trip(self.db, self.location_client, trip_id,
                                'COMPLETED' if topic == 'trip.completed' else 'CANCELED')
            logging.info('RELEASE | trip=%s released=%s', trip_id, count)
            return
        if topic != 'trip.requested' or finished(self.db, trip_id):
            return
        cached = self.db['MatchingResults'].find_one({'_id': trip_id})
        if cached:
            self.publish(cached['topic'], cached['event'])
            return
        if self.db['ProcessedTrips'].find_one({'_id': event_id}):
            return
        lat, lng = payload['pickup_lat'], payload['pickup_long']
        reservation = self.location_client.reserve(trip_id, lat, lng, max_distance_m=3000, limit=5)
        # A cancellation can be processed by another worker during selection.
        if finished(self.db, trip_id):
            finish_trip(self.db, self.location_client, trip_id, 'CANCELED')
            return
        if reservation.get('matched'):
            output_topic, event_type = 'driver.matched', 'DRIVER_MATCHED'
            output = {
                'trip_id': trip_id,
                'driver_id': str(reservation['driver_id']),
                'distance_to_pickup_km': reservation['distance_to_pickup_km'],
                'estimated_time_arrival_mins': reservation['estimated_time_arrival_mins'],
                'destination_lat': payload.get('destination_lat'),
                'destination_long': payload.get('destination_long'),
            }
        else:
            output_topic, event_type = 'matching.failed', 'MATCHING_FAILED'
            output = {'trip_id': trip_id, 'reason': 'TIMEOUT_NO_DRIVERS'}
        result = {
            'metadata': {
                'event_id': uuid.uuid4().hex,
                'correlation_id': trip_id,
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'source': 'matching-service',
            },
            'payload': output,
        }
        # Persist output before publish; retries replay the same event ID.
        self.db['MatchingResults'].update_one(
            {'_id': trip_id},
            {'$setOnInsert': {'topic': output_topic, 'event': result}},
            upsert=True,
        )
        cached = self.db['MatchingResults'].find_one({'_id': trip_id})
        self.publish(cached['topic'], cached['event'])
        self.db['ProcessedTrips'].update_one(
            {'_id': event_id},
            {'$setOnInsert': {'processed_at': datetime.utcnow()}},
            upsert=True,
        )
        logging.info('%s | trip=%s driver=%s', event_type, trip_id, output.get('driver_id'))


def main():
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017/'))
    mongo_db = os.getenv('MONGO_DB', 'MatchingDB')
    db = client[mongo_db]
    location_url = os.getenv('LOCATION_SERVICE_URL', 'http://localhost:8000')
    location_client = LocationClient(location_url)
    broker = os.getenv('KAFKA_BROKER', '127.0.0.1:9092')
    consumer = Consumer({
        'bootstrap.servers': broker,
        'group.id': 'matching_group_v2',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
        'allow.auto.create.topics': True,
        'topic.metadata.refresh.interval.ms': 5000,
        'session.timeout.ms': 10000,
        'heartbeat.interval.ms': 3000,
    })
    consumer.subscribe(['trip.requested', 'trip.completed', 'trip.cancelled'])
    matcher = Matcher(db, Producer({'bootstrap.servers': broker}), location_client)
    last_reconcile = 0
    running = True

    def _stop(signum, _frame):
        nonlocal running
        logging.info('Received signal %s; shutting down cleanly to leave Kafka group...', signum)
        running = False

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logging.info('Matching ready: db=%s location=%s', mongo_db, location_url)
    try:
        while running:
            if time.monotonic() - last_reconcile >= 15:
                last_reconcile = time.monotonic()
                try:
                    busy = location_client.list_busy()
                    if busy:
                        response = requests.get(
                            os.getenv('BOOKING_SERVICE_URL', 'http://localhost:8080') + '/api/trips',
                            timeout=5,
                        )
                        response.raise_for_status()
                        count = reconcile(db, location_client, response.json())
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
            # Database/Kafka/HTTP errors escape and restart the worker with uncommitted offset.
            consumer.commit(message=msg, asynchronous=False)
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        client.close()


if __name__ == '__main__':
    main()

package com.uber.booking.services;

import com.uber.booking.events.TripCancelledEvent;
import com.uber.booking.events.TripCompletedEvent;
import com.uber.booking.events.TripRequestedEvent;
import com.uber.booking.events.TripStartedEvent;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.logging.Logger;

@Service
public class KafkaProducerService {

    private static final Logger LOGGER = Logger.getLogger(KafkaProducerService.class.getName());

    public static final String TOPIC_TRIP_REQUESTED = "trip.requested";
    public static final String TOPIC_TRIP_STARTED = "trip.started";
    public static final String TOPIC_TRIP_COMPLETED = "trip.completed";
    public static final String TOPIC_TRIP_CANCELLED = "trip.cancelled";

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    public void sendTripRequestedEvent(TripRequestedEvent event) {
        LOGGER.info(String.format("Sending %s event for trip: %s", TOPIC_TRIP_REQUESTED, event.getPayload().getTrip_id()));
        kafkaTemplate.send(TOPIC_TRIP_REQUESTED, event.getMetadata().getCorrelation_id(), event);
    }

    public void sendTripStartedEvent(TripStartedEvent event) {
        LOGGER.info(String.format("Sending %s event for trip: %s", TOPIC_TRIP_STARTED, event.getPayload().getTrip_id()));
        kafkaTemplate.send(TOPIC_TRIP_STARTED, event.getMetadata().getCorrelation_id(), event);
    }

    public void sendTripCompletedEvent(TripCompletedEvent event) {
        LOGGER.info(String.format("Sending %s event for trip: %s", TOPIC_TRIP_COMPLETED, event.getPayload().getTrip_id()));
        kafkaTemplate.send(TOPIC_TRIP_COMPLETED, event.getMetadata().getCorrelation_id(), event);
    }

    public void sendTripCancelledEvent(TripCancelledEvent event) {
        LOGGER.info(String.format("Sending %s event for trip: %s", TOPIC_TRIP_CANCELLED, event.getPayload().getTrip_id()));
        kafkaTemplate.send(TOPIC_TRIP_CANCELLED, event.getMetadata().getCorrelation_id(), event);
    }
}

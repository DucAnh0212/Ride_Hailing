package com.uber.booking.services;

import com.uber.booking.events.TripRequestedEvent;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.logging.Logger;

@Service
public class KafkaProducerService {

    private static final Logger LOGGER = Logger.getLogger(KafkaProducerService.class.getName());
    private static final String TOPIC = "trip.requested";

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    public void sendTripRequestedEvent(TripRequestedEvent event) {
        LOGGER.info(String.format("Sending trip.requested event for trip: %s", event.getPayload().getTrip_id()));
        kafkaTemplate.send(TOPIC, event.getMetadata().getCorrelation_id(), event);
    }
}

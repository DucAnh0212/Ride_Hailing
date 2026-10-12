package com.uber.booking.services;

import com.uber.booking.events.DriverMatchedEvent;
import com.uber.booking.events.MatchingFailedEvent;
import com.uber.booking.models.IdempotencyLog;
import com.uber.booking.models.Trip;
import com.uber.booking.repositories.IdempotencyLogRepository;
import com.uber.booking.repositories.TripRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.logging.Logger;

@Service
public class KafkaConsumerService {

    private static final Logger LOGGER = Logger.getLogger(KafkaConsumerService.class.getName());

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private IdempotencyLogRepository idempotencyLogRepository;

    @KafkaListener(topics = "driver.matched", groupId = "booking-group")
    @Transactional
    public void consumeDriverMatchedEvent(DriverMatchedEvent event) {
        String eventId = event.getMetadata().getEvent_id();
        
        // 1. Check Idempotency
        if (idempotencyLogRepository.existsById(eventId)) {
            LOGGER.info("Duplicate event ignored: " + eventId);
            return;
        }

        LOGGER.info("Processing DriverMatchedEvent for trip: " + event.getPayload().getTrip_id());

        // 2. Process Business Logic
        String tripId = event.getPayload().getTrip_id();
        Optional<Trip> optionalTrip = tripRepository.findById(tripId);
        
        if (optionalTrip.isPresent()) {
            Trip trip = optionalTrip.get();
            if ("PENDING".equals(trip.getStatus())) {
                trip.setStatus("ACCEPTED");
                trip.setDriverId(event.getPayload().getDriver_id());
                tripRepository.save(trip);
                LOGGER.info("Trip " + tripId + " updated to ACCEPTED.");
            }
        } else {
            LOGGER.warning("Trip not found: " + tripId);
        }

        // 3. Save Idempotency Log
        IdempotencyLog log = IdempotencyLog.builder()
                .eventId(eventId)
                .eventType(event.getMetadata().getEvent_type())
                .processedAt(LocalDateTime.now())
                .build();
        idempotencyLogRepository.save(log);
    }
    
    @KafkaListener(topics = "matching.failed", groupId = "booking-group")
    @Transactional
    public void consumeMatchingFailedEvent(MatchingFailedEvent event) {
        String eventId = event.getMetadata().getEvent_id();
        
        // 1. Check Idempotency
        if (idempotencyLogRepository.existsById(eventId)) {
            LOGGER.info("Duplicate event ignored: " + eventId);
            return;
        }

        LOGGER.info("Processing MatchingFailedEvent for trip: " + event.getPayload().getTrip_id());

        // 2. Process Business Logic
        String tripId = event.getPayload().getTrip_id();
        Optional<Trip> optionalTrip = tripRepository.findById(tripId);
        
        if (optionalTrip.isPresent()) {
            Trip trip = optionalTrip.get();
            if ("PENDING".equals(trip.getStatus())) {
                trip.setStatus("CANCELED");
                trip.setCancelReason(event.getPayload().getReason());
                tripRepository.save(trip);
                LOGGER.info("Trip " + tripId + " updated to CANCELED.");
            }
        } else {
            LOGGER.warning("Trip not found: " + tripId);
        }

        // 3. Save Idempotency Log
        IdempotencyLog log = IdempotencyLog.builder()
                .eventId(eventId)
                .eventType(event.getMetadata().getEvent_type())
                .processedAt(LocalDateTime.now())
                .build();
        idempotencyLogRepository.save(log);
    }
}

package com.uber.booking.services;

import com.uber.booking.events.DriverMatchedEvent;
import com.uber.booking.events.MatchingFailedEvent;
import com.uber.booking.events.TripCancelledEvent;
import com.uber.booking.events.TripRequestedEvent;
import com.uber.booking.models.IdempotencyLog;
import com.uber.booking.models.Trip;
import com.uber.booking.repositories.IdempotencyLogRepository;
import com.uber.booking.repositories.TripRepository;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;
import java.util.logging.Logger;

@Service
public class KafkaConsumerService {

    private static final Logger LOGGER = Logger.getLogger(KafkaConsumerService.class.getName());

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private IdempotencyLogRepository idempotencyLogRepository;

    @Autowired
    private KafkaProducerService kafkaProducerService;

    @KafkaListener(topics = "driver.matched", groupId = "booking-group")
    @Transactional
    public void consumeDriverMatchedEvent(DriverMatchedEvent event) {
        String eventId = event.getMetadata().getEvent_id();
        
        // 1. Kiểm tra tính lũy đẳng (Idempotency)
        if (idempotencyLogRepository.existsById(eventId)) {
            LOGGER.info("Duplicate event ignored: " + eventId);
            return;
        }

        LOGGER.info("Processing DriverMatchedEvent for trip: " + event.getPayload().getTrip_id());

        // 2. Cập nhật trạng thái chuyến đi sang ACCEPTED
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

        // 3. Lưu log Idempotency
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
        
        // 1. Kiểm tra tính lũy đẳng (Idempotency)
        if (idempotencyLogRepository.existsById(eventId)) {
            LOGGER.info("Duplicate event ignored: " + eventId);
            return;
        }

        LOGGER.info("Processing MatchingFailedEvent for trip: " + event.getPayload().getTrip_id());

        // 2. Kích hoạt giao dịch bù trừ Saga (Compensating Transaction): Hủy cuốc
        String tripId = event.getPayload().getTrip_id();
        Optional<Trip> optionalTrip = tripRepository.findById(tripId);
        
        if (optionalTrip.isPresent()) {
            Trip trip = optionalTrip.get();
            if ("PENDING".equals(trip.getStatus())) {
                trip.setStatus("CANCELED");
                trip.setCancelReason(event.getPayload().getReason());
                tripRepository.save(trip);
                LOGGER.info("Saga Compensating Action: Trip " + tripId + " updated to CANCELED due to " + event.getPayload().getReason());

                // Bắn sự kiện bù trừ sang Kafka thông báo các dịch vụ khác
                TripRequestedEvent.EventMetadata cancelMetadata = TripRequestedEvent.EventMetadata.builder()
                        .event_id("can_" + UUID.randomUUID().toString().substring(0, 8))
                        .correlation_id(tripId)
                        .event_type("TRIP_CANCELLED")
                        .timestamp(LocalDateTime.now().toString())
                        .source("booking-service")
                        .build();

                TripCancelledEvent.Payload cancelPayload = TripCancelledEvent.Payload.builder()
                        .trip_id(tripId)
                        .passenger_id(trip.getPassengerId())
                        .driver_id(trip.getDriverId())
                        .cancel_reason(event.getPayload().getReason())
                        .cancelled_at(LocalDateTime.now())
                        .build();

                kafkaProducerService.sendTripCancelledEvent(new TripCancelledEvent(cancelMetadata, cancelPayload));
            }
        } else {
            LOGGER.warning("Trip not found: " + tripId);
        }

        // 3. Lưu log Idempotency
        IdempotencyLog log = IdempotencyLog.builder()
                .eventId(eventId)
                .eventType(event.getMetadata().getEvent_type())
                .processedAt(LocalDateTime.now())
                .build();
        idempotencyLogRepository.save(log);
    }

    /**
     * Lắng nghe Dead Letter Queue (DLQ / DLT) để giám sát các gói tin lỗi
     */
    @KafkaListener(topics = {"driver.matched.DLT", "matching.failed.DLT"}, groupId = "booking-dlq-group")
    public void consumeDeadLetterQueue(ConsumerRecord<String, Object> record) {
        LOGGER.severe(String.format("🚨 [DEAD LETTER QUEUE] Phát hiện gói tin lỗi từ topic [%s] | Key: %s | Nội dung: %s",
                record.topic(), record.key(), record.value()));
    }
}

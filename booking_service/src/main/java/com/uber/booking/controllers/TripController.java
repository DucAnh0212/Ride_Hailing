package com.uber.booking.controllers;

import com.uber.booking.dto.TripCancelDTO;
import com.uber.booking.dto.TripRequestDTO;
import com.uber.booking.events.TripCancelledEvent;
import com.uber.booking.events.TripCompletedEvent;
import com.uber.booking.events.TripRequestedEvent;
import com.uber.booking.events.TripStartedEvent;
import com.uber.booking.models.Trip;
import com.uber.booking.repositories.TripRepository;
import com.uber.booking.services.FareCalculationService;
import com.uber.booking.services.KafkaProducerService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.OptimisticLockingFailureException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/trips")
public class TripController {

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private KafkaProducerService kafkaProducerService;

    @Autowired
    private FareCalculationService fareCalculationService;

    @GetMapping
    public List<Trip> getAllTrips() {
        return tripRepository.findAll();
    }

    @GetMapping("/pending")
    public List<Trip> getPendingTrips() {
        return tripRepository.findByStatus("PENDING");
    }

    @GetMapping("/{tripId}")
    public ResponseEntity<?> getTripById(@PathVariable String tripId) {
        return tripRepository.findById(tripId)
                .<ResponseEntity<?>>map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.status(HttpStatus.NOT_FOUND)
                        .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId)));
    }

    @PostMapping
    public Trip createTrip(@RequestBody TripRequestDTO request) {
        Trip trip = new Trip();
        trip.setTripId("trip_" + UUID.randomUUID().toString().substring(0, 8));
        trip.setPassengerId(request.getPassengerId());
        trip.setPickupLat(request.getPickupLat());
        trip.setPickupLong(request.getPickupLong());
        trip.setDestLat(request.getDestLat());
        trip.setDestLong(request.getDestLong());
        
        trip.setStatus("PENDING");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        
        Trip savedTrip = tripRepository.save(trip);
        
        // Tạo Kafka Event
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("req_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(savedTrip.getTripId())
                .event_type("TRIP_REQUESTED")
                .timestamp(LocalDateTime.now().toString())
                .source("booking-service")
                .build();
                
        TripRequestedEvent.Payload payload = TripRequestedEvent.Payload.builder()
                .trip_id(savedTrip.getTripId())
                .passenger_id(savedTrip.getPassengerId())
                .pickup_lat(savedTrip.getPickupLat())
                .pickup_long(savedTrip.getPickupLong())
                .destination_lat(savedTrip.getDestLat())
                .destination_long(savedTrip.getDestLong())
                .vehicle_type(request.getVehicleType())
                .build();
                
        TripRequestedEvent event = new TripRequestedEvent(metadata, payload);
        kafkaProducerService.sendTripRequestedEvent(event);
        
        return savedTrip;
    }

    /**
     * Tài xế bắt đầu chuyến đi (ACCEPTED -> STARTED)
     */
    @PutMapping("/{tripId}/start")
    public ResponseEntity<?> startTrip(@PathVariable String tripId) {
        Trip trip = tripRepository.findById(tripId).orElse(null);
        if (trip == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId));
        }

        if (!"ACCEPTED".equals(trip.getStatus())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Chuyến đi phải ở trạng thái ACCEPTED mới có thể bắt đầu. Trạng thái hiện tại: " + trip.getStatus()));
        }

        trip.setStatus("STARTED");
        Trip updatedTrip = tripRepository.save(trip);

        // Bắn sự kiện trip.started
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("sta_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_STARTED")
                .timestamp(LocalDateTime.now().toString())
                .source("booking-service")
                .build();

        TripStartedEvent.Payload payload = TripStartedEvent.Payload.builder()
                .trip_id(tripId)
                .driver_id(trip.getDriverId())
                .passenger_id(trip.getPassengerId())
                .started_at(LocalDateTime.now())
                .build();

        kafkaProducerService.sendTripStartedEvent(new TripStartedEvent(metadata, payload));

        return ResponseEntity.ok(updatedTrip);
    }

    /**
     * Tài xế kết thúc chuyến đi (STARTED/ACCEPTED -> COMPLETED)
     * Tính cước phí tự động và mô phỏng thanh toán
     */
    @PutMapping("/{tripId}/complete")
    public ResponseEntity<?> completeTrip(@PathVariable String tripId) {
        Trip trip = tripRepository.findById(tripId).orElse(null);
        if (trip == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId));
        }

        if (!"STARTED".equals(trip.getStatus()) && !"ACCEPTED".equals(trip.getStatus())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Không thể hoàn thành chuyến đi ở trạng thái: " + trip.getStatus()));
        }

        // Tính cước phí Haversine
        BigDecimal fare = fareCalculationService.calculateFare(
                trip.getPickupLat(), trip.getPickupLong(),
                trip.getDestLat(), trip.getDestLong()
        );

        trip.setStatus("COMPLETED");
        trip.setFareAmount(fare);
        trip.setPaymentStatus("PAID_SIMULATED"); // Mô phỏng thanh toán hoàn tất
        Trip updatedTrip = tripRepository.save(trip);

        // Bắn sự kiện trip.completed
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("com_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_COMPLETED")
                .timestamp(LocalDateTime.now().toString())
                .source("booking-service")
                .build();

        TripCompletedEvent.Payload payload = TripCompletedEvent.Payload.builder()
                .trip_id(tripId)
                .driver_id(trip.getDriverId())
                .passenger_id(trip.getPassengerId())
                .fare_amount(fare)
                .payment_status("PAID_SIMULATED")
                .completed_at(LocalDateTime.now())
                .build();

        kafkaProducerService.sendTripCompletedEvent(new TripCompletedEvent(metadata, payload));

        return ResponseEntity.ok(updatedTrip);
    }

    /**
     * Hủy chuyến đi (PENDING, ACCEPTED, STARTED -> CANCELED)
     * Kích hoạt giao dịch bù trừ Saga
     */
    @PutMapping("/{tripId}/cancel")
    public ResponseEntity<?> cancelTrip(@PathVariable String tripId, @RequestBody(required = false) TripCancelDTO cancelDTO) {
        Trip trip = tripRepository.findById(tripId).orElse(null);
        if (trip == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId));
        }

        if ("COMPLETED".equals(trip.getStatus())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Không thể hủy chuyến đi đã hoàn thành"));
        }

        if ("CANCELED".equals(trip.getStatus())) {
            return ResponseEntity.ok(trip); // Idempotent cancel
        }

        String reason = (cancelDTO != null && cancelDTO.getReason() != null)
                ? cancelDTO.getReason()
                : "PASSENGER_CANCELED";

        trip.setStatus("CANCELED");
        trip.setCancelReason(reason);
        Trip updatedTrip = tripRepository.save(trip);

        // Bắn sự kiện trip.cancelled (Giao dịch bù trừ)
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("can_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_CANCELLED")
                .timestamp(LocalDateTime.now().toString())
                .source("booking-service")
                .build();

        TripCancelledEvent.Payload payload = TripCancelledEvent.Payload.builder()
                .trip_id(tripId)
                .passenger_id(trip.getPassengerId())
                .driver_id(trip.getDriverId())
                .cancel_reason(reason)
                .cancelled_at(LocalDateTime.now())
                .build();

        kafkaProducerService.sendTripCancelledEvent(new TripCancelledEvent(metadata, payload));

        return ResponseEntity.ok(updatedTrip);
    }

    /**
     * Bắt ngoại lệ xung đột đồng thời (Optimistic Locking) khi 2 thao tác tranh chấp cùng 1 record
     */
    @ExceptionHandler(OptimisticLockingFailureException.class)
    public ResponseEntity<?> handleOptimisticLockingFailure(OptimisticLockingFailureException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                "error", "OPTIMISTIC_LOCKING_CONFLICT",
                "message", "Dữ liệu chuyến đi vừa bị cập nhật bởi một giao dịch khác. Vui lòng tải lại và thử lại!"
        ));
    }
}

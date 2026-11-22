package com.uber.booking.controllers;

import com.uber.booking.dto.TripCancelDTO;
import com.uber.booking.dto.TripRequestDTO;
import com.uber.booking.events.TripAcceptedEvent;
import com.uber.booking.events.TripCancelledEvent;
import com.uber.booking.events.TripCompletedEvent;
import com.uber.booking.events.TripRejectedEvent;
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

    private static boolean invalidCoordinate(Double lat, Double lng) {
        return lat == null || lng == null || !Double.isFinite(lat) || !Double.isFinite(lng)
                || Math.abs(lat) > 90.0 || Math.abs(lng) > 180.0;
    }

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
    public ResponseEntity<?> createTrip(@RequestBody TripRequestDTO request) {
        if (request == null || request.getPassengerId() == null || request.getPassengerId().isBlank()
                || invalidCoordinate(request.getPickupLat(), request.getPickupLong())
                || invalidCoordinate(request.getDestLat(), request.getDestLong())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Thông tin chuyến đi hoặc tọa độ không hợp lệ"));
        }
        if (request.getPickupLat().equals(request.getDestLat())
                && request.getPickupLong().equals(request.getDestLong())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Điểm đón và điểm đến phải khác nhau"));
        }

        Trip trip = new Trip();
        trip.setTripId("trip_" + UUID.randomUUID().toString().substring(0, 8));
        trip.setPassengerId(request.getPassengerId());
        trip.setPickupLat(request.getPickupLat());
        trip.setPickupLong(request.getPickupLong());
        trip.setDestLat(request.getDestLat());
        trip.setDestLong(request.getDestLong());

        trip.setStatus("PENDING");
        trip.setFareAmount(fareCalculationService.calculateFare(
                request.getPickupLat(), request.getPickupLong(),
                request.getDestLat(), request.getDestLong()
        ));
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);

        Trip savedTrip = tripRepository.save(trip);

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

        kafkaProducerService.sendTripRequestedEvent(new TripRequestedEvent(metadata, payload));
        return ResponseEntity.ok(savedTrip);
    }

    /**
     * Tài xế chấp nhận chuyến đi được ghép (MATCHED -> ACCEPTED)
     */
    @PutMapping("/{tripId}/accept")
    public ResponseEntity<?> acceptTrip(@PathVariable String tripId) {
        Trip trip = tripRepository.findById(tripId).orElse(null);
        if (trip == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId));
        }

        if (!"MATCHED".equals(trip.getStatus())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Chuyến đi phải ở trạng thái MATCHED mới có thể chấp nhận. Trạng thái hiện tại: " + trip.getStatus()));
        }

        trip.setStatus("ACCEPTED");
        Trip updatedTrip = tripRepository.save(trip);

        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("acc_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_ACCEPTED")
                .timestamp(LocalDateTime.now().toString())
                .source("booking-service")
                .build();

        TripAcceptedEvent.Payload payload = TripAcceptedEvent.Payload.builder()
                .trip_id(tripId)
                .driver_id(trip.getDriverId())
                .passenger_id(trip.getPassengerId())
                .accepted_at(LocalDateTime.now())
                .build();

        kafkaProducerService.sendTripAcceptedEvent(new TripAcceptedEvent(metadata, payload));
        return ResponseEntity.ok(updatedTrip);
    }

    /**
     * Tài xế từ chối chuyến đi được ghép (MATCHED -> CANCELED + Saga giải phóng tài xế)
     */
    @PutMapping("/{tripId}/reject")
    public ResponseEntity<?> rejectTrip(@PathVariable String tripId, @RequestBody(required = false) TripCancelDTO rejectDTO) {
        Trip trip = tripRepository.findById(tripId).orElse(null);
        if (trip == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("message", "Không tìm thấy chuyến đi: " + tripId));
        }

        if (!"MATCHED".equals(trip.getStatus())) {
            return ResponseEntity.badRequest()
                    .body(Map.of("message", "Chỉ có thể từ chối chuyến đi ở trạng thái MATCHED. Trạng thái hiện tại: " + trip.getStatus()));
        }

        String reason = (rejectDTO != null && rejectDTO.getReason() != null && !rejectDTO.getReason().isBlank())
                ? rejectDTO.getReason()
                : "DRIVER_REJECTED";

        trip.setStatus("CANCELED");
        trip.setCancelReason(reason);
        Trip updatedTrip = tripRepository.save(trip);

        LocalDateTime now = LocalDateTime.now();

        TripRequestedEvent.EventMetadata rejectMetadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("rej_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_REJECTED")
                .timestamp(now.toString())
                .source("booking-service")
                .build();

        TripRejectedEvent.Payload rejectPayload = TripRejectedEvent.Payload.builder()
                .trip_id(tripId)
                .driver_id(trip.getDriverId())
                .passenger_id(trip.getPassengerId())
                .reason(reason)
                .rejected_at(now)
                .build();
        kafkaProducerService.sendTripRejectedEvent(new TripRejectedEvent(rejectMetadata, rejectPayload));

        // Giao dịch bù trừ Saga: thông báo Matching giải phóng tài xế về AVAILABLE
        TripRequestedEvent.EventMetadata cancelMetadata = TripRequestedEvent.EventMetadata.builder()
                .event_id("can_" + UUID.randomUUID().toString().substring(0, 8))
                .correlation_id(tripId)
                .event_type("TRIP_CANCELLED")
                .timestamp(now.toString())
                .source("booking-service")
                .build();

        TripCancelledEvent.Payload cancelPayload = TripCancelledEvent.Payload.builder()
                .trip_id(tripId)
                .passenger_id(trip.getPassengerId())
                .driver_id(trip.getDriverId())
                .cancel_reason(reason)
                .cancelled_at(now)
                .build();
        kafkaProducerService.sendTripCancelledEvent(new TripCancelledEvent(cancelMetadata, cancelPayload));

        return ResponseEntity.ok(updatedTrip);
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

        BigDecimal fare = fareCalculationService.calculateFare(
                trip.getPickupLat(), trip.getPickupLong(),
                trip.getDestLat(), trip.getDestLong()
        );

        trip.setStatus("COMPLETED");
        trip.setFareAmount(fare);
        trip.setPaymentStatus("PAID_SIMULATED");
        Trip updatedTrip = tripRepository.save(trip);

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
     * Hủy chuyến đi (PENDING, MATCHED, ACCEPTED, STARTED -> CANCELED)
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
            return ResponseEntity.ok(trip);
        }

        String reason = (cancelDTO != null && cancelDTO.getReason() != null && !cancelDTO.getReason().isBlank())
                ? cancelDTO.getReason()
                : "PASSENGER_CANCELED";

        trip.setStatus("CANCELED");
        trip.setCancelReason(reason);
        Trip updatedTrip = tripRepository.save(trip);

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

    @ExceptionHandler(OptimisticLockingFailureException.class)
    public ResponseEntity<?> handleOptimisticLockingFailure(OptimisticLockingFailureException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT).body(Map.of(
                "error", "OPTIMISTIC_LOCKING_CONFLICT",
                "message", "Dữ liệu chuyến đi vừa bị cập nhật bởi một giao dịch khác. Vui lòng tải lại và thử lại!"
        ));
    }
}

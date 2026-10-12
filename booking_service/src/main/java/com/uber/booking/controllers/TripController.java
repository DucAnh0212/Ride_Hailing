package com.uber.booking.controllers;

import com.uber.booking.models.Trip;
import com.uber.booking.repositories.TripRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.uber.booking.dto.TripRequestDTO;
import com.uber.booking.events.TripRequestedEvent;
import com.uber.booking.services.KafkaProducerService;

import java.time.LocalDateTime;
import java.util.UUID;
import java.util.List;

@RestController
@RequestMapping("/api/trips")
public class TripController {

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private KafkaProducerService kafkaProducerService;

    @GetMapping
    public List<Trip> getAllTrips() {
        return tripRepository.findAll();
    }

    @GetMapping("/pending")
    public List<Trip> getPendingTrips() {
        return tripRepository.findByStatus("PENDING");
    }

    @PostMapping
    public Trip createTrip(@RequestBody TripRequestDTO request) {
        Trip trip = new Trip();
        // Tạo mã chuyến đi ngẫu nhiên (VD: trip_a1b2c3d4)
        trip.setTripId("trip_" + UUID.randomUUID().toString().substring(0, 8));
        trip.setPassengerId(request.getPassengerId());
        trip.setPickupLat(request.getPickupLat());
        trip.setPickupLong(request.getPickupLong());
        trip.setDestLat(request.getDestLat());
        trip.setDestLong(request.getDestLong());
        
        // Thiết lập các trạng thái mặc định khi mới đặt xe
        trip.setStatus("PENDING");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        
        // Lưu vào SQL Server
        Trip savedTrip = tripRepository.save(trip);
        
        // Tạo Kafka Event (gói tin)
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
        
        // Bắn gói tin lên Kafka
        kafkaProducerService.sendTripRequestedEvent(event);
        
        return savedTrip;
    }
}

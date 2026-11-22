package com.uber.booking;

import com.uber.booking.dto.TripCancelDTO;
import com.uber.booking.dto.TripRequestDTO;
import com.uber.booking.events.DriverMatchedEvent;
import com.uber.booking.events.MatchingFailedEvent;
import com.uber.booking.events.TripRequestedEvent;
import com.uber.booking.models.Trip;
import com.uber.booking.repositories.IdempotencyLogRepository;
import com.uber.booking.repositories.TripRepository;
import com.uber.booking.services.FareCalculationService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.kafka.core.KafkaTemplate;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class BookingServiceApplicationTests {

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private TripRepository tripRepository;

    @Autowired
    private IdempotencyLogRepository idempotencyLogRepository;

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    @Autowired
    private FareCalculationService fareCalculationService;

    @Test
    void testCreateBookingApi() {
        TripRequestDTO request = new TripRequestDTO();
        request.setPassengerId("usr_" + UUID.randomUUID().toString().substring(0, 6));
        request.setPickupLat(10.762622);
        request.setPickupLong(106.660172);
        request.setDestLat(10.775620);
        request.setDestLong(106.700420);
        request.setVehicleType("MOTORBIKE");

        ResponseEntity<Trip> response = restTemplate.postForEntity("/api/trips", request, Trip.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().getStatus()).isEqualTo("PENDING");
    }

    @Test
    void testDriverMatchedConsumerTransitionsToMatched() throws InterruptedException {
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        Trip trip = new Trip();
        trip.setTripId("trip_mat_" + randomId);
        trip.setPassengerId("usr_" + randomId);
        trip.setPickupLat(10.762622);
        trip.setPickupLong(106.660172);
        trip.setDestLat(10.775620);
        trip.setDestLong(106.700420);
        trip.setStatus("PENDING");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        String eventId = "evt_mat_" + randomId;
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id(eventId)
                .correlation_id(trip.getTripId())
                .event_type("DRIVER_MATCHED")
                .timestamp(LocalDateTime.now().toString())
                .source("matching-service")
                .build();
        DriverMatchedEvent.Payload payload = DriverMatchedEvent.Payload.builder()
                .trip_id(trip.getTripId())
                .driver_id("drv_" + randomId)
                .distance_to_pickup_km(1.2)
                .estimated_time_arrival_mins(4)
                .build();

        kafkaTemplate.send("driver.matched", trip.getTripId(), new DriverMatchedEvent(metadata, payload));

        Trip updatedTrip = null;
        for (int i = 0; i < 15; i++) {
            Thread.sleep(1000);
            updatedTrip = tripRepository.findById(trip.getTripId()).orElse(null);
            if (updatedTrip != null && "MATCHED".equals(updatedTrip.getStatus())) {
                break;
            }
        }

        assertThat(updatedTrip).isNotNull();
        assertThat(updatedTrip.getStatus()).isEqualTo("MATCHED");
        assertThat(updatedTrip.getDriverId()).isEqualTo("drv_" + randomId);
        assertThat(idempotencyLogRepository.existsById(eventId)).isTrue();
    }

    @Test
    void testMatchingFailedConsumer_SagaCompensation() throws InterruptedException {
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        Trip trip = new Trip();
        trip.setTripId("trip_fail_" + randomId);
        trip.setPassengerId("usr_" + randomId);
        trip.setPickupLat(10.762622);
        trip.setPickupLong(106.660172);
        trip.setDestLat(10.775620);
        trip.setDestLong(106.700420);
        trip.setStatus("PENDING");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        String eventId = "evt_fail_" + randomId;
        TripRequestedEvent.EventMetadata metadata = TripRequestedEvent.EventMetadata.builder()
                .event_id(eventId)
                .correlation_id(trip.getTripId())
                .event_type("MATCHING_FAILED")
                .timestamp(LocalDateTime.now().toString())
                .source("matching-service")
                .build();
        MatchingFailedEvent.Payload payload = MatchingFailedEvent.Payload.builder()
                .trip_id(trip.getTripId())
                .reason("TIMEOUT_NO_DRIVERS")
                .build();

        kafkaTemplate.send("matching.failed", trip.getTripId(), new MatchingFailedEvent(metadata, payload));

        Trip updatedTrip = null;
        for (int i = 0; i < 15; i++) {
            Thread.sleep(1000);
            updatedTrip = tripRepository.findById(trip.getTripId()).orElse(null);
            if (updatedTrip != null && "CANCELED".equals(updatedTrip.getStatus())) {
                break;
            }
        }

        assertThat(updatedTrip).isNotNull();
        assertThat(updatedTrip.getStatus()).isEqualTo("CANCELED");
        assertThat(updatedTrip.getCancelReason()).isEqualTo("TIMEOUT_NO_DRIVERS");
        assertThat(idempotencyLogRepository.existsById(eventId)).isTrue();
    }

    @Test
    void testAcceptStartAndCompleteTripLifecycle() {
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        Trip trip = new Trip();
        trip.setTripId("trip_flow_" + randomId);
        trip.setPassengerId("usr_" + randomId);
        trip.setDriverId("drv_" + randomId);
        trip.setPickupLat(10.762622);
        trip.setPickupLong(106.660172);
        trip.setDestLat(10.775620);
        trip.setDestLong(106.700420);
        trip.setStatus("MATCHED");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        HttpEntity<Void> empty = new HttpEntity<>(new HttpHeaders());

        ResponseEntity<Trip> acceptResponse = restTemplate.exchange(
                "/api/trips/" + trip.getTripId() + "/accept", HttpMethod.PUT, empty, Trip.class);
        assertThat(acceptResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(acceptResponse.getBody().getStatus()).isEqualTo("ACCEPTED");

        ResponseEntity<Trip> startResponse = restTemplate.exchange(
                "/api/trips/" + trip.getTripId() + "/start", HttpMethod.PUT, empty, Trip.class);
        assertThat(startResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(startResponse.getBody().getStatus()).isEqualTo("STARTED");

        ResponseEntity<Trip> completeResponse = restTemplate.exchange(
                "/api/trips/" + trip.getTripId() + "/complete", HttpMethod.PUT, empty, Trip.class);
        assertThat(completeResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        Trip completedTrip = completeResponse.getBody();
        assertThat(completedTrip.getStatus()).isEqualTo("COMPLETED");
        assertThat(completedTrip.getPaymentStatus()).isEqualTo("PAID_SIMULATED");
        assertThat(completedTrip.getFareAmount()).isGreaterThan(BigDecimal.ZERO);
    }

    @Test
    void testRejectTripApi() {
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        Trip trip = new Trip();
        trip.setTripId("trip_rej_" + randomId);
        trip.setPassengerId("usr_" + randomId);
        trip.setDriverId("drv_" + randomId);
        trip.setPickupLat(10.762622);
        trip.setPickupLong(106.660172);
        trip.setDestLat(10.775620);
        trip.setDestLong(106.700420);
        trip.setStatus("MATCHED");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Trip> response = restTemplate.exchange(
                "/api/trips/" + trip.getTripId() + "/reject",
                HttpMethod.PUT,
                new HttpEntity<>(new TripCancelDTO("DRIVER_BUSY"), headers),
                Trip.class
        );
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().getStatus()).isEqualTo("CANCELED");
        assertThat(response.getBody().getCancelReason()).isEqualTo("DRIVER_BUSY");
    }

    @Test
    void testCancelTripApi() {
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        Trip trip = new Trip();
        trip.setTripId("trip_can_" + randomId);
        trip.setPassengerId("usr_" + randomId);
        trip.setPickupLat(10.762622);
        trip.setPickupLong(106.660172);
        trip.setDestLat(10.775620);
        trip.setDestLong(106.700420);
        trip.setStatus("PENDING");
        trip.setPaymentStatus("UNPAID");
        trip.setCreatedAt(LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        ResponseEntity<Trip> response = restTemplate.exchange(
                "/api/trips/" + trip.getTripId() + "/cancel",
                HttpMethod.PUT,
                new HttpEntity<>(new TripCancelDTO("PASSENGER_CHANGED_MIND"), headers),
                Trip.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody().getStatus()).isEqualTo("CANCELED");
        assertThat(response.getBody().getCancelReason()).isEqualTo("PASSENGER_CHANGED_MIND");
    }

    @Test
    void testFareCalculationAccuracy() {
        BigDecimal fare = fareCalculationService.calculateFare(10.7721, 106.6983, 10.7950, 106.7219);
        assertThat(fare).isNotNull();
        assertThat(fare).isGreaterThanOrEqualTo(BigDecimal.valueOf(15000));
    }
}

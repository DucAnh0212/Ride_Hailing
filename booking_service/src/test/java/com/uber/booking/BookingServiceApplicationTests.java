package com.uber.booking;

import com.uber.booking.dto.TripRequestDTO;
import com.uber.booking.models.Trip;
import com.uber.booking.repositories.TripRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class BookingServiceApplicationTests {

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private TripRepository tripRepository;

    @Test
    void testCreateBookingApi() {
        // 1. Chuẩn bị dữ liệu JSON giả lập Client gửi lên
        TripRequestDTO request = new TripRequestDTO();
        request.setPassengerId("usr_999");
        request.setPickupLat(10.762622);
        request.setPickupLong(106.660172);
        request.setDestLat(10.775620);
        request.setDestLong(106.700420);
        request.setVehicleType("MOTORBIKE");

        // 2. Gọi API POST /api/trips
        ResponseEntity<Trip> response = restTemplate.postForEntity("/api/trips", request, Trip.class);

        // 3. Kiểm chứng kết quả (Assertions)
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        
        Trip createdTrip = response.getBody();
        assertThat(createdTrip).isNotNull();
        assertThat(createdTrip.getTripId()).startsWith("trip_");
        assertThat(createdTrip.getStatus()).isEqualTo("PENDING");
        assertThat(createdTrip.getPaymentStatus()).isEqualTo("UNPAID");

        // 4. Kiểm tra xem dữ liệu đã thực sự lưu vào SQL Server chưa
        long count = tripRepository.count();
        System.out.println("\n=================================================");
        System.out.println("🎉 TEST API POST /api/trips THÀNH CÔNG! 🎉");
        System.out.println("Mã chuyến đi vừa được tạo: " + createdTrip.getTripId());
        System.out.println("Hành khách: " + createdTrip.getPassengerId());
        System.out.println("Trạng thái: " + createdTrip.getStatus());
        System.out.println("Tọa độ đón: " + createdTrip.getPickupLat() + ", " + createdTrip.getPickupLong());
        System.out.println("Tổng số chuyến đi trong DB hiện tại: " + count);
        System.out.println("=================================================\n");
    }

    @Autowired
    private org.springframework.kafka.core.KafkaTemplate<String, Object> kafkaTemplate;

    @Autowired
    private com.uber.booking.repositories.IdempotencyLogRepository idempotencyLogRepository;

    @Test
    void testDriverMatchedConsumer() throws InterruptedException {
        // 1. Tạo sẵn một Trip rỗng trạng thái PENDING
        Trip trip = new Trip();
        trip.setTripId("trip_test_" + java.util.UUID.randomUUID().toString().substring(0, 8));
        trip.setPassengerId("usr_test");
        trip.setStatus("PENDING");
        trip.setCreatedAt(java.time.LocalDateTime.now());
        trip.setVersion(0);
        tripRepository.save(trip);

        // 2. Tạo một sự kiện giả lập từ Matching Service
        String eventId = "evt_" + java.util.UUID.randomUUID().toString().substring(0, 8);
        com.uber.booking.events.TripRequestedEvent.EventMetadata metadata = com.uber.booking.events.TripRequestedEvent.EventMetadata.builder()
                .event_id(eventId)
                .correlation_id(trip.getTripId())
                .event_type("DRIVER_MATCHED")
                .timestamp(java.time.LocalDateTime.now().toString())
                .source("matching-service")
                .build();
        
        com.uber.booking.events.DriverMatchedEvent.Payload payload = com.uber.booking.events.DriverMatchedEvent.Payload.builder()
                .trip_id(trip.getTripId())
                .driver_id("drv_999")
                .distance_to_pickup_km(1.5)
                .estimated_time_arrival_mins(5)
                .build();

        com.uber.booking.events.DriverMatchedEvent event = new com.uber.booking.events.DriverMatchedEvent(metadata, payload);

        // 3. Gửi sự kiện lên Kafka
        kafkaTemplate.send("driver.matched", trip.getTripId(), event);

        System.out.println("\n[TEST] Đã gửi sự kiện driver.matched. Chờ Consumer xử lý...");

        // 4. Chờ tối đa 15 giây để Consumer đọc và xử lý xong
        Trip updatedTrip = null;
        for (int i = 0; i < 15; i++) {
            Thread.sleep(1000);
            updatedTrip = tripRepository.findById(trip.getTripId()).orElse(null);
            if (updatedTrip != null && "ACCEPTED".equals(updatedTrip.getStatus())) {
                break;
            }
        }
        assertThat(updatedTrip).isNotNull();
        assertThat(updatedTrip.getStatus()).isEqualTo("ACCEPTED");
        assertThat(updatedTrip.getDriverId()).isEqualTo("drv_999");

        boolean isIdempotencySaved = idempotencyLogRepository.existsById(eventId);
        assertThat(isIdempotencySaved).isTrue();

        System.out.println("\n=================================================");
        System.out.println("🎉 TEST CONSUMER driver.matched THÀNH CÔNG! 🎉");
        System.out.println("Chuyến đi đã được cập nhật thành: " + updatedTrip.getStatus());
        System.out.println("Tài xế nhận cuốc: " + updatedTrip.getDriverId());
        System.out.println("Đã ghi log Idempotency với Event ID: " + eventId);
        System.out.println("=================================================\n");
    }
}

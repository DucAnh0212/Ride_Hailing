package com.uber.booking.events;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TripRequestedEvent {
    
    private EventMetadata metadata;
    private Payload payload;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class EventMetadata {
        private String event_id;
        private String correlation_id;
        private String event_type;
        private String timestamp;
        private String source;
    }

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class Payload {
        private String trip_id;
        private String passenger_id;
        private double pickup_lat;
        private double pickup_long;
        private double destination_lat;
        private double destination_long;
        private String vehicle_type;
    }
}

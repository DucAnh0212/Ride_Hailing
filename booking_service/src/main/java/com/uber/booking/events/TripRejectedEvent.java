package com.uber.booking.events;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class TripRejectedEvent {

    private TripRequestedEvent.EventMetadata metadata;
    private Payload payload;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    @Builder
    public static class Payload {
        private String trip_id;
        private String driver_id;
        private String passenger_id;
        private String reason;
        private LocalDateTime rejected_at;
    }
}

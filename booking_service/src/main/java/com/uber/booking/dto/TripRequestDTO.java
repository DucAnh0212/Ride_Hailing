package com.uber.booking.dto;

import lombok.Data;

@Data
public class TripRequestDTO {
    private String passengerId;
    private Double pickupLat;
    private Double pickupLong;
    private Double destLat;
    private Double destLong;
    private String vehicleType;
}

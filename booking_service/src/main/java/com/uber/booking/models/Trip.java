package com.uber.booking.models;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import lombok.Data;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Table(name = "Trips")
@Data
public class Trip {

    @Id
    private String tripId;
    private String passengerId;
    private String driverId;
    private Double pickupLat;
    private Double pickupLong;
    private Double destLat;
    private Double destLong;
    private String status;
    private String cancelReason;
    private BigDecimal fareAmount;
    private String paymentStatus;
    private LocalDateTime createdAt;

    @Version
    private Integer version;
}

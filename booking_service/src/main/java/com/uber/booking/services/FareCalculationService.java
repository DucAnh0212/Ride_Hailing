package com.uber.booking.services;

import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.math.RoundingMode;

@Service
public class FareCalculationService {

    private static final double EARTH_RADIUS_KM = 6371.0;
    private static final double BASE_FARE = 15000.0; // Giá mở cửa (15,000 VND)
    private static final double RATE_PER_KM = 10000.0; // 10,000 VND / km

    /**
     * Tính khoảng cách đường chim bay theo công thức Haversine (km)
     */
    public double calculateDistanceKm(Double lat1, Double lon1, Double lat2, Double lon2) {
        if (lat1 == null || lon1 == null || lat2 == null || lon2 == null) {
            return 3.0; // Khoảng cách mặc định nếu thiếu tọa độ
        }

        double dLat = Math.toRadians(lat2 - lat1);
        double dLon = Math.toRadians(lon2 - lon1);

        double a = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                + Math.cos(Math.toRadians(lat1)) * Math.cos(Math.toRadians(lat2))
                * Math.sin(dLon / 2) * Math.sin(dLon / 2);

        double c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return EARTH_RADIUS_KM * c;
    }

    /**
     * Tính toán cước phí chuyến đi
     */
    public BigDecimal calculateFare(Double pickupLat, Double pickupLong, Double destLat, Double destLong) {
        double distanceKm = calculateDistanceKm(pickupLat, pickupLong, destLat, destLong);
        double fare = BASE_FARE + (distanceKm * RATE_PER_KM);
        if (fare < BASE_FARE) {
            fare = BASE_FARE;
        }

        return BigDecimal.valueOf(fare).setScale(2, RoundingMode.HALF_UP);
    }
}

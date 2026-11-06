-- Tạo cơ sở dữ liệu cho Booking Service (chỉ chạy dòng này nếu bạn chưa có Database)
-- CREATE DATABASE BookingDB;
-- GO
-- USE BookingDB;
-- GO

-- 1. Bảng lưu trạng thái vòng đời chuyến đi
CREATE TABLE Trips (
    trip_id VARCHAR(50) PRIMARY KEY,
    passenger_id VARCHAR(50) NOT NULL,
    driver_id VARCHAR(50) NULL,
    
    pickup_lat FLOAT NOT NULL,
    pickup_long FLOAT NOT NULL,
    dest_lat FLOAT NOT NULL,
    dest_long FLOAT NOT NULL,
    
    status VARCHAR(20) NOT NULL, -- PENDING, ACCEPTED, STARTED, COMPLETED, CANCELED
    cancel_reason VARCHAR(100) NULL,
    
    fare_amount DECIMAL(10,2) NULL,
    payment_status VARCHAR(20) DEFAULT 'UNPAID', -- PAID_SIMULATED
    
    created_at DATETIME NOT NULL,
    
    -- Cột này CỰC KỲ QUAN TRỌNG: Dùng cho Optimistic Locking ở Tuần 5
    -- Khi dùng Spring Data JPA, bạn map nó với annotation @Version
    version INT NOT NULL DEFAULT 0 
);
GO

-- 2. Bảng phục vụ tính Lũy đẳng (Idempotency) - Chống lặp tin nhắn từ Kafka
CREATE TABLE Idempotency_Log (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    processed_at DATETIME NOT NULL DEFAULT GETDATE()
);
GO

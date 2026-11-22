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

    version INT NOT NULL DEFAULT 0 
);
GO

CREATE TABLE Idempotency_Log (
    event_id VARCHAR(100) PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    processed_at DATETIME NOT NULL DEFAULT GETDATE()
);
GO

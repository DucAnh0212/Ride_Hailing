import codecs
import random
import uuid

def random_lat():
    # Tọa độ Vĩ độ xung quanh khu vực TP.HCM
    return round(random.uniform(10.700000, 10.850000), 6)

def random_long():
    # Tọa độ Kinh độ xung quanh khu vực TP.HCM
    return round(random.uniform(106.600000, 106.750000), 6)

def random_fare():
    # Mức cước phí ngẫu nhiên
    return random.choice([25000.00, 35000.00, 42000.00, 58000.00, 75000.00, 120000.00])

with codecs.open('c:/Users/tinca/OneDrive/Desktop/HeThongPhanTan/code/Ride_Hailing/booking_service/src/main/resources/data.sql', 'w', encoding='utf-8') as f:
    f.write('-- Tạo bảng Idempotency_Log (nếu chưa có do chưa code Entity)\n')
    f.write('IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = \'Idempotency_Log\')\n')
    f.write('BEGIN\n')
    f.write('  CREATE TABLE Idempotency_Log (event_id VARCHAR(100) PRIMARY KEY, event_type VARCHAR(50) NOT NULL, processed_at DATETIME NOT NULL);\n')
    f.write('END\n\n')
    f.write('-- Xóa dữ liệu cũ (nếu có)\n')
    f.write('DELETE FROM Idempotency_Log;\nDELETE FROM Trips;\n\n')
    f.write('-- 1. Dữ liệu mẫu cho bảng Trips (10 dòng mỗi trạng thái với dữ liệu ngẫu nhiên)\n')
    f.write('INSERT INTO Trips (trip_id, passenger_id, driver_id, pickup_lat, pickup_long, dest_lat, dest_long, status, cancel_reason, fare_amount, payment_status, created_at, version)\nVALUES\n')
    
    rows = []
    
    # 1. PENDING (10 dòng)
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        p_id = f"usr_{random.randint(100, 999)}"
        rows.append(f"('trip_pen_{uid}', '{p_id}', NULL, {random_lat()}, {random_long()}, {random_lat()}, {random_long()}, 'PENDING', NULL, NULL, 'UNPAID', GETDATE(), 0)")
        
    # 2. STARTED (10 dòng)
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        p_id = f"usr_{random.randint(100, 999)}"
        d_id = f"drv_{random.randint(100, 999)}"
        rows.append(f"('trip_sta_{uid}', '{p_id}', '{d_id}', {random_lat()}, {random_long()}, {random_lat()}, {random_long()}, 'STARTED', NULL, {random_fare()}, 'UNPAID', GETDATE(), 1)")
        
    # 3. COMPLETED (10 dòng)
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        p_id = f"usr_{random.randint(100, 999)}"
        d_id = f"drv_{random.randint(100, 999)}"
        rows.append(f"('trip_com_{uid}', '{p_id}', '{d_id}', {random_lat()}, {random_long()}, {random_lat()}, {random_long()}, 'COMPLETED', NULL, {random_fare()}, 'PAID_SIMULATED', GETDATE(), 2)")
        
    # 4. CANCELED (10 dòng)
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        p_id = f"usr_{random.randint(100, 999)}"
        reason = random.choice(['TIMEOUT_NO_DRIVERS', 'PASSENGER_CANCELED', 'DRIVER_REJECTED'])
        rows.append(f"('trip_can_{uid}', '{p_id}', NULL, {random_lat()}, {random_long()}, {random_lat()}, {random_long()}, 'CANCELED', '{reason}', NULL, 'UNPAID', GETDATE(), 0)")
    
    f.write(',\n'.join(rows) + ';\n\n')
    
    f.write('-- 2. Dữ liệu mẫu cho bảng Idempotency_Log (20 dòng)\n')
    f.write('INSERT INTO Idempotency_Log (event_id, event_type, processed_at)\nVALUES\n')
    
    idem_rows = []
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        idem_rows.append(f"('req_evt_{uid}', 'TRIP_REQUESTED', GETDATE())")
    for i in range(1, 11):
        uid = str(uuid.uuid4())[:8]
        idem_rows.append(f"('mat_evt_{uid}', 'DRIVER_MATCHED', GETDATE())")
        
    f.write(',\n'.join(idem_rows) + ';\n')

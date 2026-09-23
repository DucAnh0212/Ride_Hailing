import os
import random
from datetime import datetime, timedelta
import pyodbc
from pymongo import MongoClient
from faker import Faker
from dotenv import load_dotenv

# Tải cấu hình từ file .env
load_dotenv()
fake = Faker('vi_VN')

NUM_RIDERS = 2000       # Số lượng Khách hàng
NUM_DRIVERS = 500       # Số lượng Tài xế
NUM_RIDES = 15000       # Số lượng Chuyến xe lưu vào MongoDB
BATCH_SIZE = 1000       # Kích thước mỗi lô dữ liệu (Ghi xuống DB sau mỗi 1000 dòng)

sql_host = "localhost"
sql_port = "14333"
sql_user = "sa"
sql_pass = "RideAdmin#2026"
connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={sql_host},{sql_port};UID={sql_user};PWD={sql_pass};TrustServerCertificate=yes;"

try:
    # Kết nối ban đầu để tạo DB
    sql_conn = pyodbc.connect(connection_string, autocommit=True)
    cursor = sql_conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'RideHailingDB')
        BEGIN CREATE DATABASE RideHailingDB; END
    """)
    
    sql_conn = pyodbc.connect(connection_string + "DATABASE=RideHailingDB;")
    cursor = sql_conn.cursor()
    cursor.fast_executemany = True  
    
    cursor.execute("IF OBJECT_ID('Vehicles', 'U') IS NOT NULL DROP TABLE Vehicles")
    cursor.execute("IF OBJECT_ID('Users', 'U') IS NOT NULL DROP TABLE Users")

    cursor.execute("""
        CREATE TABLE Users (
            UserID INT IDENTITY(1,1) PRIMARY KEY,
            FullName NVARCHAR(100),
            PhoneNumber VARCHAR(50) UNIQUE,
            Role VARCHAR(20) CHECK (Role IN ('Rider', 'Driver')),
            CreatedAt DATETIME DEFAULT GETDATE()
        )
    """)
    
    # Tạo bảng Vehicles
    cursor.execute("""
        CREATE TABLE Vehicles (
            VehicleID INT IDENTITY(1,1) PRIMARY KEY,
            DriverID INT FOREIGN KEY REFERENCES Users(UserID),
            LicensePlate VARCHAR(50) UNIQUE,
            VehicleType VARCHAR(50),
            Color NVARCHAR(30)
        )
    """)
    sql_conn.commit()

except Exception as e:
    print(f"Lỗi kết nối: {e}")
    exit()

try:
    mongo_client = MongoClient(os.getenv("MONGODB_URI"))
    mongo_db = mongo_client["RideHailingDB"]
    rides_collection = mongo_db["Rides"]
    rides_collection.delete_many({}) # Xóa data cũ
except Exception as e:
    exit()

# A. Nạp dữ liệu Users (Riders & Drivers)
def seed_users(role, total_count):
    inserted = 0
    while inserted < total_count:
        batch_data = []
        current_batch_size = min(BATCH_SIZE, total_count - inserted)
        
        for _ in range(current_batch_size):
            # Dùng fake.unique để đảm bảo PhoneNumber không bị trùng làm sập DB
            batch_data.append((fake.name(), fake.unique.phone_number(), role))
            
        cursor.executemany("INSERT INTO Users (FullName, PhoneNumber, Role) VALUES (?, ?, ?)", batch_data)
        sql_conn.commit()
        inserted += current_batch_size
        print(f"   + Đã nạp {inserted}/{total_count} {role}...")

seed_users('Rider', NUM_RIDERS)
seed_users('Driver', NUM_DRIVERS)

# Lấy danh sách ID thực tế từ SQL Server
cursor.execute("SELECT UserID FROM Users WHERE Role = 'Driver'")
driver_ids = [row[0] for row in cursor.fetchall()]

cursor.execute("SELECT UserID FROM Users WHERE Role = 'Rider'")
rider_ids = [row[0] for row in cursor.fetchall()]

# B. Nạp dữ liệu Vehicles cho Drivers
vehicles_data = []
vehicle_types = ['Honda Vision', 'Yamaha Exciter', 'Toyota Vios', 'Hyundai Accent', 'VinFast VF e34']

for driver_id in driver_ids:
    # fake.unique để đảm bảo Biển số xe không trùng nhau
    license_plate = fake.unique.bothify(text='??-#####', letters='ABCDEFGHJKLMNPRSTUVWXYZ')
    vehicles_data.append((driver_id, f"29{license_plate}", random.choice(vehicle_types), fake.color_name()))

# Do số lượng tài xế (500) nhỏ hơn BATCH_SIZE (1000) nên ta insert luôn 1 lượt
cursor.executemany("INSERT INTO Vehicles (DriverID, LicensePlate, VehicleType, Color) VALUES (?, ?, ?, ?)", vehicles_data)
sql_conn.commit()

# C. Nạp dữ liệu Chuyến xe vào MongoDB theo Lô
inserted_rides = 0
statuses = ['Completed', 'Cancelled', 'In_Progress']

while inserted_rides < NUM_RIDES:
    rides_batch = []
    current_batch_size = min(BATCH_SIZE, NUM_RIDES - inserted_rides)
    
    for _ in range(current_batch_size):
        ride = {
            "RiderID": random.choice(rider_ids),
            "DriverID": random.choice(driver_ids),
            "Status": random.choice(statuses),
            "Price": random.randint(30, 250) * 1000,
            "StartTime": datetime.utcnow() - timedelta(days=random.randint(0, 30)),
            "Route": {
                "PickupLocation": {"lat": round(random.uniform(21.0, 21.1), 6), "lng": round(random.uniform(105.7, 105.9), 6)},
                "DropoffLocation": {"lat": round(random.uniform(21.0, 21.1), 6), "lng": round(random.uniform(105.7, 105.9), 6)}
            },
            "Rating": random.randint(1, 5) if random.random() > 0.3 else None
        }
        rides_batch.append(ride)
        
    rides_collection.insert_many(rides_batch)
    inserted_rides += current_batch_size
    print(f"   + Đã nạp {inserted_rides}/{NUM_RIDES} chuyến xe vào MongoDB...")

# Đóng kết nối
cursor.close()
sql_conn.close()
mongo_client.close()
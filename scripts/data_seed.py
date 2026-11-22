import argparse
import logging
import os
import random
from datetime import datetime, timedelta
import pyodbc
from pymongo import MongoClient
from faker import Faker
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s | NODE: Data-Seed | %(levelname)s | %(message)s')

parser = argparse.ArgumentParser(description="Seed synthetic users/vehicles into IdentityDB")
parser.add_argument("--confirm-reset", action="store_true", help="Confirm dropping and recreating Users/Vehicles tables")
parser.add_argument("--riders", type=int, default=200)
parser.add_argument("--drivers", type=int, default=50)
args = parser.parse_args()

if not args.confirm_reset:
    raise SystemExit("Refusing destructive seed without --confirm-reset. Existing database preserved.")

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
fake = Faker('vi_VN')

BATCH_SIZE = 1000
sql_host = os.getenv("SQL_SERVER_HOST", "localhost")
sql_port = os.getenv("SQL_SERVER_PORT", "14333")
sql_user = os.getenv("SQL_SERVER_USER", "sa")
sql_pass = os.getenv("SQL_SERVER_PASSWORD", "")
db_name = os.getenv("IDENTITY_DB_NAME", "IdentityDB")
mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={sql_host},{sql_port};"
    f"UID={sql_user};PWD={sql_pass};TrustServerCertificate=yes;"
)

sql_conn = pyodbc.connect(connection_string, autocommit=True)
cursor = sql_conn.cursor()
cursor.execute(f"IF DB_ID('{db_name}') IS NULL CREATE DATABASE [{db_name}]")
sql_conn.close()

sql_conn = pyodbc.connect(connection_string + f"DATABASE={db_name};")
cursor = sql_conn.cursor()
cursor.fast_executemany = True

cursor.execute("IF OBJECT_ID('dbo.Vehicles', 'U') IS NOT NULL DROP TABLE dbo.Vehicles")
cursor.execute("IF OBJECT_ID('dbo.Users', 'U') IS NOT NULL DROP TABLE dbo.Users")
cursor.execute("""
    CREATE TABLE dbo.Users (
        UserID INT IDENTITY(1,1) PRIMARY KEY,
        FullName NVARCHAR(100) NOT NULL,
        PhoneNumber VARCHAR(50) NOT NULL UNIQUE,
        PasswordHash VARCHAR(255) NULL,
        Role VARCHAR(20) NOT NULL CHECK (Role IN ('Rider', 'Driver')),
        IsActive BIT NOT NULL DEFAULT 1,
        CreatedAt DATETIME NOT NULL DEFAULT GETDATE()
    )
""")
cursor.execute("""
    CREATE TABLE dbo.Vehicles (
        VehicleID INT IDENTITY(1,1) PRIMARY KEY,
        DriverID INT NOT NULL REFERENCES dbo.Users(UserID),
        LicensePlate VARCHAR(50) NOT NULL UNIQUE,
        VehicleType VARCHAR(50) NOT NULL,
        Color NVARCHAR(30)
    )
""")
sql_conn.commit()


def seed_users(role, total_count):
    inserted = 0
    while inserted < total_count:
        batch = [(fake.name(), fake.unique.phone_number(), role) for _ in range(min(BATCH_SIZE, total_count - inserted))]
        cursor.executemany("INSERT INTO dbo.Users (FullName, PhoneNumber, Role) VALUES (?, ?, ?)", batch)
        sql_conn.commit()
        inserted += len(batch)
        logging.info("Seeded %d/%d %s", inserted, total_count, role)


seed_users('Rider', args.riders)
seed_users('Driver', args.drivers)

cursor.execute("SELECT UserID FROM dbo.Users WHERE Role = 'Driver'")
driver_ids = [row[0] for row in cursor.fetchall()]

vehicle_types = ['Honda Vision', 'Yamaha Exciter', 'Toyota Vios', 'Hyundai Accent', 'VinFast VF e34']
vehicles = [
    (did, f"29{fake.unique.bothify(text='??-#####', letters='ABCDEFGHJKLMNPRSTUVWXYZ')}",
     random.choice(vehicle_types), fake.color_name())
    for did in driver_ids
]
cursor.executemany("INSERT INTO dbo.Vehicles (DriverID, LicensePlate, VehicleType, Color) VALUES (?, ?, ?, ?)", vehicles)
sql_conn.commit()
cursor.close()
sql_conn.close()
logging.info("Seeded %s successfully (%d riders, %d drivers, %d vehicles).", db_name, args.riders, args.drivers, len(vehicles))

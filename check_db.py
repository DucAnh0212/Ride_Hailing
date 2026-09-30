import os
import logging
import pyodbc
from pymongo import MongoClient
from dotenv import load_dotenv

# Khởi tạo Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s | NODE: DB-Check | %(levelname)s | %(message)s')

load_dotenv()

logging.info("🔍 ĐANG KIỂM TRA DỮ LIỆU TRONG CONTAINER...\n")

# Lấy cấu hình từ biến môi trường
sql_host = os.getenv("SQL_SERVER_HOST", "localhost")
sql_port = os.getenv("SQL_SERVER_PORT", "1433")
sql_user = os.getenv("SQL_SERVER_USER", "sa")
sql_pass = os.getenv("SQL_SERVER_PASSWORD", "")
mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")

# 1. Kiểm tra SQL Server
try:
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={sql_host},{sql_port};DATABASE=RideHailingDB;UID={sql_user};PWD={sql_pass};TrustServerCertificate=yes;"
    sql_conn = pyodbc.connect(conn_str)
    cursor = sql_conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM Users")
    logging.info(f"✅ SQL Server -> Bảng Users có: {cursor.fetchone()[0]} dòng")
    
    cursor.execute("SELECT COUNT(*) FROM Vehicles")
    logging.info(f"✅ SQL Server -> Bảng Vehicles có: {cursor.fetchone()[0]} dòng")
except Exception as e:
    logging.error(f"❌ Lỗi SQL Server: {e}")

# 2. Kiểm tra MongoDB
try:
    mongo_client = MongoClient(mongo_uri)
    db = mongo_client["RideHailingDB"]
    rides_count = db["Rides"].count_documents({})
    logging.info(f"✅ MongoDB -> Collection Rides có: {rides_count} dòng")
except Exception as e:
    logging.error(f"❌ Lỗi MongoDB: {e}")

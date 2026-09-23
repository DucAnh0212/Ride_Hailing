import pyodbc
from pymongo import MongoClient

print("🔍 ĐANG KIỂM TRA DỮ LIỆU TRONG CONTAINER...\n")

sql_host = "localhost"
sql_port = "14333"
sql_user = "sa"
sql_pass = "RideAdmin#2026"

# 1. Kiểm tra SQL Server
try:
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={sql_host},{sql_port};DATABASE=RideHailingDB;UID={sql_user};PWD={sql_pass};TrustServerCertificate=yes;"
    sql_conn = pyodbc.connect(conn_str)
    cursor = sql_conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM Users")
    print(f"✅ SQL Server -> Bảng Users có: {cursor.fetchone()[0]} dòng")
    
    cursor.execute("SELECT COUNT(*) FROM Vehicles")
    print(f"✅ SQL Server -> Bảng Vehicles có: {cursor.fetchone()[0]} dòng")
except Exception as e:
    print(f"❌ Lỗi SQL Server: {e}")

# 2. Kiểm tra MongoDB
try:
    mongo_client = MongoClient("mongodb://localhost:27017/")
    db = mongo_client["RideHailingDB"]
    rides_count = db["Rides"].count_documents({})
    print(f"✅ MongoDB -> Collection Rides có: {rides_count} dòng")
except Exception as e:
    print(f"❌ Lỗi MongoDB: {e}")
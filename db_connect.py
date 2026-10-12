
# pyrefly: ignore [missing-import]
import pyodbc

# Thông tin cấu hình kết nối dựa trên Connection String bạn cung cấp
server = r'localhost\SQLEXPRESS'
database = 'RideHailingDB'
username = 'sa'
password = '1'

# Tạo chuỗi kết nối tương thích với pyodbc
connection_string = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={server};"
    f"DATABASE={database};"
    f"UID={username};"
    f"PWD={password};"
    f"TrustServerCertificate=yes;"
)

def test_connection():
    try:
        print("Testing connection to SQL Server...")
        # Thiết lập kết nối
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        # Chạy một truy vấn thử nghiệm lấy phiên bản SQL Server
        cursor.execute("SELECT @@VERSION")
        row = cursor.fetchone()
        
        print("\n[SUCCESS] CONNECTION ESTABLISHED!")
        print("-" * 50)
        print("Your SQL Server version is:\n", row[0])
        print("-" * 50)
        
        # Đóng kết nối để giải phóng bộ nhớ
        cursor.close()
        conn.close()
        
    except Exception as e:
        print("[ERROR] CONNECTION FAILED:")
        print(e)

if __name__ == "__main__":
    test_connection()

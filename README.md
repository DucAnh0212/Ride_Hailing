# Ride Hailing — Hệ thống đặt xe Microservices phân tán (DS03)

Hệ thống đặt xe phân tán mô phỏng Grab/Uber với 5 business microservices độc lập (Database-per-Service), API Gateway, Apache Kafka, Frontend React và bộ kiểm thử/mô phỏng tự động.

## 1. Kiến trúc, phân công và tách biệt dữ liệu

| Thành viên | Phụ trách | Công nghệ | Database sở hữu |
|---|---|---|---|
| Tùng | `identity-service`, `api-gateway`, `frontend` | Node.js 22, Express, JWT, React, Vite | SQL Server: `IdentityDB` |
| Tín | `booking-service` (vòng đời chuyến, Accept/Reject, Saga, tính cước) | Java 17, Spring Boot 3.2, Kafka | SQL Server: `BookingDB` |
| Đức Anh | `location_service`, `matching_worker`, `analytics_worker`, Docker/Cloud, Simulator | Python 3.11, FastAPI, MongoDB, Kafka, Docker | MongoDB: `LocationDB`, `MatchingDB`, `DataWarehouseDB` |

~~~text
Browser -> Frontend (Nginx :80) -> API Gateway (:3000, JWT + RBAC + Correlation-ID)
  -> Identity Service (:3001)  -> SQL Server [IdentityDB]
  -> Booking Service  (:8080)  -> SQL Server [BookingDB]
  -> Location Service (:8000)  -> MongoDB    [LocationDB]

Booking --(Kafka: trip.requested/completed/cancelled)--> Matching Worker -> MongoDB [MatchingDB]
Matching Worker --(Internal REST /internal/drivers/*)--> Location Service -> MongoDB [LocationDB]
Matching Worker --(Kafka: driver.matched / matching.failed)--> Booking Service
Kafka (8 lifecycle topics) --> Analytics Worker -> MongoDB [DataWarehouseDB]
~~~

Mỗi microservice chỉ đọc/ghi cơ sở dữ liệu của riêng mình; không có truy cập chéo DB giữa các service.

## 2. Cấu trúc thư mục

~~~text
api-gateway/                 Xác thực JWT, RBAC, Correlation ID, định tuyến REST
identity-service/            Đăng ký/đăng nhập, quản lý tài khoản (IdentityDB)
booking_service/             Vòng đời chuyến đi, Accept/Reject, Saga, tính cước (BookingDB)
matching_location_service/   Location API (LocationDB) và Matching Worker (MatchingDB)
analytics_service/           ELT Worker thu thập 8 topic Kafka vào DataWarehouseDB + DLQ
frontend/                    Giao diện Hành khách và Tài xế (React + Vite)
deploy/                      Cấu hình override bảo mật & hướng dẫn triển khai Cloud VPS
tests/                       Bộ 15 ca kiểm thử tự động theo Mục 9 đặc tả DS03
scripts/                     Driver simulator/benchmark qua Gateway, fault injection, check DB
docs/                        Tài liệu kỹ thuật (đặt report.pdf & slides.pdf tại đây)
docker-compose.yml           Toàn bộ hạ tầng và microservices
.env.example                 Mẫu cấu hình biến môi trường (không chứa bí mật)
~~~

## 3. Cài đặt và khởi chạy bằng Docker

### 3.1. Tạo file `.env`
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
$b = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($b); $rng.Dispose()
"JWT_SECRET=" + (-join ($b | ForEach-Object { $_.ToString("x2") }))
```
Điền `SQL_SERVER_PASSWORD` (đạt độ mạnh SQL Server) và dòng `JWT_SECRET=...` vào cuối `.env`. Kiểm tra cấu hình:
```powershell
docker compose config --quiet
```

### 3.2. Khởi chạy toàn bộ hệ thống
```powershell
docker compose up -d --build
docker compose ps
```
`IdentityDB` và `BookingDB` được tự động khởi tạo idempotent bởi `identity-service` và `booking-service` khi khởi động (không xóa dữ liệu cũ). Mở giao diện tại **http://localhost** (API Gateway tại **http://localhost:3000**).

Để triển khai lên **Cloud / VPS** (khóa cổng SQL Server, MongoDB, Kafka, Zookeeper về `127.0.0.1`), xem [deploy/README.md](deploy/README.md):
```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.cloud.yml up -d --build
```

## 4. API qua Gateway (`http://localhost:3000`)

| Chức năng | Endpoint | Quyền |
|---|---|---|
| Đăng ký / đăng nhập / thông tin tài khoản | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` | Public / Bearer |
| Tạo / xem danh sách / chi tiết chuyến | `POST /api/trips`, `GET /api/trips`, `GET /api/trips/{id}` | Bearer (theo chủ chuyến) |
| Chấp nhận / từ chối chuyến | `PUT /api/trips/{id}/accept`, `PUT /api/trips/{id}/reject` | `Driver` được gán |
| Bắt đầu / hoàn thành / hủy chuyến | `PUT /api/trips/{id}/start`, `/complete`, `/cancel` | `Driver` / Chủ chuyến |
| Cập nhật tọa độ / đọc trạng thái / Online–Offline | `POST /api/location`, `GET /api/location/me`, `PUT /api/location/status` | `Driver` |

## 5. Kịch bản demo E2E (2 phiên trình duyệt)
1. Mở **http://localhost** ở trình duyệt thường (đăng ký **Hành khách**) và cửa sổ ẩn danh (đăng ký **Tài xế**).
2. Tài xế gửi vị trí `21.0285, 105.8542` → chuyển `Đang chờ chuyến mới (Online)` (có thể bật/tắt nút `Offline` ↔ `Online`).
3. Hành khách đặt chuyến đón `21.0285, 105.8542` đến `21.0385, 105.8642` → Matching ghép tài xế, trạng thái chuyển `PENDING → MATCHED`.
4. Tài xế chọn **Từ chối chuyến** (để demo Saga giải phóng tài xế về `AVAILABLE`) hoặc **Nhận chuyến** (`MATCHED → ACCEPTED`) → **Bắt đầu chuyến** (`STARTED`) → **Hoàn thành chuyến** (`COMPLETED`, tính cước Haversine + `PAID_SIMULATED`, tự nhả tài xế về `AVAILABLE`).

## 6. Kiểm thử tự động, mô phỏng & tiêm lỗi

```powershell
# 1. Chạy đủ 15 ca kiểm thử bắt buộc (Mục 9: 8 functional, 2 concurrency, 2 fault/recovery, 2 security, 1 benchmark)
python tests/test_system_e2e.py --gateway http://localhost:3000

# 2. Chạy Driver Simulator & Benchmark hiệu năng qua API Gateway (dùng được cả Local & Cloud)
python scripts/driver_simulator.py --gateway http://localhost:3000 --mode simulate --drivers 5 --duration 15
python scripts/driver_simulator.py --gateway http://localhost:3000 --mode benchmark --drivers 10 --requests 40

# 3. Kiểm tra dữ liệu trên cả 5 database độc lập
python scripts/check_db.py

# 4. Demo tiêm lỗi Kafka (DLQ poison-pill / duplicate deduplication) và tắt/bật matching_worker
python scripts/mock_trip.py --mode poison-pill
python scripts/mock_trip.py --mode duplicate-event
powershell -ExecutionPolicy Bypass -File scripts/fault_injection.ps1
```

Xem thêm chi tiết tại [tests/README.md](tests/README.md), [deploy/README.md](deploy/README.md), [docs/TECHNICAL_HANDOVER.md](docs/TECHNICAL_HANDOVER.md) và [frontend/README.md](frontend/README.md).

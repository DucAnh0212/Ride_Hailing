# Tài liệu bàn giao kỹ thuật — Ride Hailing DS03

## 1. Kiến trúc tách biệt Database-per-Service (Mục 7.2 & Mục 12)
Mỗi business microservice sở hữu cơ sở dữ liệu riêng và **không truy cập trực tiếp database của service khác**:

| Microservice | Engine & Database riêng | Bảng / Collection sở hữu | Giao tiếp liên dịch vụ |
|---|---|---|---|
| `identity-service` | SQL Server — `IdentityDB` | `Users`, `Vehicles` | HTTP REST qua `api-gateway` |
| `booking-service` | SQL Server — `BookingDB` | `Trips`, `Idempotency_Log` | HTTP REST + Kafka (`trip.*`, `driver.matched`, `matching.failed`) |
| `location_service` | MongoDB — `LocationDB` | `LiveLocations`, `DriverRepairs` | HTTP REST công khai qua Gateway + nội bộ `/internal/drivers/*` cho Matching |
| `matching_worker` | MongoDB — `MatchingDB` | `ProcessedTrips`, `FinishedTrips`, `MatchingResults` | Kafka + HTTP REST sang `location_service` và `booking-service` |
| `analytics_worker` | MongoDB — `DataWarehouseDB` | `Fact_Events`, `DeadLetterQueue` | Kafka consumer (toàn bộ 8 topic vòng đời) |

Cả `IdentityDB` và `BookingDB` đều được tự động khởi tạo idempotent bởi chính service sở hữu khi khởi động container (không phụ thuộc seed phá dữ liệu).

## 2. Hợp đồng API & Vòng đời chuyến đi
- Vòng đời chuyến đi: `PENDING → MATCHED → ACCEPTED → STARTED → COMPLETED` (hoặc `CANCELED` khi hành khách hủy, ghép thất bại `TIMEOUT_NO_DRIVERS`, hoặc tài xế từ chối `DRIVER_REJECTED`).
- `PUT /api/trips/{id}/accept`: Chỉ tài xế được gán (`Driver`) gọi khi chuyến ở `MATCHED` → chuyển `ACCEPTED`, bắn `trip.accepted`.
- `PUT /api/trips/{id}/reject`: Chỉ tài xế được gán gọi khi chuyến ở `MATCHED` → chuyển `CANCELED`, bắn `trip.rejected` và sự kiện bù trừ Saga `trip.cancelled` để Matching giải phóng tài xế về `AVAILABLE`.
- `PUT /api/location/status`: Chỉ tài xế gọi qua Gateway để chuyển `AVAILABLE ↔ OFFLINE`; bị chặn (`409`) khi tài xế đang `BUSY` hoặc có `active_trip_id`.
- `X-Correlation-ID` được sinh/truyền qua Gateway tới các service upstream và ghi vào log cùng node + timestamp.

## 3. Khả năng chịu lỗi & Kiểm chứng
- Matching dùng `active_trip_id` + atomic lock (`find_one_and_update` trong `location_service`), `FinishedTrips` tombstone, `MatchingResults` cache, manual Kafka commit offset và vòng đối soát 15 giây với Booking.
- Booking dùng `@Version` Optimistic Locking, `Idempotency_Log`, Kafka retry (`FixedBackOff(1000ms, 3)`) và Dead-Letter Topic (`driver.matched.DLT`, `matching.failed.DLT`).
- Bộ kiểm thử E2E (15 ca chuẩn Mục 9): `tests/test_system_e2e.py`.
- Công cụ mô phỏng & benchmark qua API Gateway (chạy được cả Local lẫn Cloud): `scripts/driver_simulator.py`.
- Công cụ tiêm lỗi Kafka (DLQ & deduplication): `scripts/mock_trip.py` và `scripts/fault_injection.ps1`.

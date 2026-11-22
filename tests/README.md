# Bộ kiểm thử hệ thống Ride Hailing (Mục 9 — Đặc tả DS03)

Bộ kiểm thử [test_system_e2e.py](test_system_e2e.py) dùng thư viện chuẩn Python (`unittest` + `urllib`, không cần cài thêm package ngoài) và phủ đầy đủ **15 ca kiểm thử bắt buộc** theo Mục 9:

| Nhóm | Số ca | Mã ca | Mô tả |
|---|---:|---|---|
| **Functional** | 8 | `F01`–`F08` | Đăng ký/đăng nhập/`/me`, cập nhật GPS & `/location/me`, bật/tắt Online–Offline, tạo chuyến & ghép tự động (`PENDING → MATCHED`), tài xế từ chối chuyến (`reject` + Saga nhả tài xế), vòng đời đầy đủ (`MATCHED → ACCEPTED → STARTED → COMPLETED` + cước + `PAID_SIMULATED`), hành khách hủy chuyến, ghép thất bại không có xe (`TIMEOUT_NO_DRIVERS` Saga) |
| **Concurrency / Conflict** | 2 | `C01`–`C02` | 2 hành khách đặt đồng thời cùng 1 tài xế (chống double-booking bằng atomic lock), xung đột đồng thời `accept` vs `cancel` (Optimistic Locking `@Version`) |
| **Fault & Recovery** | 2 | `R01`–`R02` | Dừng container `matching_worker` giữa luồng → Kafka giữ `trip.requested` → bật lại tự khớp chuyến; tiêm gói tin poison-pill & trùng lặp kiểm tra Analytics DLQ + Deduplication |
| **Security & Invalid Data** | 2 | `S01`–`S02` | `401` thiếu token, `403` sai vai trò / giả mạo `passengerId` / xem chuyến người khác; `400`/`409`/`422` dữ liệu sai, trùng email, đổi trạng thái khi `BUSY` |
| **Performance & Scalability** | 1 | `P01` | Chạy tải đồng thời cập nhật GPS + đặt chuyến qua `scripts/driver_simulator.py --mode benchmark`, xuất throughput (req/s), latency (avg/p50/p95) và tỷ lệ thành công |

## Cách chạy

Đảm bảo Docker stack đang chạy (`docker compose up -d --build`), rồi chạy từ thư mục gốc:

```powershell
# Chạy đủ 15 ca kiểm thử trên local Docker
python tests/test_system_e2e.py --gateway http://localhost:3000

# Chạy trên Cloud VPS từ máy ngoài (bỏ qua 2 ca cần lệnh docker compose local)
python tests/test_system_e2e.py --gateway http://<CLOUD_IP>:3000 --skip-docker-faults
```

Ngoài ra, bộ unit/integration test Java của Booking Service nằm tại `booking_service/src/test/java/com/uber/booking/BookingServiceApplicationTests.java`.

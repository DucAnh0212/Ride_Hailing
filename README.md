# TungNV — Phần Identity Service, API Gateway và Frontend của Tùng

Thư mục này được tách sạch từ dự án **[Ride_Hailing_Main](file:///c:/Users/OS/.gemini/antigravity-ide/scratch/Ride_Hailing_Main)** (nhánh `main`), chỉ bao gồm 3 thành phần thuộc nhiệm vụ của **Tùng**:

1. **`identity-service/`** — Đăng ký, đăng nhập, kiểm tra phiên (`/api/auth/register`, `/login`, `/me`, `/health`), mã hóa mật khẩu Bcrypt, cấp JWT `HS256`, tự động khởi tạo `IdentityDB` (`Users`, `Vehicles`) và ghi log theo `X-Correlation-ID`.
2. **`api-gateway/`** — Cửa ngõ định tuyến duy nhất (`:3000` / `:3100`), xác thực JWT & phân quyền RBAC (`Rider` / `Driver`), gắn `X-Correlation-ID` và proxy tới `identity-service`, `booking-service`, `location_service`.
3. **`frontend/`** — Giao diện Web React + Vite cho **Hành khách** (`PassengerDashboard.jsx`, 16 địa điểm Hà Nội `places.js`, ước tính giá cước) và **Tài xế** (`DriverDashboard.jsx`, `DriverAvailability.jsx`, Online/Offline, Nhận/Từ chối/Bắt đầu/Hoàn thành chuyến).

---

## Cấu trúc thư mục

~~~text
TungNV/
├── identity-service/    # Node.js 22 + Express + mssql + Bcrypt + JWT (IdentityDB)
├── api-gateway/         # Node.js 22 + Express + JWT + RBAC + Correlation-ID
├── frontend/            # React 19 + Vite 8 + Nginx
├── docker-compose.yml   # Compose riêng cho 3 service của Tùng (nối vào network backend của nhóm)
├── .env.example         # Mẫu biến môi trường (không chứa bí mật)
└── README.md            # Hướng dẫn chạy
~~~

---

## Cách 1: Chạy bằng Docker (nối với backend của `Ride_Hailing_Main`)

Đảm bảo hạ tầng backend của nhóm (`sqlserver`, `booking-service`, `location_service`, `matching_worker`, `kafka`, `mongodb`) đã chạy trong `Ride_Hailing_Main`.

1. Tạo file `.env` từ mẫu và điền `DB_PASSWORD` (khớp mật khẩu SQL Server hiện tại) + `JWT_SECRET` (tối thiểu 32 byte):
   ```powershell
   Set-Location "c:\Users\OS\.gemini\antigravity-ide\scratch\TungNV"
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```
2. Build và chạy 3 container của Tùng ở dải cổng riêng (`8088` Web, `3100` Gateway, `3101` Identity) để không xung đột cổng gốc:
   ```powershell
   docker compose -p tungnv up -d --build
   docker compose -p tungnv ps
   ```
3. Mở trình duyệt tại **http://localhost:8088**.

---

## Cách 2: Chạy trực tiếp bằng Node.js 22 (Local Development)

1. Mở 3 terminal trong `TungNV`, tạo `.env` từ `.env.example` trong từng service nếu chạy độc lập:
   * **Terminal 1 — Identity Service (`:3101`):**
     ```powershell
     Set-Location identity-service
     npm ci
     npm start
     ```
   * **Terminal 2 — API Gateway (`:3100`):**
     ```powershell
     Set-Location api-gateway
     npm ci
     npm start
     ```
   * **Terminal 3 — Frontend (`Vite dev`):**
     ```powershell
     Set-Location frontend
     npm ci
     npm run dev
     ```
2. Kiểm tra code Frontend trước khi bàn giao:
   ```powershell
   npm run lint
   npm run build
   ```


# Ride Hailing — bàn giao phần Tùng (P0)

## Chạy trên máy mới

Cần Docker Compose. Node.js 22 cần cho cài dependency và build ngoài Docker.

1. Sao chép `.env.example` thành `.env`, cấu hình mật khẩu SQL Server. Không commit `.env`.
2. Sinh JWT secret bằng `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`, gán vào `JWT_SECRET` trong `.env`. Compose cấp cùng giá trị cho Identity và Gateway. Secret tối thiểu 32 byte; thiếu secret thì ứng dụng từ chối khởi động.
3. Chạy `docker compose up -d sqlserver mongodb zookeeper kafka`, đợi SQL Server sẵn sàng.
4. Chạy `docker compose build identity-service api-gateway frontend`.
5. Chạy `docker compose run --rm --no-deps identity-service npm run db:init`. Lệnh tạo RideHailingDB, Users, Vehicles nếu thiếu và bổ sung IsActive; không xóa dữ liệu hoặc thay ID/role hiện có.
6. Chạy `docker compose up -d --build`. Mở web tại `http://localhost`, Gateway tại `http://localhost:3000`.

Không dùng `data_seed.py` để nâng cấp dữ liệu đang có: script của nhóm có DROP bảng. Nếu chủ động seed lại, phải khởi động lại Identity để bổ sung IsActive. Tài khoản seed thiếu PasswordHash không được đăng nhập; hãy đăng ký tài khoản demo mới qua API/UI. Không tự đặt lại mật khẩu của người dùng cũ.

## Contract tương thích

- Giữ Users.UserID là INT và role DB/API là `Rider` hoặc `Driver`. Đăng ký nhận `passenger`, `rider`, `driver`, không phân biệt hoa thường.
- `/api/auth/register` nhận `{email, password, role, fullName?}`; trường email tiếp tục chứa email hoặc số điện thoại, tối đa 50 ký tự. Mật khẩu mới tối thiểu 8 ký tự, tối đa 72 byte UTF-8. Trả 201 với `{token, user}`; trùng tài khoản trả 409.
- `/api/auth/login` giữ request/response cũ. Sai thông tin, tài khoản vô hiệu hóa hoặc thiếu hash trả 401.
- `GET /api/auth/me` và Gateway `GET /api/users/me` trả `{user}`. Gateway kiểm tra tài khoản còn hoạt động trước mỗi thao tác nghiệp vụ.
- `/api/trips` giữ payload camelCase của Booking. `/api/orders` là alias tương đương. Các route nghiệp vụ yêu cầu `Authorization: Bearer <token>`.
- Hành khách tạo chuyến cho chính mình; Gateway gán passengerId từ danh tính đã xác thực. Gửi ID khác trả 403.
- Danh sách/chi tiết chỉ trả chuyến của hành khách hoặc tài xế được gán. Chỉ tài xế được gán được start/complete. Chủ chuyến hoặc tài xế được gán có thể cancel theo state machine hiện có của Booking.
- `/api/location` chỉ cho Driver POST tọa độ của chính mình; driver_id là số. Không thay đổi schema FastAPI/MongoDB hoặc Kafka event của Đức Anh.
- Correlation ID được truyền bằng `X-Correlation-ID`; đây là ID request, không thay thế correlation_id/trip_id của Kafka.

## Ranh giới truy cập

Compose chỉ bind Identity (3001), Booking (8080), Location (8000) vào 127.0.0.1 để công cụ phát triển trên máy vẫn hoạt động. Các service tiếp tục dùng tên Docker nội bộ. Máy khác phải gọi Gateway.

Các cổng localhost vẫn là đường truy cập tin cậy cho người phát triển; Booking/Location chưa tự kiểm tra JWT. Không dùng cấu hình này như môi trường production đa người dùng. Kiểm tra quyền sở hữu tại Gateway sử dụng GET hiện có của Booking; khi mở rộng luồng gán lại tài xế, Tín cần kiểm tra quyền trong cùng transaction cập nhật ở Booking để loại bỏ race giữa đọc và ghi.

Frontend hành khách đã nối đặt, theo dõi và hủy chuyến thật (P1), khôi phục phiên đăng nhập và xử lý mất kết nối. Màn hình tài xế đã nối gửi vị trí, danh sách/chi tiết chuyến, bắt đầu và hoàn thành chuyến thật; có hồ sơ, lịch sử, tổng cước và thông báo trong trang cho hai vai trò. Matching đã giải phóng BUSY sau hoàn thành/hủy; FE đọc trạng thái thật qua GET /api/location/me. Online/offline, nhận/từ chối riêng và hồ sơ xe còn phụ thuộc API backend. Xem frontend/README.md để chạy và kiểm thử. API mặc định theo hostname của trang web, cổng 3000; VITE_API_GATEWAY_URL là cấu hình tùy chọn tại thời điểm build.

## Kiểm tra bản bàn giao

Bộ test và công cụ mô phỏng chỉ giữ ở máy phát triển, không nằm trong nhánh bàn giao. Có thể kiểm tra build bằng npm ci trong mỗi ứng dụng Node, npm run lint và npm run build trong frontend, cùng docker compose build. Kiểm tra thủ công qua luồng hai tài khoản trong frontend/README.md.

Khi chạy Node ngoài Docker: copy `.env.example` riêng trong mỗi service thành `.env`, điền DB_PASSWORD và JWT_SECRET giống nhau; URL mặc định dùng localhost. Compose dùng `.env` gốc. JWT cũ bị vô hiệu khi đổi secret.

## Git

Nhánh Tùng bàn giao source, manifest/lockfile, Dockerfile, .dockerignore và .env.example. Không đưa bộ test, công cụ mô phỏng, kết quả kiểm thử, bản sao local, .env, node_modules hoặc dist vào commit. Dùng npm ci để cài theo lockfile.

## Matching và Location

Giữ event contract Booking. Matching dùng active_trip_id để chỉ giải phóng đúng chuyến sau hoàn thành/hủy; FinishedTrips chặn ghép lại chuyến kết thúc, MatchingResults lưu kết quả để gửi lại. Đối soát Booking mỗi 15 giây cho reservation có mã chuyến. Không bảo đảm exactly-once xuyên MongoDB/Kafka.

GET /api/location/me qua Gateway trả trạng thái tài xế hiện tại. Endpoint nội bộ GET /api/location/{driver_id} phục vụ Gateway.
Công cụ repair_driver.py chỉ dành cho dữ liệu legacy BUSY không có active_trip_id; dừng Matching, chạy không có --apply để kiểm tra trước, rồi mới áp dụng sau khi Booking xác nhận không còn chuyến đang chạy. Không tự chạy khi khởi động.

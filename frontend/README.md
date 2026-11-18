# Frontend kết nối backend — hành khách và tài xế

## Chạy và cấu hình

Node.js 22: `npm ci`, `npm run dev`. Docker từ thư mục gốc: `docker compose up -d --build --no-deps frontend`.
API mặc định cùng hostname với web, cổng 3000. VITE_API_GATEWAY_URL có thể cấu hình trong frontend/.env (Vite) hoặc Docker build argument. Không gọi SQL Server, MongoDB hoặc Kafka trực tiếp từ trình duyệt.

## Demo hoàn toàn qua giao diện

1. Mở http://localhost ở hai phiên riêng biệt: trình duyệt thường cho hành khách, cửa sổ ẩn danh hoặc trình duyệt khác cho tài xế. Hai tab cùng trình duyệt chia sẻ token nên không dùng để đăng nhập hai tài khoản khác nhau.
2. Đăng ký tài khoản mới cho từng vai trò. Thông tin tài khoản hiển thị từ Identity trong mục Thông tin tài khoản.
3. Trên màn hình tài xế, nhập vĩ độ/kinh độ rồi Gửi vị trí. Hoặc Lấy vị trí thiết bị, cấp quyền GPS, kiểm tra tọa độ rồi Gửi vị trí. GPS chỉ điền form, không tự gửi vị trí khi chưa xác nhận. Cần HTTPS hoặc localhost để dùng GPS trên trình duyệt.
4. Trên màn hình hành khách, nhập điểm đón gần tọa độ tài xế và điểm đến khác; nhấn Đặt xe. Matching chọn tài xế khả dụng theo thuật toán hiện có, không bảo đảm chọn tài xế demo nếu có nhiều tài xế khác ở gần.
5. Hai bên thấy cùng mã chuyến, trạng thái Đã có tài xế. Backend hiện tự ACCEPTED sau ghép xe, nên FE không có bước nhận/từ chối riêng.
6. Tài xế nhấn Bắt đầu chuyến rồi Xác nhận. Hành khách thấy Đang di chuyển.
7. Tài xế nhấn Hoàn thành chuyến rồi Xác nhận. Hành khách thấy Đã hoàn thành, cước và PAID_SIMULATED. Tài xế trở về chờ; hóa đơn xem trong lịch sử. Tổng cước tài xế là tổng fareAmount của các chuyến COMPLETED, không phải số tiền ròng được trả hay thu nhập riêng hôm nay.
8. Để kiểm tra hủy: hành khách chọn chuyến đang hoạt động, Hủy chuyến → Xác nhận hủy. Tài xế nhận trạng thái Đã hủy qua polling và mất nút bắt đầu/hoàn thành. Hành khách không có nút hoàn thành chuyến.
9. Bộ lọc Tất cả / Đang hoạt động / Lịch sử chỉ lọc dữ liệu thuộc tài khoản hiện tại. Chọn chuyến để đọc chi tiết mới nhất. Reload khôi phục phiên và tải lại chuyến từ backend.

## API đang sử dụng

| Tác vụ | API |
| --- | --- |
| Xác thực và hồ sơ hiện tại | POST /api/auth/register, POST /api/auth/login, GET /api/auth/me |
| Danh sách và chi tiết được phân quyền | GET /api/trips, GET /api/trips/{id} |
| Hành khách đặt/hủy | POST /api/trips, PUT /api/trips/{id}/cancel |
| Tài xế bắt đầu/hoàn thành | PUT /api/trips/{id}/start, PUT /api/trips/{id}/complete |
| Gửi vị trí tài xế | POST /api/location |

Giữ UserID số, role Rider/Driver, passengerId/driverId chuỗi trong Booking và driver_id số trong Location. API client gắn JWT, xử lý 401/403/lỗi mạng. Giao diện không tự xác nhận thao tác ghi trước phản hồi backend.

## Đồng bộ và xử lý lỗi

- Poll mỗi 2 giây khi có chuyến hoạt động; tài xế rảnh mỗi 5 giây để nhận phân công; hành khách không có chuyến hoạt động mỗi 15 giây. Có nút Tải lại thủ công.
- Dừng tải khi tab bị ẩn; quay lại tab sẽ đọc ngay. Hủy request đọc khi rời dashboard hoặc đăng xuất.
- Thông báo trong trang dựa trên thay đổi trạng thái từ backend, không phải Kafka consumer, push notification hay SSE/WebSocket.
- Giữ trạng thái cuối cùng kèm lỗi nếu mất mạng. Không tự retry POST/PUT. Sau lỗi thao tác ghi, tải lại để đối chiếu kết quả.
- POST mất phản hồi: khóa đặt lại, lưu cờ chưa xác nhận theo user trong sessionStorage; chỉ cho đặt lại sau khi kiểm tra danh sách và xác nhận thủ công.
- Chặn bấm lặp tại client, bỏ qua phản hồi đọc cũ khi có thao tác ghi mới. Không tuyên bố chống trùng nhiều tab/client vì Booking chưa có idempotency key cho tạo chuyến.

## Kiểm tra bản bàn giao

Chạy npm run lint và npm run build. Bộ test tự động giữ riêng tại máy phát triển, không được đưa lên nhánh này.

## Các phần cần backend trước khi nối FE

Đây là phần chưa triển khai, không phải endpoint đã tồn tại:

- Đã có GET /api/location/me qua Gateway, chỉ cho tài xế đọc chính mình. POST vị trí không tự mở khóa BUSY. Online/offline và lọc loại xe còn chờ backend.
- Matching đã giải phóng BUSY theo active_trip_id sau hoàn thành/hủy. FE tự trở về chờ; hóa đơn giữ trong lịch sử. Bản sao rollback và bằng chứng kiểm thử giữ riêng ở máy phát triển.
- Tín và Đức Anh: thống nhất trạng thái chờ xác nhận, API/event nhận/từ chối, tìm lại tài xế sau từ chối. Không dùng API start thay cho accept.
- Tùng phối hợp Tín: API thông tin tài xế/xe của chuyến với kiểm tra chủ sở hữu; hiện FE chỉ hiển thị ID được Booking trả về. Bảng Vehicles có dữ liệu nhưng chưa có API tương ứng để FE truy xuất an toàn.
- Tín: chống tạo trùng phía server, kiểm tra quyền cùng transaction cập nhật. Gateway hiện kiểm tra quyền qua API đọc trước khi ghi.
- Sau khi contract ổn định: SSE/WebSocket/thông báo backend. Không tích hợp Kafka vào trình duyệt.

Giữ contract Booking; bản bàn giao kèm cập nhật vòng đời Matching và API đọc trạng thái Location.

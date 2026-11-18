# Ride Hailing — Hướng dẫn cài đặt và sử dụng

Hệ thống đặt xe phân tán cho hành khách và tài xế. Tài liệu này dành cho người chạy demo và thành viên tiếp nhận mã nguồn trên nhánh **Tùng**.

Bản README kỹ thuật trước đây được giữ nguyên tại [docs/TECHNICAL_HANDOVER.md](docs/TECHNICAL_HANDOVER.md).

## 1. Chức năng và công nghệ

Hành khách đăng ký, đăng nhập, đặt xe bằng tọa độ, theo dõi và hủy chuyến. Tài xế gửi vị trí, xem chuyến được giao, bắt đầu và hoàn thành chuyến. Sau khi kết thúc hoặc hủy, tài xế quay về trạng thái chờ; hóa đơn và lịch sử vẫn được lưu.

| Thành viên | Phụ trách | Công nghệ |
|---|---|---|
| Tùng | Identity, API Gateway, Frontend | Node.js, Express, JWT, React, Vite |
| Tín | Booking/Trip, Saga, vòng đời chuyến, tính cước | Java 17, Spring Boot, SQL Server, Kafka |
| Đức Anh | Location, Matching, Analytics, hạ tầng, seed | Python, FastAPI, MongoDB, Kafka, Docker Compose |

~~~text
Trình duyệt -> API Gateway -> Identity / Booking / Location
Identity / Booking -> SQL Server
Location / Matching -> MongoDB RideHailingDB
Booking -> Kafka -> Matching -> Kafka -> Booking
Booking -> Kafka -> Matching (giải phóng tài xế)
Kafka -> Analytics -> MongoDB DataWarehouseDB
~~~

Matching tìm tài xế AVAILABLE trong bán kính tối đa 3 km, xét tối đa 5 ứng viên gần nhất rồi xếp hạng theo ước lượng khoảng cách/ETA. Booking tự chuyển chuyến sang ACCEPTED sau khi ghép; chưa có bước tài xế nhận/từ chối riêng.

## 2. Chuẩn bị

- Git để tải mã nguồn.
- Docker Desktop đang chạy Linux containers, có Docker Compose.
- Trình duyệt hiện đại; dùng hai phiên riêng cho hành khách và tài xế.
- Node.js 22 nếu phát triển ngoài Docker. Không cần cài Java/Python riêng khi chạy toàn bộ bằng Docker.
- Internet để tải image và dependency lần đầu.

Các lệnh bên dưới dùng PowerShell trên Windows, không yêu cầu gọi pwsh hoặc dùng SkipHttpErrorCheck.

~~~powershell
git --version
docker version
docker compose version
~~~

docker version phải có phần Server kết nối thành công. Nếu báo dockerDesktopLinuxEngine không tồn tại, mở Docker Desktop và đợi engine sẵn sàng.

Các cổng cần trống: 80, 3000, 3001, 8080, 8000, 14333, 27017, 9092, 2181. Không chạy hai bản dự án đồng thời vì Compose dùng tên container cố định.

## 3. Tải mã nguồn và cấu hình

### 3.1. Tải 

Nếu máy chưa có dự án:

~~~powershell
git clone --branch "Tùng" https://github.com/DucAnh0212/Ride_Hailing.git
Set-Location Ride_Hailing
~~~

Nếu đã có dự án với thay đổi chưa commit, lưu công việc trước khi cập nhật/chuyển nhánh. Không dùng git reset --hard để cập nhật.

Tất cả lệnh Docker dưới đây chạy từ thư mục chứa docker-compose.yml.

### 3.2. Tạo .env

~~~powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
notepad .env
~~~

Điền SQL_SERVER_PASSWORD và JWT_SECRET. Mật khẩu SQL phải đáp ứng chính sách độ mạnh của SQL Server. JWT_SECRET tối thiểu 32 byte; Compose cấp cùng giá trị cho Identity và Gateway.

Sinh secret bằng PowerShell, không cần cài Node:

~~~powershell
$secretBytes = New-Object byte[] 32
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$generator.GetBytes($secretBytes)
$generator.Dispose()
[Convert]::ToBase64String($secretBytes)
~~~

Chép kết quả vào dòng JWT_SECRET= trong .env. Không chia sẻ hoặc commit .env.

Nếu đã có database từ lần chạy trước, giữ mật khẩu SQL hiện có: sửa biến môi trường không tự đổi mật khẩu trong volume đang lưu dữ liệu.

Kiểm tra cấu hình mà không in bí mật:

~~~powershell
docker compose config --quiet
~~~

## 4. Khởi động lần đầu

### 4.1. Chạy hạ tầng

~~~powershell
docker compose up -d sqlserver mongodb zookeeper kafka
docker compose ps
docker compose logs --tail 40 sqlserver
~~~

Đợi SQL Server báo sẵn sàng nhận kết nối. Trạng thái container Up chưa bảo đảm ứng dụng bên trong đã sẵn sàng.

Kiểm tra Kafka:

~~~powershell
docker compose exec -T kafka kafka-topics --bootstrap-server kafka:29092 --list
~~~

Máy mới có thể chưa có topic; lệnh phải kết thúc không báo lỗi kết nối. Nếu chưa sẵn sàng, đợi rồi thử lại.

### 4.2. Build và khởi tạo database

~~~powershell
docker compose build identity-service api-gateway frontend
docker compose run --rm --no-deps identity-service npm run db:init
~~~

Chỉ tiếp tục khi db:init thành công. Lệnh tạo RideHailingDB và các bảng Identity còn thiếu, bổ sung IsActive, không xóa dữ liệu cũ. Booking tạo/cập nhật bảng của nó khi khởi động.

~~~powershell
docker compose up -d --build
docker compose ps
docker compose logs --tail 30 identity-service booking-service matching_worker
~~~

Mở **http://localhost**. Nếu chưa kết nối được, kiểm tra trạng thái và log trước khi thử lại.

Không cần chạy data_seed.py để demo. Script seed có thao tác DROP bảng; không dùng trên dữ liệu cần giữ. Tài khoản seed thiếu PasswordHash không đăng nhập được; hãy đăng ký tài khoản mới qua giao diện.

## 5. Demo một chuyến hoàn chỉnh

### 5.1. Tạo tài khoản hành khách và tài xế

1. Mở http://localhost trong trình duyệt thường.
2. Chọn Chưa có tài khoản? Đăng ký.
3. Nhập số điện thoại/email chưa sử dụng, mật khẩu ít nhất 8 ký tự, chọn Hành khách rồi nhấn Tạo tài khoản.
4. Mở cửa sổ ẩn danh hoặc trình duyệt khác, đăng ký tài khoản thứ hai với vai trò Tài xế.

Không dùng hai tab cùng phiên trình duyệt để đăng nhập hai vai trò vì token được lưu chung trong localStorage. Tài khoản chỉ xem được các chuyến thuộc quyền của mình.

### 5.2. Tài xế gửi vị trí

| Trường | Giá trị minh họa |
|---|---|
| Vĩ độ tài xế | 21.0285 |
| Kinh độ tài xế | 105.8542 |

Nhấn Gửi vị trí. Đợi thông báo đã gửi và trạng thái Đang chờ chuyến mới.

Hoặc nhấn Lấy vị trí thiết bị, cấp quyền GPS, kiểm tra tọa độ rồi nhấn Gửi vị trí. Nút GPS chỉ điền form, không tự gửi. GPS trình duyệt cần localhost hoặc HTTPS; nếu không cấp quyền thì nhập thủ công.

Nhập số thập phân theo ví dụ, không dùng dấu phân cách hàng nghìn. Trình duyệt có thể hiển thị dấu phẩy thay dấu chấm theo thiết lập vùng.

### 5.3. Hành khách đặt xe

| Trường | Giá trị minh họa |
|---|---|
| Điểm đón Vĩ độ | 21.0285 |
| Điểm đón Kinh độ | 105.8542 |
| Điểm đến Vĩ độ | 21.0385 |
| Điểm đến Kinh độ | 105.8642 |

Nhấn Đặt xe một lần. Đợi Đang tìm tài xế chuyển thành Đã có tài xế. Kiểm tra cùng mã chuyến trên hai giao diện.

Nếu nhiều tài xế khác cũng AVAILABLE ở gần, Matching có thể chọn tài xế khác. Để demo đúng hai tài khoản, dùng tọa độ khu vực chưa có tài xế khác và đặt điểm đón gần vị trí tài xế vừa gửi.

### 5.4. Bắt đầu và hoàn thành

1. Tài xế nhấn Bắt đầu chuyến rồi Xác nhận.
2. Hai bên thấy Đang di chuyển.
3. Tài xế nhấn Hoàn thành chuyến rồi Xác nhận.
4. Hành khách thấy Đã hoàn thành, cước và Đã thanh toán (giả lập).
5. Tài xế trở về chờ khi backend xử lý xong sự kiện. Xem hóa đơn trong Lịch sử.

Tổng cước tài xế là tổng fareAmount của các chuyến COMPLETED; không phải tiền chuyển vào ví và không chỉ tính hôm nay.

## 6. Hủy chuyến và chạy chuyến tiếp theo

### Hủy chuyến

Hành khách chọn chuyến đang hoạt động, nhấn Hủy chuyến rồi Xác nhận hủy. Đợi backend xác nhận Đã hủy. Tài xế không còn nút bắt đầu/hoàn thành và quay về chờ. Chuyến đã hoàn thành không hủy được.

### Hai chuyến liên tiếp với cùng tài xế

1. Hoàn thành chuyến thứ nhất.
2. Đợi tài xế hiển thị Đang chờ chuyến mới.
3. Nếu đang xem hóa đơn cũ, nhấn Quay về chờ chuyến.
4. Hành khách đặt chuyến mới gần vị trí tài xế đã gửi.
5. Kiểm tra mã chuyến mới và tài xế được gán, rồi bắt đầu/hoàn thành tiếp.

Không cần đăng ký lại hoặc reset tài xế. Khi tài xế thực sự di chuyển, cần gửi lại vị trí: hệ thống chưa tự cập nhật GPS nền hoặc tự chuyển tọa độ tài xế tới điểm đến.

## 7. Trạng thái và dữ liệu thật/giả lập

| Trạng thái chuyến | Hiển thị/ý nghĩa |
|---|---|
| PENDING | Đang tìm tài xế |
| ACCEPTED | Đã có tài xế |
| STARTED | Đang di chuyển |
| COMPLETED | Đã hoàn thành |
| CANCELED | Đã hủy, do người dùng hoặc ghép thất bại |

| Trạng thái tài xế | Ý nghĩa |
|---|---|
| AVAILABLE | Có thể nhận chuyến |
| BUSY | Đang được giữ cho một chuyến |
| OFFLINE | Không nhận chuyến; API đọc cũng dùng trạng thái này khi chưa có vị trí |

| Dữ liệu | Nguồn và giới hạn |
|---|---|
| Tài khoản, chuyến, lịch sử, trạng thái | API thật, lưu SQL Server/MongoDB |
| Ghép xe và sự kiện kết thúc | Booking/Matching trao đổi Kafka thật |
| Tọa độ trong tài liệu | Ví dụ nhập tay, không phải GPS thật |
| Vị trí thiết bị | GPS trình duyệt; lưu khi nhấn Gửi vị trí |
| Cước | Backend tính: 15.000 đồng mở cửa + 10.000 đồng/km theo Haversine đường chim bay |
| ETA | Ước lượng, không có dữ liệu giao thông thực tế |
| PAID_SIMULATED | Thanh toán giả lập; không trừ tiền, không gọi cổng thanh toán |
| Seed và dữ liệu test cũ | Tổng hợp phục vụ demo, có thể còn trong database local |

FE cập nhật bằng polling: khoảng 2 giây khi có chuyến hoạt động, 5 giây khi tài xế chờ và 15 giây khi hành khách không có chuyến. Trạng thái nhận chuyến của tài xế được đọc riêng khoảng 2 giây. Tab ẩn tạm dừng tải và đọc lại khi được mở.

Matching gắn active_trip_id để chỉ giải phóng đúng chuyến, có đối soát Booking mỗi 15 giây cho reservation có mã chuyến. BUSY legacy không có mã chuyến cần kiểm tra riêng, không mở khóa hàng loạt.

## 8. Địa chỉ truy cập và API

| Thành phần | Địa chỉ trên máy Docker |
|---|---|
| Web | http://localhost |
| Gateway | http://localhost:3000 |
| Identity nội bộ | http://127.0.0.1:3001 |
| Booking nội bộ | http://127.0.0.1:8080 |
| Location nội bộ | http://127.0.0.1:8000 |
| SQL Server | localhost,14333 |
| MongoDB | localhost:27017 |
| Kafka | localhost:9092 |
| Zookeeper | localhost:2181 |

Người dùng đi qua Web/Gateway. Booking và Location chưa tự kiểm tra JWT; cổng nội bộ dành cho phát triển trên máy. Compose phục vụ demo local, chưa phải cấu hình triển khai Internet; database/broker vẫn publish cổng trên host.

| Chức năng | API qua Gateway |
|---|---|
| Đăng ký/đăng nhập | POST /api/auth/register, POST /api/auth/login |
| Tài khoản hiện tại | GET /api/auth/me |
| Danh sách/tạo chuyến | GET /api/trips, POST /api/trips |
| Chi tiết | GET /api/trips/{id} |
| Bắt đầu/hoàn thành/hủy | PUT /api/trips/{id}/start, /complete, /cancel |
| Gửi vị trí | POST /api/location |
| Trạng thái tài xế hiện tại | GET /api/location/me |

API nghiệp vụ yêu cầu Bearer token. /api/orders là alias của /api/trips. Người dùng không cần gọi các API này trực tiếp để demo.

## 9. Vận hành thường ngày

Chạy lại:

~~~powershell
docker compose up -d
docker compose ps
~~~

Sau khi khởi động Docker, kiểm tra Kafka sẵn sàng theo mục 4 trước khi demo.

Xem log:

~~~powershell
docker compose logs --tail 80 api-gateway identity-service
docker compose logs --tail 80 booking-service matching_worker location_service
~~~

Tạm dừng, giữ container và dữ liệu:

~~~powershell
docker compose stop
~~~

Gỡ container/network, giữ named volumes:

~~~powershell
docker compose down
~~~

Không thêm -v nếu muốn giữ tài khoản/chuyến: tùy chọn này xóa volumes SQL/Mongo. Kafka/Zookeeper hiện chưa khai báo named volumes trong Compose, vì vậy không coi down/recreate là cơ chế bảo toàn lịch sử sự kiện; ưu tiên stop khi chỉ tạm dừng demo.

Sau khi cập nhật mã, build lại dịch vụ thay đổi:

~~~powershell
docker compose up -d --build --no-deps frontend api-gateway
~~~

## 10. Xử lý lỗi thường gặp

| Hiện tượng | Hướng xử lý |
|---|---|
| Không kết nối Docker engine | Mở Docker Desktop, dùng Linux containers, đợi docker version có Server |
| Thiếu JWT_SECRET | Điền secret ít nhất 32 byte trong .env gốc |
| db:init lỗi | Kiểm tra SQL sẵn sàng, mật khẩu, volume cũ; sửa cấu hình rồi chạy lại |
| Không mở được Web | Kiểm tra docker compose ps, port 80 và frontend |
| Đăng ký trùng | Dùng email/số điện thoại khác; API trả 409 |
| Seed không đăng nhập được | Tạo tài khoản mới qua UI; seed có thể thiếu PasswordHash |
| 401 / phiên hết hạn | Đăng nhập lại; đổi JWT_SECRET làm token cũ mất hiệu lực |
| Tìm xe mãi không xong | Xem log Booking/Matching/Kafka, xác nhận tài xế AVAILABLE và gần điểm đón |
| Không có tài xế, chuyến bị hủy | Gửi vị trí tài xế khả dụng gần điểm đón rồi tạo chuyến mới |
| BUSY sau khi kết thúc | Đợi event/đối soát, xem log Matching; không ép status trong MongoDB |
| GPS không hoạt động | Dùng localhost/HTTPS, cấp quyền hoặc nhập tọa độ thủ công |
| Báo lỗi sau Đặt xe | Tải lại danh sách để xác định chuyến đã tạo chưa; không bấm lặp liên tục |
| Không nhận pwsh / SkipHttpErrorCheck | Các bước tài liệu này không cần hai lệnh/tùy chọn đó |
| npm audit cảnh báo | Không tự dùng npm audit fix --force; kiểm tra ảnh hưởng major version trước |

Nếu Kafka đã sẵn sàng nhưng consumer chưa xử lý sau khi khởi động Docker, xem log rồi khởi động lại:

~~~powershell
docker compose restart matching_worker analytics_worker
docker compose logs --tail 40 matching_worker
~~~

Với BUSY legacy không có active_trip_id, người quản trị cần kiểm tra Booking và dùng repair_driver.py theo bản kỹ thuật. Không áp dụng cho tài xế đang có chuyến hoạt động.

## 11. Phát triển và kiểm tra bản bàn giao

Chạy Frontend ngoài Docker, backend vẫn phải hoạt động:

~~~powershell
Set-Location frontend
npm ci
npm run dev
~~~

Mở URL Vite in trong terminal. VITE_API_GATEWAY_URL tùy chọn trỏ tới Gateway; mặc định dùng hostname của Web và cổng 3000. Khi build Docker với URL riêng, truyền build argument VITE_API_GATEWAY_URL.

Kiểm tra:

~~~powershell
npm run lint
npm run build
~~~

Bộ test, ảnh/log test và công cụ mô phỏng chỉ giữ tại máy phát triển, không có trong cây mã bàn giao. Không chạy npm test trên bản clone nếu chưa được cung cấp bộ test riêng.

Tài liệu mô tả code đã commit trên nhánh Tùng. Bản vá dependency hoặc thử nghiệm chưa commit ở máy cá nhân không được coi là đã bàn giao.

## 12. Giới hạn hiện tại

- Chưa có bản đồ/lộ trình giao thông, GPS nền hoặc thanh toán thật.
- Chưa có nút nhận/từ chối chuyến riêng, online/offline trên FE hoặc hồ sơ xe đầy đủ.
- Endpoint AVAILABLE/OFFLINE chỉ dùng nội bộ và từ chối sửa tài xế BUSY/có reservation.
- Chưa bảo đảm exactly-once xuyên MongoDB/Kafka hoặc chống đặt trùng từ mọi tab/client.
- Tổng cước/ETA/khoảng cách phục vụ demo; không phải báo cáo doanh thu thực tế.

## 13. Cấu trúc dự án và tài liệu

~~~text
frontend/                    Giao diện hành khách và tài xế
api-gateway/                 Phân quyền và chuyển tiếp API
identity-service/            Đăng ký, đăng nhập, schema Identity
booking_service/             Vòng đời chuyến, Saga, tính cước
matching_location_service/   Location, Matching, giải phóng tài xế
analytics_service/           Thu thập sự kiện vào MongoDB
data_seed.py                 Seed minh họa, có thể xóa dữ liệu cũ
docker-compose.yml           Hạ tầng và ứng dụng
README.md                    Hướng dẫn chính (cài đặt và sử dụng)
docs/TECHNICAL_HANDOVER.md    README kỹ thuật trước đây, giữ nguyên nội dung
~~~

Xem thêm [chi tiết Frontend](frontend/README.md) và [bàn giao kỹ thuật](docs/TECHNICAL_HANDOVER.md).

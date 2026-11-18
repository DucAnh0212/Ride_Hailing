# Data Mining — Khai phá dữ liệu hệ thống Ride Hailing

Thư mục phục vụ phân tích, khai phá dữ liệu (Data Mining) và học máy (Machine Learning) dựa trên dữ liệu thu thập từ Data Warehouse (`DataWarehouseDB`), MongoDB (`RideHailingDB`) và SQL Server.

## 1. Cấu trúc thư mục

~~~text
data_mining/
├── datasets/        Tập dữ liệu trích xuất phục vụ huấn luyện và phân tích
├── notebooks/       Jupyter Notebook phân tích khám phá dữ liệu (EDA) và thực nghiệm mô hình
├── scripts/         Mã nguồn tiền xử lý dữ liệu, trích xuất đặc trưng và pipeline khai phá
└── README.md        Tài liệu hướng dẫn module Data Mining
~~~

## 2. Nguồn dữ liệu khai thác

- **DataWarehouseDB (MongoDB)**: Bảng `Fact_Events` lưu trữ sự kiện vòng đời chuyến (`trip.requested`, `driver.matched`, `trip.started`, `trip.completed`, `trip.cancelled`).
- **RideHailingDB (MongoDB)**: Vị trí và trạng thái tài xế thời gian thực (`drivers`).
- **SQL Server**: Lịch sử người dùng (`Users`) và chi tiết chuyến đi (`Trips`).

## 3. Các bài toán khai phá dữ liệu tiềm năng

1. **Phân cụm điểm đón/trả (Hotspot Clustering)**: Áp dụng DBSCAN hoặc K-Means dựa trên tọa độ GPS để phát hiện các khu vực có mật độ đặt xe cao theo thời gian.
2. **Dự báo nhu cầu đặt xe (Demand Forecasting)**: Dự đoán số lượng yêu cầu đặt chuyến theo khu vực và khung giờ (sáng, trưa, tan tầm) để điều phối tài xế chủ động.
3. **Phân nhóm khách hàng & tài xế (Customer/Driver Segmentation)**: Phân tích thói quen di chuyển, mức chi trả, tỷ lệ hủy chuyến để tối ưu trải nghiệm.
4. **Phát hiện bất thường (Anomaly Detection)**: Nhận diện các cuốc xe bất thường về thời gian, khoảng cách hoặc cước phí.

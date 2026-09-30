# Sử dụng ảnh Python tối giản để nhẹ Docker
FROM python:3.11-slim

# Thiết lập thư mục làm việc bên trong container
WORKDIR /app

# Copy file requirements.txt để cài đặt thư viện trước (tận dụng cache của Docker)
COPY requirements.txt .

# Cài đặt các thư viện cần thiết. Đặc biệt cần gcc để cài confluent-kafka
RUN apt-get update && apt-get install -y librdkafka-dev gcc \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove -y gcc \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy toàn bộ mã nguồn (.env, .py) vào container
COPY . .

# Mặc định mở cổng 8000 (Dành cho location_api)
EXPOSE 8000

# Lệnh khởi chạy mặc định (Sẽ chạy Location API). 
# Với Geo Matcher, chúng ta sẽ ghi đè lệnh này trong docker-compose.yml sau.
CMD ["uvicorn", "location_api:app", "--host", "0.0.0.0", "--port", "8000"]
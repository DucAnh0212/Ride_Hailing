# Hướng dẫn triển khai Docker trên Cloud / VPS

## Yêu cầu máy chủ
- Linux VM / Cloud VPS (Ubuntu 22.04+, AWS EC2, GCP Compute Engine, DigitalOcean...).
- RAM tối thiểu **4 GB** (khuyến nghị **8 GB** cho SQL Server 2022 + Kafka + Spring Boot).
- Docker Engine & Docker Compose plugin v2.20+.
- Firewall / Security Group chỉ mở cổng **80** (Frontend) và **3000** (API Gateway) — hoặc đặt reverse proxy HTTPS phía trước (Caddy/Nginx) và chỉ mở cổng **443**.

## Các bước triển khai
```bash
git clone https://github.com/DucAnh0212/Ride_Hailing.git
cd Ride_Hailing
cp .env.example .env
# Điền SQL_SERVER_PASSWORD mạnh và sinh JWT_SECRET >= 32 bytes:
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env

# Chạy với file override Cloud (khóa SQL Server, MongoDB, Kafka, Zookeeper về 127.0.0.1)
docker compose -f docker-compose.yml -f deploy/docker-compose.cloud.yml up -d --build
docker compose ps
```

## Kiểm tra & tải giả lập từ xa (không cần mở cổng DB/Kafka)
```bash
# Kiểm tra toàn bộ 15 ca kiểm thử E2E qua API Gateway công khai
python3 tests/test_system_e2e.py --gateway http://<CLOUD_IP>:3000 --skip-docker-faults

# Chạy driver simulator & benchmark qua API Gateway công khai
python3 scripts/driver_simulator.py --gateway http://<CLOUD_IP>:3000 --mode benchmark --drivers 10 --requests 30
```

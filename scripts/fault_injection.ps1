# Live Fault Injection Demo Script (PDF Section 7.4 & Section 11)
# Demonstrates stopping matching_worker mid-flow, buffering messages in Kafka, and automatic recovery upon restart.
param(
    [string]$GatewayUrl = "http://localhost:3000"
)

$ErrorActionPreference = "Stop"
Write-Host "=== 1. Checking current stack health ==="
docker compose ps

Write-Host "`n=== 2. Stopping matching_worker to simulate service crash ==="
docker compose stop matching_worker
docker compose ps matching_worker

Write-Host "`n=== 3. Running automated fault-recovery check (trip queued in Kafka while worker is down) ==="
Write-Host "You can now book a trip on http://localhost (it will stay PENDING in Kafka), then press Enter to restart matching_worker..."
Read-Host

Write-Host "`n=== 4. Restarting matching_worker and observing automatic Kafka recovery ==="
docker compose start matching_worker
Start-Sleep -Seconds 4
docker compose logs --tail 25 matching_worker

Write-Host "`n=== 5. Checking Analytics DataWarehouseDB Fact_Events ==="
docker compose exec -T mongodb mongosh --quiet --eval "db.getSiblingDB('DataWarehouseDB').Fact_Events.aggregate([{\$group:{_id:'\$event_type', count:{\$sum:1}}}]).toArray()"

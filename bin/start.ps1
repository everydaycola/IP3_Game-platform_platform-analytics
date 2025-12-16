# Platform Analytics - Auto Setup Script
# Run this after 'docker-compose down -v' to automatically set everything up

Write-Host "Starting platform-analytics stack..." -ForegroundColor Cyan
Write-Host "============================================================"

# Start Elasticsearch first
Write-Host "`nStarting Elasticsearch..." -ForegroundColor Yellow
docker-compose up -d elasticsearch

# Wait for Elasticsearch to be healthy
Write-Host "Waiting for Elasticsearch health check (max 5 minutes)..." -ForegroundColor Yellow
$timeout = 300
$elapsed = 0
while ($elapsed -lt $timeout) {
    $status = docker-compose ps elasticsearch --format json | ConvertFrom-Json
    if ($status.Health -eq "healthy") {
        break
    }
    Start-Sleep -Seconds 5
    $elapsed += 5
    if ($elapsed % 30 -eq 0) {
        Write-Host "   Still waiting... ($elapsed sec)" -ForegroundColor Gray
    }
}

if ($elapsed -ge $timeout) {
    Write-Host "Elasticsearch health check timed out" -ForegroundColor Red
    exit 1
}

Write-Host "Elasticsearch is healthy!" -ForegroundColor Green

# Run setup
Write-Host "`nRunning setup (templates + user passwords)..." -ForegroundColor Yellow
docker-compose --profile=setup run --rm setup
if ($LASTEXITCODE -ne 0) {
    Write-Host "Setup failed" -ForegroundColor Red
    exit 1
}

# Start all services
Write-Host "`nStarting all services..." -ForegroundColor Yellow
docker-compose up -d

# Wait for RabbitMQ to be ready (needs more time to create exchange)
Write-Host "`nWaiting for RabbitMQ to initialize (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Setup RabbitMQ bindings
Write-Host "`nSetting up RabbitMQ queue bindings..." -ForegroundColor Yellow
python setup/setup_rabbitmq_bindings.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "RabbitMQ setup failed (continuing anyway)" -ForegroundColor Yellow
}

# Wait for Kibana to be ready
Write-Host "`nWaiting for Kibana to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Create data view in Kibana
Write-Host "`nCreating Kibana data view..." -ForegroundColor Yellow
python setup/create_data_view.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Data view creation failed (continuing anyway)" -ForegroundColor Yellow
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Platform Analytics is ready!" -ForegroundColor Green
Write-Host "`nAccess points:" -ForegroundColor Cyan
Write-Host "   - Kibana: http://localhost:5601"
Write-Host "   - Elasticsearch: http://localhost:9200"
Write-Host "   - RabbitMQ Management: http://localhost:15672"
Write-Host "   - Credentials: elastic / changeme (admin / admin for RabbitMQ)"
Write-Host "`nData view 'platform-events-*' is ready in Kibana!" -ForegroundColor Cyan
Write-Host "You can now create your dashboards manually in Kibana." -ForegroundColor Cyan
Write-Host "`nGenerate test data with:" -ForegroundColor Cyan
Write-Host '   echo "1" | python .\scripts\generate_revenue_data.py'
Write-Host "============================================================" -ForegroundColor Cyan

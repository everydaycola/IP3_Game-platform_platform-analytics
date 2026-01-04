# Platform Analytics - Auto Setup Script
# Run this after 'docker-compose down -v' to automatically set everything up

Write-Host "Starting platform-analytics stack..." -ForegroundColor Cyan
Write-Host "============================================================"

Write-Host "Resetting stack (down -v) to start from zero..." -ForegroundColor Yellow
docker-compose down -v --remove-orphans

# Install Python requirements
Write-Host "`nInstalling Python requirements..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install requirements (continuing anyway)" -ForegroundColor Yellow
}

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

# Generate Revenue data (purchase_made, payment_made, gamePage_visit events)
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Generating Revenue data..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

python setup/generate_revenue_data.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Revenue data generation failed" -ForegroundColor Red
}

Write-Host ""
Write-Host "Deploying User Engagement & Retention dashboard (transforms + pipeline)..." -ForegroundColor Cyan

# Run the retention dashboard setup script (transforms, enrich policy, pipeline)
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
& (Join-Path $repoRoot "bin\setup_retention_dashboard.ps1")

# Also run the Python retention transforms setup (creates additional transforms with player_id.keyword fix)
Write-Host "`nCreating retention transforms (DAU/WAU/MAU/Cohorts)..." -ForegroundColor Yellow
echo "" | python setup/create_retention_transforms.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Retention transforms creation had issues (continuing anyway)" -ForegroundColor Yellow
}

# Generate Game Performance data (game_started, game_ended, game_abandoned events)
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Generating Game Performance data..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

# Run the game performance data generator (uses RabbitMQ, generates 60 days of sessions)
# Auto-select option 1 (60 days) for startup
"1" | python setup/generate_game_performance_data.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Game performance data generation failed" -ForegroundColor Red
}

# Wait for Logstash to process events (need more time for all game sessions)
Write-Host "`nWaiting for Logstash to process events (30 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 30

# Import dashboards from exported NDJSON files using Kibana Saved Objects API
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Importing Kibana Dashboards from exports..." -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan

$kibanaUrl = "http://localhost:5601"
$kibanaAuth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("elastic:changeme"))
$exportPath = Join-Path $repoRoot "kibana\exports"

# Import each dashboard NDJSON file
$dashboardFiles = @(
    @{ file = "revenue.ndjson"; name = "Revenue Dashboard" },
    @{ file = "user_engagement_retention.ndjson"; name = "User Engagement & Retention Dashboard" },
    @{ file = "game_performance.ndjson"; name = "Game Performance Dashboard" }
)

foreach ($dashboard in $dashboardFiles) {
    $filePath = Join-Path $exportPath $dashboard.file
    if (Test-Path $filePath) {
        Write-Host "  Importing $($dashboard.name)..." -ForegroundColor Gray
        try {
            $fileContent = Get-Content -Path $filePath -Raw -Encoding UTF8
            $boundary = "----WebKitFormBoundary" + [System.Guid]::NewGuid().ToString("N").Substring(0,16)
            
            $bodyLines = @(
                "--$boundary",
                "Content-Disposition: form-data; name=`"file`"; filename=`"$($dashboard.file)`"",
                "Content-Type: application/ndjson",
                "",
                $fileContent,
                "--$boundary--",
                ""
            )
            $body = $bodyLines -join "`r`n"
            
            $response = Invoke-RestMethod -Uri "$kibanaUrl/api/saved_objects/_import?overwrite=true" `
                -Method POST `
                -Headers @{
                    "Authorization" = "Basic $kibanaAuth"
                    "kbn-xsrf" = "true"
                    "Content-Type" = "multipart/form-data; boundary=$boundary"
                } `
                -Body $body `
                -ErrorAction Stop
            
            if ($response.success) {
                Write-Host "    ✅ $($dashboard.name) imported ($($response.successCount) objects)" -ForegroundColor Green
            } else {
                Write-Host "    ⚠️  $($dashboard.name) import had issues" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "    ❌ Failed to import $($dashboard.name): $_" -ForegroundColor Red
        }
    } else {
        Write-Host "  ⚠️  File not found: $filePath" -ForegroundColor Yellow
    }
}

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "Platform Analytics is ready!" -ForegroundColor Green
Write-Host "`nAccess points:" -ForegroundColor Cyan
Write-Host "   - Kibana: http://localhost:5601"
Write-Host "   - Elasticsearch: http://localhost:9200"
Write-Host "   - RabbitMQ Management: http://localhost:15672"
Write-Host "   - Credentials: elastic / changeme (admin / admin for RabbitMQ)"
Write-Host "`nDashboards:" -ForegroundColor Yellow
Write-Host "   1. Revenue Dashboard (Opbrengsten Dashboard)" -ForegroundColor Cyan
Write-Host "      http://localhost:5601/app/dashboards#/view/revenue-dashboard"
Write-Host "      - Total Revenue, Avg Purchase Value, Transactions"
Write-Host "      - Revenue Evolution, Top Games, Payment Methods"
Write-Host "`n   2. User Engagement & Retention Dashboard" -ForegroundColor Cyan
Write-Host "      http://localhost:5601/app/dashboards#/list (search for 'User Engagement')"
Write-Host "      - DAU/WAU/MAU, Avg Session Duration"
Write-Host "      - D1/D7/D30 Retention Metrics"
Write-Host "      - Activity Trends and Retention Analysis"
Write-Host "`n   3. Game Performance Dashboard" -ForegroundColor Cyan
Write-Host "      http://localhost:5601/app/dashboards#/list (search for 'Game Performance')"
Write-Host "      - Totale sessies, Unieke spelers, Gem. sessieduur"
Write-Host "      - Voltooide games, Verlaten games"
Write-Host "      - Sessies per spel, Evolutie over tijd"
Write-Host "`nGenerate additional test data:" -ForegroundColor Yellow
Write-Host "   - Revenue: python .\\setup\\generate_revenue_data.py"
Write-Host "   - Game Performance: python .\\setup\\generate_game_performance_data.py"
Write-Host "============================================================" -ForegroundColor Cyan

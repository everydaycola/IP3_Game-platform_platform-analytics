# GitLab CI/CD Quick Setup Script
# Run dit script om snel de pipeline te configureren

Write-Host "=== GitLab CI/CD Setup voor Platform Analytics ===" -ForegroundColor Cyan
Write-Host ""

# Check of we in de juiste directory zijn
if (!(Test-Path ".gitlab-ci.yml")) {
    Write-Host "ERROR: .gitlab-ci.yml niet gevonden!" -ForegroundColor Red
    Write-Host "Zorg dat je in de project root directory bent." -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] GitLab CI configuratie gevonden" -ForegroundColor Green

# Check Docker
Write-Host "`nControleren Docker installatie..." -ForegroundColor Yellow
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Docker is geinstalleerd" -ForegroundColor Green
    docker --version
} else {
    Write-Host "[FAIL] Docker niet gevonden!" -ForegroundColor Red
    Write-Host "  Installeer Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
}

# Check Python
Write-Host "`nControleren Python installatie..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Python is geinstalleerd" -ForegroundColor Green
    python --version
} else {
    Write-Host "[FAIL] Python niet gevonden!" -ForegroundColor Red
}

# Check Git
Write-Host "`nControleren Git installatie..." -ForegroundColor Yellow
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Git is geinstalleerd" -ForegroundColor Green
    
    # Check Git remote
    $gitRemote = git remote get-url origin 2>$null
    if ($gitRemote) {
        Write-Host "[OK] Git remote configured: $gitRemote" -ForegroundColor Green
        
        if ($gitRemote -match "gitlab") {
            Write-Host "[OK] GitLab repository gedetecteerd!" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Geen GitLab repository gedetecteerd" -ForegroundColor Yellow
            Write-Host "  Zorg dat je repository op GitLab staat" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARN] Geen Git remote geconfigureerd" -ForegroundColor Yellow
    }
} else {
    Write-Host "[FAIL] Git niet gevonden!" -ForegroundColor Red
}

# Creeer .env bestand als het niet bestaat
Write-Host "`nControleren environment configuratie..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    Write-Host "Creeren .env bestand van .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "[OK] .env bestand aangemaakt" -ForegroundColor Green
    Write-Host "  [WARN] Pas de waarden aan in .env voor je specifieke setup!" -ForegroundColor Yellow
} else {
    Write-Host "[OK] .env bestand bestaat al" -ForegroundColor Green
}

# Test basis Python dependencies
Write-Host "`nInstalleren Python dependencies..." -ForegroundColor Yellow
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt --quiet
    Write-Host "[OK] Python dependencies geinstalleerd" -ForegroundColor Green
} else {
    Write-Host "[WARN] requirements.txt niet gevonden" -ForegroundColor Yellow
}

# Test lokale Docker builds
Write-Host "`n=== Test Docker Builds ===" -ForegroundColor Cyan
Write-Host "Wil je de Docker images lokaal bouwen om de configuratie te testen? (j/n)" -ForegroundColor Yellow
$response = Read-Host

if ($response -eq "j" -or $response -eq "J") {
    Write-Host "`nBouwen Elasticsearch image..." -ForegroundColor Yellow
    docker build -t platform-analytics/elasticsearch:test --build-arg ELASTIC_VERSION=8.15.3 ./elasticsearch
    
    Write-Host "`nBouwen Kibana image..." -ForegroundColor Yellow
    docker build -t platform-analytics/kibana:test --build-arg ELASTIC_VERSION=8.15.3 ./kibana
    
    Write-Host "`nBouwen Logstash image..." -ForegroundColor Yellow
    docker build -t platform-analytics/logstash:test --build-arg ELASTIC_VERSION=8.15.3 ./logstash
    
    Write-Host "`nBouwen Setup image..." -ForegroundColor Yellow
    docker build -t platform-analytics/setup:test -f setup/Dockerfile .
    
    Write-Host "`n[OK] Alle images succesvol gebouwd!" -ForegroundColor Green
}

# Samenvatting
Write-Host "`n=== Setup Samenvatting ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Volgende stappen om de CI/CD pipeline te activeren:" -ForegroundColor White
Write-Host ""
Write-Host "1. Push je code naar GitLab:" -ForegroundColor Yellow
Write-Host "   git add ." -ForegroundColor Gray
Write-Host "   git commit -m 'Add CI/CD pipeline'" -ForegroundColor Gray
Write-Host "   git push origin main" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Configureer GitLab CI/CD Variables:" -ForegroundColor Yellow
Write-Host "   Settings → CI/CD → Variables" -ForegroundColor Gray
Write-Host "   - ELASTIC_PASSWORD" -ForegroundColor Gray
Write-Host "   - KIBANA_SYSTEM_PASSWORD" -ForegroundColor Gray
Write-Host "   - LOGSTASH_INTERNAL_PASSWORD" -ForegroundColor Gray
Write-Host "   - RABBITMQ_USER" -ForegroundColor Gray
Write-Host "   - RABBITMQ_PASSWORD" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Activeer GitLab Container Registry:" -ForegroundColor Yellow
Write-Host "   Settings → General → Visibility → Container Registry (enabled)" -ForegroundColor Gray
Write-Host ""
Write-Host "4. Configureer GitLab Runner (als self-hosted):" -ForegroundColor Yellow
Write-Host "   Settings → CI/CD → Runners" -ForegroundColor Gray
Write-Host "   Tags: docker, development, staging, production" -ForegroundColor Gray
Write-Host ""
Write-Host "5. Bekijk de pipeline:" -ForegroundColor Yellow
Write-Host "   CI/CD → Pipelines" -ForegroundColor Gray
Write-Host ""
Write-Host "Meer info: docs/CICD_SETUP.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "[OK] Setup compleet! Veel succes met je CI/CD pipeline!" -ForegroundColor Green

# Platform Analytics - Quick Start Guide

## Automatic Setup (Recommended)

After running `docker-compose down -v`, simply use the automated startup script:

```powershell
.\bin\start.ps1
```

This script will:
1. ✅ Start Elasticsearch
2. ✅ Wait for health check
3. ✅ Run setup (templates + user passwords)
4. ✅ Start all services

**That's it!** Everything is configured automatically.

## Manual Setup (If needed)

If you prefer to run commands manually:

```powershell
# 1. Remove everything
docker-compose down -v

# 2. Start Elasticsearch
docker-compose up -d elasticsearch

# 3. Wait for Elasticsearch (90 seconds)
Start-Sleep -Seconds 90

# 4. Run setup
docker-compose build setup
docker-compose --profile=setup run --rm setup

# 5. Start all services
docker-compose up -d
```

## Access Points

- **Kibana**: http://localhost:5601
- **Elasticsearch**: http://localhost:9200
- **Credentials**: `elastic` / `changeme`

## Generate Test Data

```powershell
# Quick test (10 transactions)
echo "1" | python .\scripts\generate_revenue_data.py

# 30 days historical data
echo "2" | python .\scripts\generate_revenue_data.py
```

## Troubleshooting

### Elasticsearch shows enrollment tokens
If you see enrollment tokens instead of starting normally, the auto-configuration is still enabled. Run:
```powershell
docker-compose down -v
.\bin\start.ps1
```

### Kibana authentication errors
The setup script automatically configures the `kibana_system` password. If you still see authentication errors:
```powershell
docker-compose restart kibana
```

### Health check timeout
If the health check takes longer than 5 minutes, check Elasticsearch logs:
```powershell
docker-compose logs elasticsearch
```

## What the Setup Does

The `start.ps1` script and setup container:
- Disables Elasticsearch SSL and auto-configuration
- Creates index templates for platform events
- Sets passwords for `kibana_system` user
- Creates initial indices with proper mappings
- Ensures all services start in correct order

## Daily Usage

**Starting:**
```powershell
docker-compose up -d
```

**Stopping:**
```powershell
docker-compose down
```

**Full reset (removes all data):**
```powershell
docker-compose down -v
.\bin\start.ps1
```

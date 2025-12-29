# Platform Analytics Dashboard

## 🎯 Project Overview

Analytics platform for gaming platform with two comprehensive dashboards:
- **Revenue Dashboard** - Monetization and transaction analytics
- **User Retention & Engagement Dashboard** - User behavior, retention, and churn analysis

**Tech Stack:** Elasticsearch 8.11, Kibana 8.11, Logstash 8.11, RabbitMQ 3.12, Python 
 

---

## 🚀 Quick Start
## Automatic Setup (Recommended)

### First Time Setup

```powershell
# 1. Start all services with automated setup
.\bin\start.ps1

# 2. Wait for completion (~2 minutes)
# The script automatically:
#   - Starts Elasticsearch
#   - Waits for health check
#   - Configures templates and passwords
#   - Starts all services (Kibana, Logstash, RabbitMQ)

# 3. Access Kibana
# URL: http://localhost:5601
# Username: elastic
# Password: changeme
```

### Generate Data

```powershell
# Revenue Dashboard - 30 days of transaction data
python scripts/generate_revenue_data.py
# Choose option 2: "30 days historical data"

# Retention Dashboard - 60 days of user behavior data
python scripts/generate_retention_data.py
# Choose option 2: "60 days (1,400 users, realistic profiles)"
```

### Create Dashboards

```powershell
# Revenue Dashboard
python scripts/create_revenue_dashboard.py

# User Retention & Engagement Dashboard
python scripts/create_combined_dashboard.py
```

---

## 📊 Dashboard 1: Revenue Analytics

**Purpose:** Track monetization, transactions, and revenue metrics

### Key Metrics (KPIs)
- **Total Revenue**: €44,837 (30 days)
- **Total Transactions**: 36,945 transactions
- **Average Transaction Value**: €1.23
- **Revenue per User**: €32.54
- **Active Paying Users**: 1,376 users

### Visualizations
- Revenue over time (daily trend)
- Top 5 games by revenue
- Payment method distribution (Credit Card, PayPal, iDEAL)
- Transaction volume by hour
- Revenue by game category

### Data Generation
- Realistic transaction patterns
- 6 games with varying popularity
- Multiple payment methods
- Peak hours: 14:00-22:00
- Weekend spikes

---

## 📊 Dashboard 2: User Retention & Engagement

**Purpose:** Understand user behavior, retention patterns, and churn risk

### Key Metrics (KPIs)

**Activity Metrics:**
- **DAU** (Daily Active Users): 474 avg
- **WAU** (Weekly Active Users): 1,003 avg
- **MAU** (Monthly Active Users): 963 avg
- **Avg Sessions/User**: 34.5 per month

**Engagement Metrics:**
- **Total Sessions**: Sum of daily sessions
- **Unique Games**: 6 games on platform
- **Avg Days Active**: 7 days (median per user)
- **Total Users Tracked**: 1,376 users

**Stickiness:**
- Formula: (Avg DAU / MAU) × 100%
- Current: ~46.7% (Excellent engagement)

**Retention Analysis:**
- **D1 Retention**: ~31% (users returning after 1 day)
- **D7 Retention**: ~52% (users returning after 7 days)
- **D30 Retention**: ~75% (users returning after 30 days)

### Visualizations
- DAU Trend (daily active users over time)
- WAU Trend (weekly active users)
- Retention Activity by Cohort (weekly cohorts)
- Sessions per Day (total platform sessions)
- Active Users by Hour (0-23, sorted numerically)
- Monthly Sessions Trend

### Data Architecture

```
Event Generation (generate_retention_data.py)
    ↓
RabbitMQ (session_started events)
    ↓
Logstash (processing & routing)
    ↓
Elasticsearch (platform-events-* indices)
    ↓
8 Transforms (real-time metrics calculation)
    ├── DAU (daily-active-users)
    ├── WAU (weekly-active-users)
    ├── MAU (monthly-active-users)
    ├── User Sessions (per-user aggregation)
    ├── Cohorts (new user tracking)
    ├── Hourly Activity (peak hours)
    ├── Retention Rates (D1/D7/D30)
    └── Churn Analysis (30+ days inactive)
    ↓
Kibana Dashboard (auto-refresh every 1-10 minutes)
```

### User Behavior Profiles
Data generation simulates 4 realistic user types:
- **Super Active** (10%): Daily players, 5-10 sessions/day, 90% retention
- **Regular** (30%): 3-5 times/week, 3-7 sessions/day, 70% retention
- **Casual** (40%): 1-2 times/week, 1-4 sessions/day, 50% retention
- **Churned** (20%): Played once/few times, then stopped

---

## 🔧 Technical Details

### Services
- **Elasticsearch** (port 9200): Data storage and aggregation engine
- **Kibana** (port 5601): Visualization and dashboard interface
- **Logstash** (port 5000): Event processing pipeline
- **RabbitMQ** (port 5672, 15672): Message queue for event ingestion

### Data Flow
1. **Event Generation**: Python scripts simulate user behavior or transactions
2. **Message Queue**: Events sent to RabbitMQ exchanges
3. **Processing**: Logstash consumes from RabbitMQ, enriches, and indexes to Elasticsearch
4. **Aggregation**: Elasticsearch transforms calculate real-time metrics (runs every 1-10 minutes)
5. **Visualization**: Kibana dashboards query indices and display insights

### Key Scripts

| Script | Purpose |
|--------|---------|
| `bin/start.ps1` | Automated startup with health checks |
| `scripts/generate_revenue_data.py` | Generate transaction events |
| `scripts/generate_retention_data.py` | Generate user session events |
| `scripts/create_revenue_dashboard.py` | Create revenue dashboard |
| `scripts/create_retention_dashboard.py` | Create retention dashboard |
| `setup/setup_elasticsearch.py` | Configure ES templates and transforms |

### Indices Created
- `platform-events-*`: Raw events (purchases, sessions)
- `retention-metrics-daily-active-users`: DAU calculations
- `retention-metrics-weekly-active-users`: WAU calculations
- `retention-metrics-monthly-active-users`: MAU calculations
- `retention-metrics-user-sessions`: Per-user session aggregates
- `retention-metrics-cohorts`: New user cohorts
- `retention-metrics-hourly-activity`: Hourly patterns
- `retention-metrics-retention-rates`: Retention cohort tracking
- `retention-metrics-churn-analysis`: Churn risk analysis

---

## 🎓 ISM Project Requirements - ✅ Complete

### Activity Metrics
- ✅ **DAU** - Average daily active users
- ✅ **WAU** - Average weekly active users
- ✅ **MAU** - Average monthly active users

### Engagement Metrics
- ✅ **Sessions per User** - Average per month
- ✅ **Total Sessions** - Daily platform activity
- ✅ **Unique Games** - Games available on platform
- ✅ **Days Active** - Per-user activity tracking

### Advanced Metrics
- ✅ **Stickiness** - (Avg DAU / MAU) × 100%
- ✅ **Retention** - D1/D7/D30 cohort-based
- ✅ **Churn Analysis** - 30+ days inactive tracking
- ✅ **Activity Patterns** - Hourly and weekly trends

### Management Dashboard Features
- ✅ Clean KPI visualizations (no technical jargon)
- ✅ Proper aggregation types (avg for behavior, sum for totals, median for typical user)
- ✅ Correct intervals (1d daily, 1w weekly, 1M monthly)
- ✅ Management-friendly labels ("Avg Daily Active Users", not "max daily_active_users")
- ✅ No hardcoded values - all metrics from live data
- ✅ Real-time updates via Elasticsearch transforms

---

## 📖 Documentation

### Main Documentation
- **Project Architecture**: [docs/RETENTION_ARCHITECTURE.md](docs/RETENTION_ARCHITECTURE.md)

### Technical Guides
- **Event Specification**: [docs/EVENT_SPECIFICATION.md](docs/EVENT_SPECIFICATION.md)
- **ISB Deployment**: [docs/ISB_DEPLOYMENT.md](docs/ISB_DEPLOYMENT.md)

---

## 🔄 Daily Workflow

### Starting the Platform
```powershell
docker-compose up -d
```

### Stopping the Platform
```powershell
docker-compose down
```

### Full Reset (removes all data)
```powershell
docker-compose down -v
.\bin\start.ps1
```

### Check Service Health
```powershell
# Elasticsearch
curl http://localhost:9200/_cluster/health

# RabbitMQ Management UI
# http://localhost:15672 (guest/guest)

# Kibana
# http://localhost:5601
```

### View Logs
```powershell
docker-compose logs -f elasticsearch
docker-compose logs -f kibana
docker-compose logs -f logstash
```

---

## 🐛 Troubleshooting

### Elasticsearch shows enrollment tokens
Auto-configuration is enabled. Reset:
```powershell
docker-compose down -v
.\bin\start.ps1
```

### Kibana authentication errors
```powershell
docker-compose restart kibana
```

### Transforms not running
Check transforms in Kibana Dev Tools:
```json
GET _transform/_stats
```

Restart a transform:
```json
POST _transform/transform-daily-active-users/_start
```

### No data in dashboards
1. Check if data was generated:
```powershell
curl -u elastic:changeme "http://localhost:9200/platform-events-*/_count"
```

2. Check if transforms are running:
```json
GET _transform/_stats
```

<<<<<<< README.md
3. Regenerate data if needed:
```powershell
python scripts/generate_retention_data.py
```

### Port conflicts
If ports 5601, 9200, 5672, or 5000 are in use:
```powershell
# Check what's using the port
netstat -ano | findstr :5601

# Stop the process or change ports in docker-compose.yml
```

---

## 🎯 Key Learning Outcomes (ISM Project)

1. **Data Pipeline Design**: Event-driven architecture with message queues
2. **Real-time Analytics**: Elasticsearch transforms for continuous aggregation
3. **Dashboard Design**: Management-focused KPI visualization
4. **Retention Analysis**: Cohort-based retention tracking (D1/D7/D30)
5. **User Segmentation**: Behavioral profiling and churn prediction
6. **Aggregation Strategies**: Correct use of avg, sum, median, cardinality
7. **Time-series Analysis**: Proper interval handling (1d, 1w, 1M)

---

## 📞 Access Information

**Kibana Dashboard:**
- URL: http://localhost:5601
- Username: `elastic`
- Password: `changeme`

**Elasticsearch API:**
- URL: http://localhost:9200
- Auth: Same as above

**RabbitMQ Management:**
- URL: http://localhost:15672
- Username: `guest`
- Password: `guest`

---

## ✅ Project Status

**Status:** ✅ **COMPLETE**

All ISM requirements implemented:
- ✅ Revenue Dashboard (monetization tracking)
- ✅ Retention Dashboard (user engagement, retention, churn)
- ✅ Real-time data pipeline (RabbitMQ → Logstash → Elasticsearch)
- ✅ Automated transforms (DAU, WAU, MAU, Retention, Churn)
- ✅ Management-ready visualizations (no technical jargon)
- ✅ Comprehensive documentation
- ✅ Automated setup scripts

**Data Summary:**
- 60 days of user behavior data (1,376 users)
- 30 days of revenue data (36,945 transactions, €44,837)
- 8 retention metrics calculated in real-time
- 14 visualizations across 2 dashboards

## CI/CD Pipeline

This project includes a complete GitLab CI/CD pipeline with automated testing, building, and deployment.

### Quick Setup

```powershell
.\bin\setup-cicd.ps1
```

### Features

- 🔍 **Automated Testing**: Python linting, formatting checks, and unit tests
- 🐳 **Docker Builds**: Automatic building and pushing to GitLab Container Registry
- 🚀 **Multi-Environment Deployment**:
  - Development (auto on `develop` branch)
  - Staging (auto on `main` branch)
  - Production (manual approval required)
- 📦 **Container Registry**: All images stored in GitLab Container Registry
- 🔒 **Security**: Secrets management via GitLab CI/CD Variables

### Pipeline Stages

1. **Lint** → Code quality checks
2. **Test** → Unit tests with coverage
3. **Build** → Build and push Docker images
4. **Deploy** → Automated deployment to environments

### Documentation

See [docs/CICD_SETUP.md](docs/CICD_SETUP.md) for detailed CI/CD setup instructions.

### Container Registry Images

```bash
# Login
docker login registry.gitlab.com

# Pull images
docker pull registry.gitlab.com/your-username/platform-analytics/elasticsearch:latest
docker pull registry.gitlab.com/your-username/platform-analytics/kibana:latest
docker pull registry.gitlab.com/your-username/platform-analytics/logstash:latest
```

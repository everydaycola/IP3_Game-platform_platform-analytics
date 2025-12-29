# User Retention & Engagement Dashboard - Complete Guide

## 📊 Overview

This dashboard provides **platform-level** insights into user retention and engagement, enabling management to make strategic decisions about growth, marketing, and product optimization.

This is an **ISM (Information Systems Management)** project focused on **decision-support**, not DevOps.

---

## 🎯 Business Context

### Management Questions Answered

1. **Are users coming back?** → D1/D7/D30 Retention Metrics
2. **How engaged are users?** → DAU, MAU, Stickiness, Sessions per User
3. **When do users churn?** → Churn Rate, Last Activity Analysis
4. **Is the platform growing?** → New User Trends, DAU Growth
5. **When should we market?** → Peak Activity Hours, Day of Week Patterns

### Key Decisions Enabled

- **Product**: Identify features that drive retention
- **Marketing**: Target re-engagement campaigns at churning users
- **Operations**: Scale infrastructure during peak hours
- **Growth**: Optimize onboarding to improve D1 retention

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Generation                          │
│  scripts/generate_retention_data.py                          │
│  • Simulates user behavior profiles                          │
│  • Creates realistic retention curves                        │
│  • Sends session_started events to RabbitMQ                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Event Pipeline                            │
│  RabbitMQ → Logstash → Elasticsearch                         │
│  • Events: session_started with player_id, game_id           │
│  • Index: platform-events-*                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Elasticsearch Transforms                        │
│  setup/create_retention_transforms.py                        │
│  • DAU/WAU/MAU aggregations                                  │
│  • Per-user session metrics                                  │
│  • Retention cohorts                                         │
│  • Hourly activity patterns                                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Kibana Dashboard                           │
│  setup/create_retention_dashboard.py                         │
│  • KPIs: DAU, MAU, Stickiness, Retention, Churn             │
│  • Visualizations: Trends, Distributions, Patterns           │
│  • Filters: Time range (7d/30d/90d)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

### 1. Infrastructure Running
```powershell
# Check all services are up
docker-compose ps

# Should see: elasticsearch, kibana, logstash, rabbitmq (all healthy)
```

### 2. Source Data Exists
```powershell
# Generate retention data
python scripts/generate_retention_data.py

# Choose option 2 (60 days, 20 users/day) - RECOMMENDED
```

### 3. Verify Data in Elasticsearch
```powershell
# Check events were indexed
curl -u elastic:changeme http://localhost:9200/platform-events-*/_count

# Should return count > 0
```

---

## 🚀 Quick Start (3 Steps)

### Step 1: Generate Retention Data
```powershell
python scripts/generate_retention_data.py
# Choose: 2 (Medium dataset - 60 days)
# Wait: ~2-3 minutes to complete
```

**What this does:**
- Creates realistic user behavior patterns
- Simulates power users, regular users, casual users, churned users
- Generates D1 > D7 > D30 retention curves
- Sends ~50,000+ events to RabbitMQ

**Expected output:**
```
📊 Statistics:
   Total users created: 1200
   Total sessions: 45,000
   
📊 Retention Metrics Preview:
   D1  Retention:  48.5% (582/1200 users)
   D7  Retention:  35.2% (422/1200 users)
   D30 Retention:  22.1% (265/1200 users)
```

---

### Step 2: Create Elasticsearch Transforms
```powershell
python setup/create_retention_transforms.py
```

**What this does:**
- Creates 4 continuous transforms:
  1. **Daily Active Users**: Aggregates sessions by day
  2. **User Session Metrics**: Per-user engagement stats
  3. **Retention Cohorts**: Groups users by registration week
  4. **Hourly Activity**: Usage patterns by hour/day

**Expected output:**
```
📊 Transform Creation Summary:
  ✅ Daily Active Users
  ✅ User Session Metrics
  ✅ Retention Cohorts
  ✅ Hourly Activity
  
  4/4 transforms created successfully
```

**Verify transforms are running:**
```powershell
# Via API
curl -u elastic:changeme http://localhost:9200/_transform/_stats?pretty

# Via Kibana UI
# Go to: Stack Management → Transforms
```

---

### Step 3: Create Dashboard in Kibana

```powershell
python setup/create_retention_dashboard.py
```

**What this does:**
- Creates data views for metric indices
- Creates reusable visualizations
- Generates dashboard export file

**Then manually build dashboard:**

1. **Open Kibana**: http://localhost:5601 (elastic / changeme)

2. **Go to Analytics → Dashboard → Create dashboard**

3. **Add Visualizations** (use Lens):

#### KPI Row (Metrics)

| Metric | Data View | Configuration |
|--------|-----------|---------------|
| **DAU** | metrics-daily-active-users* | Last value of `daily_active_users` |
| **MAU** | metrics-user-sessions* | Unique count of `player_id` (last 30d) |
| **Stickiness** | Combined | Formula: `DAU / MAU` |
| **Avg Sessions** | metrics-user-sessions* | Average of `total_sessions` |
| **D1 Retention** | metrics-user-sessions* | Custom calculation (see below) |
| **D7 Retention** | metrics-user-sessions* | Custom calculation (see below) |
| **D30 Retention** | metrics-user-sessions* | Custom calculation (see below) |
| **Churn Rate** | metrics-user-sessions* | % where `now() - last_session > 30d` |

#### Main Charts

1. **DAU Trend** (Line Chart)
   - Data view: `metrics-daily-active-users*`
   - X-axis: `date` (date histogram, daily)
   - Y-axis: `daily_active_users` (average)
   - Chart type: Line

2. **Sessions Distribution** (Bar Chart)
   - Data view: `metrics-user-sessions*`
   - X-axis: `total_sessions` (histogram, interval 5)
   - Y-axis: Count of users
   - Chart type: Bar (vertical)

3. **Activity by Hour** (Heatmap)
   - Data view: `metrics-hourly-activity*`
   - X-axis: `hour_of_day`
   - Y-axis: `day_of_week`
   - Metric: `session_count` (sum)
   - Chart type: Heatmap

4. **Total Sessions Over Time** (Area)
   - Data view: `metrics-daily-active-users*`
   - X-axis: `date`
   - Y-axis: `total_sessions` (sum)
   - Chart type: Area

#### Retention Calculations (Advanced)

For **D1, D7, D30 retention**, use Elasticsearch queries or Kibana formulas:

**D1 Retention Example (using filters):**
```
Cohort: Users where first_session was yesterday
Returned: Users in cohort where last_session was within 24h of first_session
D1 Retention = Returned / Cohort * 100
```

**Or use a scripted field in Kibana:**
```javascript
// D1 Retention
if (doc['last_session'].value - doc['first_session'].value <= 86400000) {
  return 1; // Retained
} else {
  return 0; // Churned
}
```

---

## 📊 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│                    User Retention & Engagement                       │
├──────┬──────┬────────┬──────────┬──────┬──────┬──────┬────────────┤
│ DAU  │ MAU  │Sticki- │  Avg     │  D1  │  D7  │  D30 │   Churn    │
│ 245  │ 980  │  25%   │Sessions  │ 48%  │ 35%  │ 22%  │   Rate     │
│      │      │        │   3.2    │      │      │      │   18%      │
├──────────────────────────────────┬──────────────────────────────────┤
│                                   │                                  │
│     📈 DAU Trend Over Time       │    📊 Sessions Distribution      │
│     (Line chart showing           │    (Bar chart: users by          │
│      daily growth)                │     session count)               │
│                                   │                                  │
├──────────────────────────────────┴──────────────────────────────────┤
│                                                                       │
│                🕐 Activity by Hour of Day & Day of Week              │
│                (Heatmap showing peak usage times)                    │
│                                                                       │
├──────────────────────────────────┬───────────────────────────────────┤
│                                   │                                   │
│  📅 Weekly Cohort Retention      │    ⚠️ Churn Risk Analysis        │
│  (Retention rates by signup week) │    (Users inactive > 21 days)    │
│                                   │                                   │
└──────────────────────────────────┴───────────────────────────────────┘
```

---

## 🎯 Management Insights

### 1. DAU (Daily Active Users)
**What it means:** Number of unique users active each day

**Management decision:**
- Growing DAU = successful growth
- Declining DAU = need intervention (marketing, new features)
- Flat DAU = mature product, focus on monetization

### 2. MAU (Monthly Active Users)
**What it means:** Number of unique users active in last 30 days

**Management decision:**
- MAU growth = platform reach expanding
- MAU/user acquisition cost = marketing ROI

### 3. Stickiness (DAU/MAU Ratio)
**What it means:** Percentage of monthly users who are active daily

**Management decision:**
- >20% = strong engagement (good)
- 10-20% = moderate engagement
- <10% = weak engagement (need gamification, features)

**Industry benchmarks:**
- Social apps: 50-60%
- Gaming platforms: 15-25%
- Casual games: 5-15%

### 4. D1 Retention
**What it means:** % of new users who return the next day

**Management decision:**
- <40% = poor onboarding, fix first-time experience
- 40-60% = acceptable
- >60% = excellent onboarding

**Actions:**
- Improve tutorial
- Add welcome rewards
- Personalize first session

### 5. D7 Retention
**What it means:** % of users still active after 7 days

**Management decision:**
- <30% = users losing interest quickly
- 30-50% = normal for most platforms
- >50% = strong product-market fit

**Actions:**
- Add progression systems
- Implement push notifications
- Create weekly events

### 6. D30 Retention
**What it means:** % of users still active after 30 days

**Management decision:**
- <15% = poor long-term value
- 15-30% = sustainable
- >30% = excellent LTV potential

**Actions:**
- Add social features (guilds, leaderboards)
- Create endgame content
- Implement retention campaigns

### 7. Churn Rate
**What it means:** % of users who haven't returned in 30+ days

**Management decision:**
- >30% = urgent problem
- 15-30% = monitor closely
- <15% = healthy

**Actions:**
- Re-engagement email campaigns
- Win-back offers
- Survey churned users

---

## 🔧 Troubleshooting

### No Data in Dashboard

**Problem:** Dashboard shows "No results found"

**Solution:**
```powershell
# 1. Check if events exist
curl -u elastic:changeme http://localhost:9200/platform-events-*/_count

# 2. Check if transforms ran
curl -u elastic:changeme http://localhost:9200/metrics-daily-active-users/_count

# 3. Check transform status
curl -u elastic:changeme http://localhost:9200/_transform/_stats?pretty

# 4. If transforms stopped, restart them
curl -X POST -u elastic:changeme http://localhost:9200/_transform/transform-daily-active-users/_start
```

---

### Transforms Failed

**Problem:** Transform shows "failed" status

**Solution:**
```powershell
# Delete and recreate
python setup/create_retention_transforms.py

# Check logs
docker-compose logs elasticsearch | grep -i transform
```

---

### Data Looks Wrong

**Problem:** Retention metrics seem unrealistic

**Solution:**
```powershell
# Regenerate with correct parameters
python scripts/generate_retention_data.py

# Clear old data first
curl -X POST -u elastic:changeme "http://localhost:9200/platform-events-*/_delete_by_query" \
  -H "Content-Type: application/json" \
  -d '{"query": {"match_all": {}}}'

# Stop transforms, delete indices, restart transforms
```

---

## 📚 Additional Resources

### API References
- [Elasticsearch Transform API](https://www.elastic.co/guide/en/elasticsearch/reference/current/transform-apis.html)
- [Kibana Lens](https://www.elastic.co/guide/en/kibana/current/lens.html)
- [Kibana Saved Objects API](https://www.elastic.co/guide/en/kibana/current/saved-objects-api.html)

### Academic References
- Retention metrics for SaaS: [Retention Science](https://retentionscience.com/)
- Cohort analysis: [Amplitude Guide](https://amplitude.com/blog/cohort-analysis)

---

## ✅ Acceptance Criteria Validation

From user story:

### ✅ D1 Retention Calculation
- Cohort: Users active on day X
- Retention: Users from cohort active on day X+1
- Dashboard shows: `D1 Retention = (Active on D1 / Cohort Size) * 100`

### ✅ D7 Retention Calculation
- Cohort: Users active on day X
- Retention: Users from cohort active within 7 days
- Dashboard shows: `D7 Retention = (Active within 7d / Cohort Size) * 100`

### ✅ Churn Detection
- User with no sessions for 30+ days = churned
- Dashboard shows: `Churn Rate = (Inactive 30d+ / Total Users) * 100`

### ✅ Stickiness Display
- Dashboard shows: `Stickiness = DAU / MAU * 100`

### ✅ Period Filter
- Dashboard has time range selector: 7d / 30d / 90d / Custom
- All metrics recalculate for selected period

---

## 🎓 ISM (Information Systems Management) Focus

This dashboard embodies ISM principles:

1. **Business Alignment**: Every metric answers a management question
2. **Decision Support**: Insights directly enable strategic actions
3. **Automation**: All processes scriptable and deployable
4. **Scalability**: Transforms handle growing data volumes
5. **Maintainability**: Clean architecture, documented, reusable

**This is NOT just a technical exercise—it's a management tool.**

---

## 📝 Next Steps

1. **Generate Data**: `python scripts/generate_retention_data.py`
2. **Create Transforms**: `python setup/create_retention_transforms.py`
3. **Build Dashboard**: Follow Kibana UI instructions above
4. **Present Insights**: Use dashboard in management meetings
5. **Iterate**: Add more metrics based on feedback

---

**Need help?** Check:
- [EVENT_SPECIFICATION.md](EVENT_SPECIFICATION.md) - Event schema
- [ISB_DEPLOYMENT.md](ISB_DEPLOYMENT.md) - Infrastructure setup
- README.md - Quick start guide

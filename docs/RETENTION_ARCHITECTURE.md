# Retention Dashboard Architecture

## 📐 System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER RETENTION & ENGAGEMENT                      │
│                          ANALYTICS ARCHITECTURE                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: DATA GENERATION                                                 │
│ ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  scripts/generate_retention_data.py                                      │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │  User Behavior Simulator                                │            │
│  │  • Power Users (15%):    D1=90%, D7=85%, D30=75%       │            │
│  │  • Regular Users (35%):  D1=60%, D7=40%, D30=25%       │            │
│  │  • Casual Users (30%):   D1=30%, D7=15%, D30=5%        │            │
│  │  • Churned Users (20%):  D1=10%, D7=2%, D30=0%         │            │
│  └─────────────────────────────────────────────────────────┘            │
│                             │                                             │
│                             │ Generates                                   │
│                             ▼                                             │
│  Event: session_started                                                  │
│  {                                                                        │
│    "@timestamp": "2025-03-15T18:45:32Z",                                │
│    "event_type": "session_started",                                      │
│    "player_id": "player_00123",                                          │
│    "session_id": "abc-def-ghi",                                          │
│    "game_id": "game_chess",                                              │
│    "game_name": "Chess"                                                  │
│  }                                                                        │
│                             │                                             │
│                             │ ~45,000 events/60 days                      │
│                             ▼                                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: EVENT PIPELINE                                                  │
│ ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐          │
│  │  RabbitMQ    │──────▶│  Logstash    │──────▶│Elasticsearch │          │
│  │              │      │              │      │              │          │
│  │ Queue:       │      │ • Parse JSON │      │ Index:       │          │
│  │ game.session │      │ • Add @timestamp│    │ platform-    │          │
│  │ .started     │      │ • Enrich data│      │ events-*     │          │
│  └──────────────┘      └──────────────┘      └──────────────┘          │
│                                                      │                    │
│  Properties:                                         │                    │
│  • Durable queues                                    │                    │
│  • JSON format                                       │ 50K+ docs          │
│  • Topic exchange                                    ▼                    │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: DATA TRANSFORMATION (Elasticsearch Transforms)                  │
│ ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  Transform 1: Daily Active Users                                         │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Source: platform-events-* (session_started)             │            │
│  │ Dest: metrics-daily-active-users                        │            │
│  │ Frequency: 1 minute                                     │            │
│  │ Aggregation:                                            │            │
│  │   GROUP BY date (day bucket)                            │            │
│  │   SELECT:                                               │            │
│  │     • daily_active_users = CARDINALITY(player_id)      │            │
│  │     • total_sessions = COUNT(session_id)               │            │
│  │     • unique_games = CARDINALITY(game_id)              │            │
│  └─────────────────────────────────────────────────────────┘            │
│                             │                                             │
│                             │ Produces: ~60 documents (60 days)           │
│                             ▼                                             │
│  metrics-daily-active-users                                              │
│  {                                                                        │
│    "date": "2025-03-15",                                                 │
│    "daily_active_users": 245,                                            │
│    "total_sessions": 1823,                                               │
│    "unique_games": 6                                                     │
│  }                                                                        │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  Transform 2: User Session Metrics                                       │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Source: platform-events-* (session_started)             │            │
│  │ Dest: metrics-user-sessions                             │            │
│  │ Frequency: 5 minutes                                    │            │
│  │ Aggregation:                                            │            │
│  │   GROUP BY player_id                                    │            │
│  │   SELECT:                                               │            │
│  │     • total_sessions = COUNT(*)                         │            │
│  │     • first_session = MIN(@timestamp)                   │            │
│  │     • last_session = MAX(@timestamp)                    │            │
│  │     • unique_days_active = CARDINALITY(@timestamp)      │            │
│  │     • unique_games_played = CARDINALITY(game_id)        │            │
│  └─────────────────────────────────────────────────────────┘            │
│                             │                                             │
│                             │ Produces: ~1200 documents (1 per user)      │
│                             ▼                                             │
│  metrics-user-sessions                                                   │
│  {                                                                        │
│    "player_id": "player_00123",                                          │
│    "total_sessions": 37,                                                 │
│    "first_session": "2025-02-01T10:15:00Z",                             │
│    "last_session": "2025-03-15T18:45:00Z",                              │
│    "unique_days_active": 28,                                             │
│    "unique_games_played": 4                                              │
│  }                                                                        │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  Transform 3: Retention Cohorts                                          │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Source: platform-events-* (session_started)             │            │
│  │ Dest: metrics-retention-cohorts                         │            │
│  │ Frequency: 1 hour                                       │            │
│  │ Aggregation:                                            │            │
│  │   GROUP BY player_id, cohort_week                       │            │
│  │   SELECT:                                               │            │
│  │     • sessions_in_cohort_week = COUNT(*)                │            │
│  │     • first_session_in_week = MIN(@timestamp)           │            │
│  │     • last_session_in_week = MAX(@timestamp)            │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                           │
│  ─────────────────────────────────────────────────────────────────────  │
│                                                                           │
│  Transform 4: Hourly Activity                                            │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Source: platform-events-* (session_started)             │            │
│  │ Dest: metrics-hourly-activity                           │            │
│  │ Frequency: 30 minutes                                   │            │
│  │ Aggregation:                                            │            │
│  │   GROUP BY hour_of_day, day_of_week                     │            │
│  │   SELECT:                                               │            │
│  │     • session_count = COUNT(*)                          │            │
│  │     • unique_players = CARDINALITY(player_id)           │            │
│  └─────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: KIBANA DASHBOARD                                                │
│ ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 User Retention & Engagement Dashboard            │   │
│  ├──────┬──────┬────────┬──────────┬──────┬──────┬──────┬─────────┤   │
│  │ DAU  │ MAU  │Sticki- │   Avg    │  D1  │  D7  │ D30  │  Churn  │   │
│  │ 245  │ 980  │ ness   │ Sessions │ 48%  │ 35%  │ 22%  │  Rate   │   │
│  │      │      │  25%   │   3.2    │      │      │      │  18%    │   │
│  ├──────────────────────────────────┴──────────────────────────────┤   │
│  │                                    │                              │   │
│  │   📈 DAU Trend Over Time          │   📊 Sessions Distribution   │   │
│  │   (Line chart showing growth)     │   (Bar chart: user counts)   │   │
│  │                                    │                              │   │
│  ├────────────────────────────────────────────────────────────────┤   │
│  │                                                                   │   │
│  │        🕐 Activity by Hour of Day & Day of Week                  │   │
│  │        (Heatmap showing peak usage times)                        │   │
│  │                                                                   │   │
│  ├──────────────────────────────────┬────────────────────────────  │   │
│  │                                   │                              │   │
│  │  📅 Weekly Cohort Retention      │   ⚠️ Churn Risk Analysis     │   │
│  │  (Retention by signup week)      │   (Inactive users)            │   │
│  │                                   │                              │   │
│  └──────────────────────────────────┴──────────────────────────────┘   │
│                                                                           │
│  Data Sources:                                                           │
│  • KPIs: metrics-daily-active-users, metrics-user-sessions              │
│  • Charts: All metric indices                                            │
│  • Filters: Global time range (7d/30d/90d)                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: MANAGEMENT INSIGHTS                                             │
│ ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  Business Questions → Metrics → Actions                                  │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Q: Are users coming back?                               │            │
│  │ M: D1=48%, D7=35%, D30=22%                              │            │
│  │ A: Retention healthy, maintain quality                  │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Q: How engaged are users?                               │            │
│  │ M: Stickiness=25%, Avg Sessions=3.2                     │            │
│  │ A: Good engagement, add social features                 │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Q: Is platform growing?                                 │            │
│  │ M: DAU +10%/week, MAU +15%/week                        │            │
│  │ A: Strong growth, scale infrastructure                  │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ Q: When do users churn?                                 │            │
│  │ M: Churn Rate=18%, mainly after week 2                  │            │
│  │ A: Add week-2 content, send notifications               │            │
│  └─────────────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Data Flow

```
                    ┌──────────────┐
                    │ Data         │
                    │ Generation   │
                    └──────┬───────┘
                           │ session_started events
                           │ (~45K events/60 days)
                           ▼
                    ┌──────────────┐
                    │ RabbitMQ     │
                    │ Queue        │
                    └──────┬───────┘
                           │ AMQP protocol
                           │ Durable queue
                           ▼
                    ┌──────────────┐
                    │ Logstash     │
                    │ Processing   │
                    └──────┬───────┘
                           │ JSON parsing
                           │ Timestamp extraction
                           ▼
                    ┌──────────────┐
                    │ Elasticsearch│
                    │ Index        │
                    │ platform-    │
                    │ events-*     │
                    └──────┬───────┘
                           │
                 ┌─────────┴─────────┐
                 │ Transforms         │
                 │ (Continuous)       │
                 └─────────┬──────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌──────────┐    ┌──────────┐   ┌──────────┐
    │ metrics- │    │ metrics- │   │ metrics- │
    │ daily-   │    │ user-    │   │ hourly-  │
    │ active-  │    │ sessions │   │ activity │
    │ users    │    │          │   │          │
    └────┬─────┘    └────┬─────┘   └────┬─────┘
         │               │              │
         └───────────────┴──────────────┘
                         │
                         │ Lens queries
                         │
                         ▼
                  ┌──────────────┐
                  │ Kibana       │
                  │ Dashboard    │
                  └──────────────┘
                         │
                         │ Visual insights
                         │
                         ▼
                  ┌──────────────┐
                  │ Management   │
                  │ Decisions    │
                  └──────────────┘
```

## 🎯 Metric Calculation Flow

### DAU (Daily Active Users)
```
platform-events-* 
  → Filter: event_type = session_started
  → Group By: @timestamp (day)
  → Aggregate: CARDINALITY(player_id)
  → Output: metrics-daily-active-users
  → Display: Latest value in Kibana
```

### D1 Retention
```
metrics-user-sessions
  → Filter: first_session >= X days ago
  → Calculate: (last_session - first_session)
  → Count: users where diff <= 1 day
  → Formula: (Count / Total Users) * 100
  → Display: Metric in Kibana
```

### Stickiness
```
Step 1: Get DAU
  metrics-daily-active-users → Latest daily_active_users

Step 2: Get MAU
  metrics-user-sessions → COUNT(DISTINCT player_id WHERE last_session >= now-30d)

Step 3: Calculate
  Stickiness = (DAU / MAU) * 100

Step 4: Display
  Kibana Formula visualization
```

## 📊 Index Schema

### platform-events-* (Raw Events)
```json
{
  "@timestamp": "date",
  "event_type": "keyword",
  "player_id": "keyword",
  "session_id": "keyword",
  "game_id": "keyword",
  "game_name": "keyword"
}
```

### metrics-daily-active-users (Aggregated)
```json
{
  "date": "date",
  "daily_active_users": "long",
  "total_sessions": "long",
  "unique_games": "long"
}
```

### metrics-user-sessions (Per User)
```json
{
  "player_id": "keyword",
  "total_sessions": "long",
  "first_session": "date",
  "last_session": "date",
  "unique_days_active": "long",
  "unique_games_played": "long"
}
```

## 🚀 Deployment Flow

```
1. Infrastructure
   docker-compose up -d
        ↓
   Elasticsearch, Kibana, Logstash, RabbitMQ running

2. Generate Data
   python scripts/generate_retention_data.py
        ↓
   45,000+ events sent to RabbitMQ
        ↓
   Logstash processes → Elasticsearch indexes

3. Create Transforms
   python setup/create_retention_transforms.py
        ↓
   4 transforms created and started
        ↓
   Metric indices populated

4. Setup Dashboard
   python setup/create_retention_dashboard.py
        ↓
   Data views created
        ↓
   Manual: Build visualizations in Kibana

5. Analyze
   Open dashboard → View insights → Make decisions
```

## 🎓 ISM Architecture Principles

### Separation of Concerns
- **Data Layer**: Raw event storage (Elasticsearch)
- **Transform Layer**: Aggregation logic (Transforms)
- **Presentation Layer**: Visualization (Kibana)
- **Business Layer**: Decision support (Insights)

### Automation
- One-command deployment
- Continuous transforms (no manual refresh)
- Scriptable configuration

### Scalability
- Distributed processing (Logstash)
- Horizontal scaling (Elasticsearch shards)
- Pre-aggregation (Transforms reduce query load)

### Maintainability
- Clear data lineage
- Documented calculations
- Version-controlled configuration

---

**Architecture Type:** Lambda Architecture (batch + stream)  
**Update Frequency:** Near real-time (1-5 min latency)  
**Query Performance:** <500ms (pre-aggregated data)  
**Data Retention:** 90 days (configurable)

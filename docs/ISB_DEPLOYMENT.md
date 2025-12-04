# ISB Deployment Afspraken - Analytics Platform

## Infrastructuur Overzicht

### Technology Stack
- **Message Queue**: RabbitMQ 3.12
- **Data Processing**: Logstash 8.11
- **Data Storage**: Elasticsearch 8.11
- **Visualization**: Kibana 8.11
- **Orchestration**: Docker Compose

---

## Deployment Specificaties

### 1. RabbitMQ
```yaml
Service: rabbitmq
Image: rabbitmq:3.12-management
Ports:
  - 5672 (AMQP)
  - 15672 (Management UI)
Resources:
  Memory: 1GB
  CPU: 1 core
Persistence: Volume mount voor data durability
```

**Afspraken met ISB**:
- High availability niet vereist in eerste versie
- Backup strategie: Daily snapshot van queues
- Monitoring: Via RabbitMQ Management UI

---

### 2. Elasticsearch
```yaml
Service: elasticsearch
Image: elasticsearch:8.11.0
Ports:
  - 9200 (HTTP)
  - 9300 (Transport)
Resources:
  Memory: 2GB (min), 4GB (recommended)
  CPU: 2 cores
  Storage: 50GB SSD
Persistence: Volume mount voor indices
```

**Afspraken met ISB**:
- Single node setup voor development/staging
- Cluster setup (3 nodes) voor productie
- Index lifecycle: 30 dagen retention
- Backup: Elasticsearch snapshot repository (daily)

---

### 3. Logstash
```yaml
Service: logstash
Image: logstash:8.11.0
Resources:
  Memory: 1GB
  CPU: 1 core
Pipeline: Custom configuration in /pipeline
```

**Afspraken met ISB**:
- Pipeline configurations via Git
- Auto-restart on failure
- Log aggregation naar central logging

---

### 4. Kibana
```yaml
Service: kibana
Image: kibana:8.11.0
Port: 5601
Resources:
  Memory: 1GB
  CPU: 0.5 core
```

**Afspraken met ISB**:
- SSO(Single Sign-On) integratie
- Dashboard export/import via Git

---

## Netwerk & Security

### Netwerk Configuratie
```
Network: platform-analytics-network
Type: bridge
Subnet: 172.20.0.0/16
```

**Services Communication**:
```
App Team → RabbitMQ (5672)
RabbitMQ → Logstash (internal)
Logstash → Elasticsearch (9200)
Kibana → Elasticsearch (9200)
Users → Kibana (5601)
```

### Security
- **Credentials**: Via environment variables (`.env` file)
- **Access Control**:
  - RabbitMQ: User/password authentication
  - Elasticsearch: Built-in security enabled
  - Kibana: RBAC for dashboards

---

## Deployment Proces

### Development/Local
```bash
# Start stack
docker compose up -d

# Verify health
docker compose ps
curl http://localhost:9200/_cluster/health
```

### Staging/Production
**Afspraak met ISB**: CI/CD pipeline via GitLab

```yaml
# .gitlab-ci.yml excerpt
deploy:
  stage: deploy
  script:
    - docker compose -f docker-compose.prod.yml up -d
    - ./scripts/import-dashboards.sh
    - ./scripts/verify-health.sh
```

---

## Monitoring & Alerting

### Health Checks
- RabbitMQ: Queue depth, consumer lag
- Elasticsearch: Cluster health, index size
- Logstash: Processing rate, errors

### Alerts (via ISB monitoring)
- RabbitMQ queue > 10K messages
- Elasticsearch disk usage > 80%
- Logstash pipeline errors > 100/min


---

## Scaling Plan

### Phase 1 (Current)
- Single node setup
- Max 10K events/min

### Phase
- Elasticsearch cluster (3 nodes)
- Load balancing
- Max 50K events/min

---

## Change Management

### Configuration Changes
1. Update in Git repository
2. Review door ISB team
3. Deploy via CI/CD pipeline
4. Verify in staging
5. Deploy to production (planned maintenance)

---

## Contact

**Analytics Student**:
- Lead: Said Khalaf
- Email: said.khalaf@student.kdg.be

**ISB Team**:
- DevOps: Team 5
# Testing Analytics Events

This guide helps you verify that events are being sent correctly from your application to the analytics pipeline.

## 🧪 Testing Methods

### Method 1: RabbitMQ Management UI (Easiest)

**Access:** http://localhost:15672
- Username: `admin`
- Password: `admin`

**Steps:**
1. Navigate to **Queues** tab
2. Look for queues like:
   - `queue.game.session.started`
   - `queue.platform.transaction.purchase`
   - `queue.platform.page.visited`
3. Check **Messages** column - should show incoming messages
4. Click on a queue name to see details
5. Use **Get Messages** section to inspect actual payloads

**What to check:**
- ✅ Messages are arriving in the correct queue
- ✅ Message rate is reasonable (not 0, not millions)
- ✅ Payload format matches EVENT_SPECIFICATION.md

---

### Method 2: Python Test Script (Recommended for Development)

Create a simple test to send a single event:

```python
# test_send_event.py
import pika
import json
from datetime import datetime, timezone
import uuid

# Connect to RabbitMQ
credentials = pika.PlainCredentials('admin', 'admin')
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost', port=5672, credentials=credentials)
)
channel = connection.channel()

# Create test event
event = {
    "event_type": "game_started",
    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
    "game_id": "game_chess",
    "player_id": "test_player_123",
    "session_id": str(uuid.uuid4()),
    "game_name": "Chess",
    "player_count": 2,
    "started_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
}

# Send to exchange
channel.basic_publish(
    exchange='platform.events',
    routing_key='game.session.started',
    body=json.dumps(event),
    properties=pika.BasicProperties(
        delivery_mode=2,  # persistent
        content_type='application/json'
    )
)

print(f"✅ Sent test event: {event['event_type']}")
print(f"   Check RabbitMQ UI or Elasticsearch for this event")
connection.close()
```

**Run:**
```powershell
python test_send_event.py
```

---

### Method 3: Check Elasticsearch (Verify End-to-End)

```powershell
# Check if events made it to Elasticsearch
curl -u elastic:changeme "http://localhost:9200/platform-events-*/_search?size=5&sort=@timestamp:desc&pretty"
```

Or use Kibana Dev Tools: http://localhost:5601/app/dev_tools#/console

```json
GET platform-events-*/_search
{
  "size": 10,
  "sort": [{"@timestamp": "desc"}],
  "query": {
    "match_all": {}
  }
}
```

**Filter by event type:**
```json
GET platform-events-*/_search
{
  "query": {
    "term": {"event_type": "game_started"}
  }
}
```

---

### Method 4: Monitor Logstash Logs

```powershell
# Watch Logstash processing
docker logs -f platform-analytics-logstash-1 --tail 50
```

Look for:
- ✅ "Successfully sent" messages
- ❌ Parse errors or validation failures

---

## 🔍 Common Issues & Solutions

### Issue: No messages in RabbitMQ queues

**Check:**
1. Is RabbitMQ running? `docker ps | findstr rabbitmq`
2. Are queues bound to exchange?
   ```powershell
   python setup/setup_rabbitmq_bindings.py
   ```
3. Is your app connected to correct host/port? (localhost:5672)
4. Check exchange exists: http://localhost:15672/#/exchanges

**Solution:**
```powershell
# Re-setup RabbitMQ bindings
python setup/setup_rabbitmq_bindings.py
```

---

### Issue: Messages in RabbitMQ but not in Elasticsearch

**Check:**
1. Is Logstash running? `docker ps | findstr logstash`
2. Check Logstash logs: `docker logs platform-analytics-logstash-1`
3. Is Elasticsearch healthy? `curl http://localhost:9200/_cluster/health`

**Common Logstash errors:**
- Parse errors → JSON format invalid
- Missing required fields → Check EVENT_SPECIFICATION.md
- Connection refused → Elasticsearch not ready

---

### Issue: Wrong event format or validation errors

**Check EVENT_SPECIFICATION.md requirements:**

1. **Timestamp format:** Must be ISO 8601
   ```json
   "timestamp": "2024-12-04T14:30:00Z"  ✅
   "timestamp": "2024-12-04 14:30:00"   ❌
   ```

2. **Required fields:** All mandatory fields present
   ```json
   {
     "event_type": "game_started",      // ✅ Required
     "timestamp": "2024-12-04T14:30:00Z", // ✅ Required
     "game_id": "uuid",                 // ✅ Required
     "player_id": "uuid"                // ✅ Required
   }
   ```

3. **Enum values:** Only allowed values
   ```json
   "game_name": "Chess"        // ✅ Valid (in enum)
   "game_name": "Backgammon"   // ❌ Not in allowed list
   ```

---

## 📊 Validation Checklist

Before deploying event sending code, verify:

- [ ] Events use correct `event_type` from EVENT_SPECIFICATION.md
- [ ] Timestamp is ISO 8601 format with 'Z' suffix
- [ ] All required fields are present
- [ ] Enum fields use only allowed values
- [ ] Routing key matches specification
- [ ] Event publishes to `platform.events` exchange
- [ ] Test event appears in RabbitMQ queue
- [ ] Test event appears in Elasticsearch within 30 seconds
- [ ] Dashboard shows the event correctly

---

## 🚀 Quick Smoke Test

```powershell
# 1. Check services are running
docker ps

# 2. Send test events
python setup/generate_revenue_data.py  # Generates 100 test events

# 3. Check RabbitMQ
# Open http://localhost:15672 and verify queues have messages

# 4. Check Elasticsearch
curl -u elastic:changeme "http://localhost:9200/platform-events-*/_count?pretty"

# 5. Check Kibana Dashboard
# Open http://localhost:5601 and verify data appears
```

---

## 📝 Event Sending Template (For Your App Team)

```python
import pika
import json
from datetime import datetime, timezone

class AnalyticsEventSender:
    def __init__(self, host='localhost', port=5672, user='admin', password='admin'):
        credentials = pika.PlainCredentials(user, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port, credentials=credentials)
        )
        self.channel = self.connection.channel()
        self.exchange = 'platform.events'
    
    def send_event(self, event_type, routing_key, payload):
        """Send an analytics event"""
        payload['event_type'] = event_type
        payload['timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        self.channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=json.dumps(payload),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type='application/json'
            )
        )
    
    def close(self):
        self.connection.close()

# Usage example:
sender = AnalyticsEventSender()

# Send game started event
sender.send_event(
    event_type='game_started',
    routing_key='game.session.started',
    payload={
        'game_id': 'game_chess',
        'player_id': 'player_12345',
        'session_id': 'session_uuid',
        'game_name': 'Chess',
        'player_count': 2,
        'started_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
)

sender.close()
```

---

## 🔗 Related Documentation

- [EVENT_SPECIFICATION.md](EVENT_SPECIFICATION.md) - Complete event schema reference
- [README.md](../README.md) - Project setup and architecture
- RabbitMQ Management: http://localhost:15672
- Kibana Dev Tools: http://localhost:5601/app/dev_tools

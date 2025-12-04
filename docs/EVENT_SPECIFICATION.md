# Event Specification - Platform Analytics

## Overzicht

Dit document beschrijft alle events die door het applicatieteam worden verstuurd naar de Analytics pipeline via RabbitMQ.

---

## Event Categorieën

### 1. Gameplay Events

Events gerelateerd aan game sessies en gameplay.

#### 1.1 Game Started
**Event Type**: `game_started`  
**Routing Key**: `game.session.started`  
**Beschrijving**: Wordt verstuurd wanneer een nieuwe game sessie start

**Payload**:
```json
{
  "event_type": "game_started",
  "timestamp": "2024-12-04T14:30:00Z",
  "game_id": "uuid",
  "player_id": "uuid",
  "session_id": "uuid",
  "game_name": "Chess|Catan|Risk|Monopoly|Scrabble",
  "player_count": 2,
  "started_at": "2024-12-04T14:30:00Z"
}
```

**Verplichte velden**: `event_type`, `timestamp`, `game_id`, `player_id`, `session_id`  
**Analytics gebruik**: Game populatie tracking, sessie start tracking

---

#### 1.2 Game Ended
**Event Type**: `game_ended`  
**Routing Key**: `game.session.ended`  
**Beschrijving**: Wordt verstuurd wanneer een game sessie normaal eindigt

**Payload**:
```json
{
  "event_type": "game_ended",
  "timestamp": "2024-12-04T15:00:00Z",
  "game_id": "uuid",
  "player_id": "uuid",
  "session_id": "uuid",
  "session_duration": 1800,
  "completed": true,
  "ended_at": "2024-12-04T15:00:00Z"
}
```

**Verplichte velden**: `event_type`, `timestamp`, `session_id`, `session_duration`, `completed`  
**Analytics gebruik**: Completion rate, average session duration, engagement metrics

---

#### 1.3 Game Abandoned
**Event Type**: `game_abandoned`  
**Routing Key**: `game.session.abandoned`  
**Beschrijving**: Wordt verstuurd wanneer een speler een game verlaat zonder te voltooien

**Payload**:
```json
{
  "event_type": "game_abandoned",
  "timestamp": "2024-12-04T14:45:00Z",
  "game_id": "uuid",
  "player_id": "uuid",
  "session_id": "uuid",
  "session_duration": 900,
  "completed": false,
  "reason": "player_quit|timeout|error"
}
```

**Analytics gebruik**: Churn analysis, game quality issues detection

---

#### 1.4 Winner Declared
**Event Type**: `winner_declared`  
**Routing Key**: `game.winner.declared`  
**Beschrijving**: Wordt verstuurd wanneer er een winnaar is in de game

**Payload**:
```json
{
  "event_type": "winner_declared",
  "timestamp": "2024-12-04T15:00:00Z",
  "game_id": "uuid",
  "session_id": "uuid",
  "winner": "Human|AI",
  "winner_id": "uuid",
  "game_name": "Chess"
}
```

**Analytics gebruik**: Win rate analysis (Human vs AI), game balance metrics

---

#### 1.5 Achievement Unlocked
**Event Type**: `achievement_unlocked`  
**Routing Key**: `game.achievement.unlocked`  
**Beschrijving**: Wordt verstuurd wanneer een speler een achievement behaalt

**Payload**:
```json
{
  "event_type": "achievement_unlocked",
  "timestamp": "2024-12-04T15:00:00Z",
  "player_id": "uuid",
  "achievement_id": "uuid",
  "achievement_name": "First Win",
  "achievement_category": "milestone|skill|social",
  "game_name": "Chess"
}
```

**Analytics gebruik**: Gamification success tracking, player progression

---

### 2. User Action Events

Events gerelateerd aan gebruikersacties buiten gameplay.

#### 2.1 User Logged In
**Event Type**: `user_logged_in`  
**Routing Key**: `user.session.logged_in`

**Payload**:
```json
{
  "event_type": "user_logged_in",
  "timestamp": "2024-12-04T14:00:00Z",
  "user_id": "uuid",
  "session_id": "uuid",
  "login_method": "email|google|facebook",
  "device_type": "web|mobile|tablet"
}
```

**Analytics gebruik**: DAU/MAU metrics, login patterns

---

#### 2.2 User Logged Out
**Event Type**: `user_logged_out`  
**Routing Key**: `user.session.logged_out`

**Payload**:
```json
{
  "event_type": "user_logged_out",
  "timestamp": "2024-12-04T16:00:00Z",
  "user_id": "uuid",
  "session_id": "uuid",
  "session_duration": 7200
}
```

**Analytics gebruik**: Session length analysis

---

#### 2.3 User Registered
**Event Type**: `user_registered`  
**Routing Key**: `user.account.registered`

**Payload**:
```json
{
  "event_type": "user_registered",
  "timestamp": "2024-12-04T13:00:00Z",
  "user_id": "uuid",
  "registration_method": "email|social"
}
```

**Analytics gebruik**: User acquisition tracking, conversion funnel

---

#### 2.4 Friend Added
**Event Type**: `friend_added`  
**Routing Key**: `user.social.friend_added`

**Payload**:
```json
{
  "event_type": "friend_added",
  "timestamp": "2024-12-04T14:30:00Z",
  "user_id": "uuid",
  "friend_id": "uuid",
  "connection_type": "request_accepted|imported"
}
```

**Analytics gebruik**: Social graph analysis, viral coefficient

---

### 3. Platform Events

Events gerelateerd aan platform interacties en transacties.

#### 3.1 Game Page Visit
**Event Type**: `gamePage_visit`  
**Routing Key**: `platform.page.visited`

**Payload**:
```json
{
  "event_type": "gamePage_visit",
  "timestamp": "2024-12-04T14:00:00Z",
  "user_id": "uuid",
  "game_id": "uuid",
  "game_name": "Chess",
  "referrer": "homepage|search|direct",
  "session_id": "uuid"
}
```

**Analytics gebruik**: Conversion funnel top, game discovery patterns

---

#### 3.2 Purchase Made
**Event Type**: `purchase_made`  
**Routing Key**: `platform.transaction.purchase`

**Payload**:
```json
{
  "event_type": "purchase_made",
  "timestamp": "2024-12-04T14:15:00Z",
  "user_id": "uuid",
  "game_id": "uuid",
  "product_type": "game|subscription|premium_feature",
  "amount": 15.99,
  "currency": "EUR",
  "transaction_id": "uuid"
}
```

**Analytics gebruik**: Revenue tracking, conversion rate, ARPU

---

#### 3.3 Payment Made
**Event Type**: `payment_made`  
**Routing Key**: `platform.transaction.payment`

**Payload**:
```json
{
  "event_type": "payment_made",
  "timestamp": "2024-12-04T14:16:00Z",
  "user_id": "uuid",
  "transaction_id": "uuid",
  "payment_method": "credit_card|paypal|ideal",
  "amount": 15.99,
  "currency": "EUR",
  "status": "completed|failed|pending"
}
```

**Analytics gebruik**: Payment success rate, payment method preferences

---

#### 3.4 System Error
**Event Type**: `system_error`  
**Routing Key**: `platform.system.error`

**Payload**:
```json
{
  "event_type": "system_error",
  "timestamp": "2024-12-04T14:30:00Z",
  "user_id": "uuid",
  "error_code": "500|404|timeout",
  "error_message": "string",
  "affected_feature": "game_load|payment|login",
  "severity": "low|medium|high|critical"
}
```

**Analytics gebruik**: System health monitoring, user experience quality

---

## RabbitMQ Configuratie

### Exchange Setup
```
Exchange Name: platform.events
Exchange Type: topic
Durability: true
Auto-delete: false
```

### Queue Bindings
```
Queue Pattern: queue.{category}.{event_type}
Examples:
  - queue.game.session.started
  - queue.user.session.logged_in
  - queue.platform.transaction.purchase
```

---

## Data Validatie Regels

1. **Timestamp**: Moet ISO 8601 format zijn
2. **UUID velden**: Moet geldige UUID v4 zijn
3. **Enums**: Alleen toegestane waarden (zie payload specs)
4. **Numeric fields**: Positieve getallen voor duration, amount
5. **Required fields**: Alle verplichte velden moeten aanwezig zijn

---

## Error Handling

### Invalid Events
Events die niet voldoen aan spec worden:
1. Gelogd in error queue: `queue.dlq.invalid_format`
2. Opgeslagen voor manual review
3. Niet verwerkt in analytics

### Missing Data
Bij optionele velden die ontbreken:
1. Default waarden gebruiken (gedocumenteerd per veld)
2. Event wel verwerken
3. Warning loggen

---

## Testing

### Test Event Generators
Gebruik [`generate_events.py`](../generate_events.py) voor het genereren van realistische test data.

```bash
python ../generate_events.py --sessions 10
```

### Validation
Events worden gevalideerd door Logstash filter pipeline voordat indexering.
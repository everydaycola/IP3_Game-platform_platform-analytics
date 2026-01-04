#!/usr/bin/env python3
"""
Revenue Data Generator - Fast Startup Mode
Generates revenue data directly to Elasticsearch (bypasses RabbitMQ for speed).
Used by start.ps1 when setting up from scratch.
"""
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import json
import random
import sys
import uuid
import time


def wait_for_elasticsearch(es_url, auth, max_retries=30):
    """Wait for Elasticsearch to be fully ready with green/yellow status"""
    print("⏳ Waiting for Elasticsearch to be ready...")
    
    for i in range(max_retries):
        try:
            r = requests.get(f"{es_url}/_cluster/health", auth=auth, timeout=5)
            if r.status_code == 200:
                health = r.json()
                status = health.get('status', 'unknown')
                if status in ['green', 'yellow']:
                    print(f"✅ Elasticsearch is ready (status: {status})")
                    return True
                else:
                    print(f"   Cluster status: {status}, waiting...")
        except Exception as e:
            print(f"   Connection attempt {i+1}/{max_retries}...")
        
        time.sleep(2)
    
    print("❌ Elasticsearch not ready after waiting")
    return False


def bulk_insert_with_retry(es_url, auth, events, batch_size=500, max_retries=3):
    """Insert events in batches with retry logic"""
    total_inserted = 0
    total_errors = 0
    
    for batch_start in range(0, len(events), batch_size):
        batch = events[batch_start:batch_start + batch_size]
        
        body_lines = []
        for e in batch:
            ts = datetime.fromisoformat(e['@timestamp'].replace('Z', '+00:00'))
            index_name = f"platform-events-{ts.strftime('%Y.%m.%d')}"
            body_lines.append(json.dumps({'index': {'_index': index_name}}))
            body_lines.append(json.dumps(e))
        
        body = '\n'.join(body_lines) + '\n'
        
        # Retry logic
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    f'{es_url}/_bulk',
                    auth=auth,
                    headers={'Content-Type': 'application/x-ndjson'},
                    data=body,
                    timeout=60
                )
                
                if r.status_code == 200:
                    result = r.json()
                    if not result.get('errors'):
                        total_inserted += len(batch)
                        break
                    else:
                        # Count actual errors vs successes
                        errors_in_batch = sum(1 for item in result['items'] if 'error' in item.get('index', {}))
                        total_inserted += len(batch) - errors_in_batch
                        total_errors += errors_in_batch
                        break
                elif r.status_code == 429:  # Too many requests
                    time.sleep(2 ** attempt)
                    continue
                else:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    total_errors += len(batch)
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                total_errors += len(batch)
    
    return total_inserted, total_errors


def generate_revenue_data():
    """Generate purchase_made, payment_made, gamePage_visit events directly to ES"""
    
    ES_URL = "http://localhost:9200"
    ES_AUTH = HTTPBasicAuth('elastic', 'changeme')
    
    print("=" * 70)
    print("💰 REVENUE DATA GENERATOR (Fast Mode)")
    print("=" * 70)
    
    # Wait for ES to be fully ready
    if not wait_for_elasticsearch(ES_URL, ES_AUTH):
        return False
    
    # Games with prices and popularity
    games = [
        {"id": "game_chess", "name": "Chess Master Pro", "price": 12.99, "popularity": 0.25},
        {"id": "game_catan", "name": "Catan Digital", "price": 15.99, "popularity": 0.20},
        {"id": "game_risk", "name": "Risk: Global Domination", "price": 14.99, "popularity": 0.18},
        {"id": "game_monopoly", "name": "Monopoly Plus", "price": 11.99, "popularity": 0.15},
        {"id": "game_scrabble", "name": "Scrabble GO", "price": 9.99, "popularity": 0.12},
        {"id": "game_cards", "name": "Ultimate Card Collection", "price": 7.99, "popularity": 0.10},
    ]
    
    payment_methods = ["credit_card", "paypal", "ideal", "bancontact", "mastercard"]
    payment_weights = [0.45, 0.30, 0.15, 0.08, 0.02]
    
    product_types = [
        {"type": "game_purchase", "weight": 0.60},
        {"type": "subscription_monthly", "price": 9.99, "weight": 0.25},
        {"type": "subscription_yearly", "price": 89.99, "weight": 0.10},
        {"type": "premium_feature", "price": 4.99, "weight": 0.05},
    ]
    
    events = []
    days = 60  # 60 days is enough to show weekly/monthly/yearly differences
    base_transactions_per_day = 50  # More transactions per day for richer data

    print(f"\n📊 Generating {days} days of revenue data...")
    print(f"   - ~{base_transactions_per_day} transactions per day")
    print(f"   - Seasonal variation & weekend bonuses")
    print(f"   - Batched insertion with retry logic")
    
    now = datetime.now()
    
    for day in range(days):
        current_date = now - timedelta(days=day)
        month = current_date.month
        
        # Seasonal variation
        if month in [11, 12, 1, 2]:
            seasonal_factor = 1.4
        elif month in [6, 7, 8]:
            seasonal_factor = 0.7
        elif month in [3, 4, 5]:
            seasonal_factor = 0.9
        else:
            seasonal_factor = 1.1
        
        # Weekend bonus
        is_weekend = current_date.weekday() >= 5
        weekend_factor = 1.3 if is_weekend else 1.0
        
        # Random variation
        random_factor = random.uniform(0.8, 1.2)
        
        daily_count = int(base_transactions_per_day * seasonal_factor * weekend_factor * random_factor)
        
        for i in range(daily_count):
            event_time = now - timedelta(days=day, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            
            # Select product type
            product = random.choices(product_types, weights=[p["weight"] for p in product_types])[0]
            
            # Select game and determine price
            if product["type"] == "game_purchase":
                game = random.choices(games, weights=[g["popularity"] for g in games])[0]
                game_id = game["id"]
                game_name = game["name"]
                price = game["price"]
            else:
                game_id = "platform_service"
                game_name = product["type"].replace("_", " ").title()
                price = product["price"]
            
            # Apply discount sometimes
            if random.random() < 0.20:
                discount = random.uniform(0.05, 0.30)
                price = round(price * (1 - discount), 2)
            
            user_id = f'user_{random.randint(1000, 9999)}'
            transaction_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            
            # 1. gamePage_visit event (70% of transactions)
            if random.random() < 0.70:
                visit_time = event_time - timedelta(seconds=random.randint(30, 300))
                events.append({
                    'event_type': 'gamePage_visit',
                    '@timestamp': visit_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'user_id': user_id,
                    'game_id': game_id,
                    'game_name': game_name,
                    'referrer': random.choice(["homepage", "search", "direct", "social_media", "recommendation"]),
                    'session_id': session_id
                })
            
            # 2. purchase_made event
            events.append({
                'event_type': 'purchase_made',
                '@timestamp': event_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'user_id': user_id,
                'game_id': game_id,
                'game_name': game_name,
                'product_type': product["type"],
                'amount': price,
                'currency': 'EUR',
                'transaction_id': transaction_id
            })
            
            # 3. payment_made event
            payment_time = event_time + timedelta(seconds=random.randint(1, 5))
            payment_method = random.choices(payment_methods, weights=payment_weights)[0]
            status = "completed" if random.random() < 0.95 else random.choice(["failed", "pending"])
            
            events.append({
                'event_type': 'payment_made',
                '@timestamp': payment_time.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'user_id': user_id,
                'transaction_id': transaction_id,
                'payment_method': payment_method,
                'amount': price,
                'currency': 'EUR',
                'status': status
            })
    
    # Insert with batching and retry
    print(f"\n📤 Inserting {len(events)} events into Elasticsearch...")
    
    inserted, errors = bulk_insert_with_retry(ES_URL, ES_AUTH, events)
    
    if errors == 0:
        print(f"✅ Successfully inserted {inserted} events")
    else:
        print(f"⚠️  Inserted {inserted} events, {errors} errors")
    
    # Refresh indices
    requests.post(f'{ES_URL}/platform-events-*/_refresh', auth=ES_AUTH)
    
    # Show summary
    r = requests.post(
        f'{ES_URL}/platform-events-*/_search',
        auth=ES_AUTH,
        json={
            'size': 0,
            'query': {'term': {'event_type': 'purchase_made'}},
            'aggs': {'total_revenue': {'sum': {'field': 'amount'}}}
        }
    )
    
    if r.status_code == 200:
        total = r.json()['aggregations']['total_revenue']['value']
        print(f"\n📊 Revenue summary:")
        print(f"   Days covered: {days}")
        print(f"   Total revenue: €{total:.2f}")
    
    print("\n" + "=" * 70)
    print("✅ Revenue data generation complete!")
    print("=" * 70)
    
    return True


if __name__ == "__main__":
    success = generate_revenue_data()
    sys.exit(0 if success else 1)

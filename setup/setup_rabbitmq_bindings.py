#!/usr/bin/env python3
"""
Setup RabbitMQ Queue Bindings
Binds queues to the platform.events exchange with correct routing keys
"""

import requests
from requests.auth import HTTPBasicAuth

RABBITMQ_URL = "http://localhost:15672"
USERNAME = "admin"
PASSWORD = "admin"

# Define queue bindings
BINDINGS = [
    {"queue": "queue.platform.user.logged_in", "routing_key": "platform.user.logged_in"},
    {"queue": "queue.platform.user.logged_out", "routing_key": "platform.user.logged_out"},
    {"queue": "queue.platform.user.registered", "routing_key": "platform.user.registered"},
    {"queue": "queue.platform.user.retention", "routing_key": "platform.user.retention"},
    {"queue": "queue.platform.friend.request_sent", "routing_key": "platform.friend.request_sent"},
    {"queue": "queue.platform.friend.request_accepted", "routing_key": "platform.friend.request_accepted"},
    {"queue": "queue.platform.game.purchased", "routing_key": "platform.game.purchased"},
    {"queue": "queue.platform.transaction.purchase", "routing_key": "platform.transaction.purchase"},
    {"queue": "queue.platform.transaction.payment", "routing_key": "platform.transaction.payment"},
    {"queue": "queue.platform.page.visited", "routing_key": "platform.page.visited"},
    {"queue": "queue.game.session.started", "routing_key": "game.session.started"},
    {"queue": "queue.game.session.ended", "routing_key": "game.session.ended"},
    {"queue": "queue.game.session.abandoned", "routing_key": "game.session.abandoned"},
    {"queue": "queue.game.achievement.unlocked", "routing_key": "game.achievement.unlocked"},
    {"queue": "queue.game.favorited", "routing_key": "game.favorited"},
    {"queue": "queue.game.user.retention", "routing_key": "game.user.retention"},
]

EXCHANGE = "platform.events"
VHOST = "/"

def create_exchange():
    """Create the exchange if it doesn't exist"""
    vhost_encoded = "%2F" if VHOST == "/" else VHOST
    url = f"{RABBITMQ_URL}/api/exchanges/{vhost_encoded}/{EXCHANGE}"
    
    payload = {
        "type": "topic",
        "durable": True,
        "auto_delete": False
    }
    
    try:
        response = requests.put(
            url,
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD)
        )
        
        if response.status_code in [201, 204]:
            print(f"✅ Exchange '{EXCHANGE}' ready")
            return True
        else:
            print(f"❌ Failed to create exchange: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating exchange: {e}")
        return False

def create_queue(queue_name):
    """Create a queue if it doesn't exist"""
    vhost_encoded = "%2F" if VHOST == "/" else VHOST
    url = f"{RABBITMQ_URL}/api/queues/{vhost_encoded}/{queue_name}"
    
    payload = {
        "durable": True,
        "auto_delete": False
    }
    
    try:
        response = requests.put(
            url,
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD)
        )
        
        if response.status_code in [201, 204]:
            return True
        else:
            print(f"❌ Failed to create queue {queue_name}: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error creating queue {queue_name}: {e}")
        return False

def create_binding(queue_name, routing_key):
    """Create a binding between exchange and queue"""
    # URL encode the vhost (/ becomes %2F)
    vhost_encoded = "%2F" if VHOST == "/" else VHOST
    url = f"{RABBITMQ_URL}/api/bindings/{vhost_encoded}/e/{EXCHANGE}/q/{queue_name}"
    
    payload = {
        "routing_key": routing_key,
        "arguments": {}
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(USERNAME, PASSWORD)
        )
        
        if response.status_code == 201:
            print(f"✅ Bound: {queue_name} ← {routing_key}")
            return True
        elif response.status_code == 204:
            print(f"ℹ️  Already exists: {queue_name} ← {routing_key}")
            return True
        else:
            print(f"❌ Failed: {queue_name} (HTTP {response.status_code})")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error binding {queue_name}: {e}")
        return False


def list_bindings():
    """List all current bindings"""
    url = f"{RABBITMQ_URL}/api/bindings"
    
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(USERNAME, PASSWORD)
        )
        
        if response.status_code == 200:
            bindings = response.json()
            platform_bindings = [b for b in bindings if b.get('source') == EXCHANGE]
            
            print(f"\n📊 Current bindings for exchange '{EXCHANGE}':")
            if not platform_bindings:
                print("   (none)")
            else:
                for b in platform_bindings:
                    print(f"   {b['destination']} ← {b.get('routing_key', '(default)')}")
            return platform_bindings
        else:
            print(f"❌ Failed to list bindings: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("🔗 RABBITMQ QUEUE BINDINGS SETUP")
    print("=" * 70)
    
    # Create exchange first
    print("\n🔧 Creating exchange...")
    if not create_exchange():
        print("❌ Failed to create exchange, aborting")
        exit(1)
    
    # Create all queues
    print("\n🔧 Creating queues...")
    for binding in BINDINGS:
        create_queue(binding["queue"])
    
    # List existing bindings
    list_bindings()
    
    # Create bindings
    print(f"\n🔧 Creating bindings...")
    success_count = 0
    for binding in BINDINGS:
        if create_binding(binding["queue"], binding["routing_key"]):
            success_count += 1
    
    print("\n" + "=" * 70)
    print(f"✅ Setup complete! {success_count}/{len(BINDINGS)} bindings configured")
    print("=" * 70)
    
    # Show final state
    list_bindings()

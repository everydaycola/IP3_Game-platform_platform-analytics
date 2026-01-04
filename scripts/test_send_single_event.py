#!/usr/bin/env python3
"""
Quick Event Sender - Test if analytics pipeline is working

Usage:
    python test_send_single_event.py game_started
    python test_send_single_event.py purchase_made
    python test_send_single_event.py all
"""

import pika
import json
import sys
from datetime import datetime, timezone
import uuid


class EventTester:
    def __init__(self, host='localhost', port=5672, user='admin', password='admin'):
        """Connect to RabbitMQ"""
        print(f"🔌 Connecting to RabbitMQ at {host}:{port}...")
        credentials = pika.PlainCredentials(user, password)
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=port, credentials=credentials)
        )
        self.channel = self.connection.channel()
        self.exchange = 'platform.events'
        print("✅ Connected!\n")
    
    def send_event(self, event_type, routing_key, payload):
        """Send an event to RabbitMQ"""
        payload['event_type'] = event_type
        payload['@timestamp'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        self.channel.basic_publish(
            exchange=self.exchange,
            routing_key=routing_key,
            body=json.dumps(payload, indent=2),
            properties=pika.BasicProperties(
                delivery_mode=2,  # persistent
                content_type='application/json'
            )
        )
        print(f"✅ Sent: {event_type}")
        print(f"   Routing key: {routing_key}")
        print(f"   Payload:\n{json.dumps(payload, indent=2)}\n")
    
    def test_game_started(self):
        """Test game_started event"""
        self.send_event(
            event_type='game_started',
            routing_key='game.session.started',
            payload={
                'game_id': 'game_chess',
                'player_id': 'test_player_001',
                'session_id': str(uuid.uuid4()),
                'game_name': 'Chess',
                'player_count': 2,
                'started_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        )
    
    def test_game_ended(self):
        """Test game_ended event"""
        self.send_event(
            event_type='game_ended',
            routing_key='game.session.ended',
            payload={
                'game_id': 'game_chess',
                'game_name': 'Chess',
                'player_id': 'test_player_001',
                'session_id': str(uuid.uuid4()),
                'session_duration_seconds': 1200,
                'completed': True,
                'ended_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        )
    
    def test_game_abandoned(self):
        """Test game_abandoned event"""
        self.send_event(
            event_type='game_abandoned',
            routing_key='game.session.abandoned',
            payload={
                'game_id': 'game_chess',
                'game_name': 'Chess',
                'player_id': 'test_player_001',
                'session_id': str(uuid.uuid4()),
                'session_duration_seconds': 300,
                'completed': False,
                'reason': 'player_quit',
                'abandoned_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            }
        )
    
    def test_purchase_made(self):
        """Test purchase_made event"""
        self.send_event(
            event_type='purchase_made',
            routing_key='platform.transaction.purchase',
            payload={
                'player_id': 'test_player_001',
                'game_id': 'game_chess',
                'game_name': 'Chess',
                'product_type': 'game',
                'amount': 9.99,
                'currency': 'EUR',
                'transaction_id': str(uuid.uuid4())
            }
        )
    
    def test_payment_made(self):
        """Test payment_made event"""
        self.send_event(
            event_type='payment_made',
            routing_key='platform.transaction.payment',
            payload={
                'player_id': 'test_player_001',
                'transaction_id': str(uuid.uuid4()),
                'payment_method': 'credit_card',
                'amount': 9.99,
                'currency': 'EUR',
                'status': 'completed'
            }
        )
    
    def test_gamepage_visit(self):
        """Test gamePage_visit event"""
        self.send_event(
            event_type='gamePage_visit',
            routing_key='platform.page.visited',
            payload={
                'player_id': 'test_player_001',
                'game_id': 'game_chess',
                'game_name': 'Chess',
                'referrer': 'homepage',
                'session_id': str(uuid.uuid4())
            }
        )
    
    def test_session_started(self):
        """Test session_started event (for retention tracking)"""
        self.send_event(
            event_type='session_started',
            routing_key='game.session.started',
            payload={
                'player_id': 'test_player_001',
                'session_id': str(uuid.uuid4()),
                'game_id': 'game_chess',
                'game_name': 'Chess',
                'session_duration_seconds': 600
            }
        )
    
    def test_all(self):
        """Send all test events"""
        print("=" * 70)
        print("📤 SENDING ALL TEST EVENTS")
        print("=" * 70 + "\n")
        
        self.test_game_started()
        self.test_game_ended()
        self.test_game_abandoned()
        self.test_purchase_made()
        self.test_payment_made()
        self.test_gamepage_visit()
        self.test_session_started()
        
        print("=" * 70)
        print("✅ ALL TEST EVENTS SENT!")
        print("=" * 70)
        print("\n📊 Next Steps:")
        print("1. Check RabbitMQ UI: http://localhost:15672")
        print("2. Wait 30 seconds for Logstash to process")
        print("3. Check Elasticsearch:")
        print('   curl -u elastic:changeme "http://localhost:9200/platform-events-*/_search?size=5&sort=@timestamp:desc"')
        print("4. Check Kibana: http://localhost:5601")
    
    def close(self):
        """Close RabbitMQ connection"""
        self.connection.close()
        print("🔌 Disconnected from RabbitMQ\n")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python test_send_single_event.py <event_type|all>")
        print("\nAvailable event types:")
        print("  - game_started")
        print("  - game_ended")
        print("  - game_abandoned")
        print("  - purchase_made")
        print("  - payment_made")
        print("  - gamePage_visit")
        print("  - session_started")
        print("  - all (sends all events)")
        sys.exit(1)
    
    event_type = sys.argv[1].lower()
    
    tester = EventTester()
    
    try:
        if event_type == 'all':
            tester.test_all()
        elif event_type == 'game_started':
            tester.test_game_started()
        elif event_type == 'game_ended':
            tester.test_game_ended()
        elif event_type == 'game_abandoned':
            tester.test_game_abandoned()
        elif event_type == 'purchase_made':
            tester.test_purchase_made()
        elif event_type == 'payment_made':
            tester.test_payment_made()
        elif event_type in ['gamepage_visit', 'gamePage_visit']:
            tester.test_gamepage_visit()
        elif event_type == 'session_started':
            tester.test_session_started()
        else:
            print(f"❌ Unknown event type: {event_type}")
            print("Use 'all' or one of: game_started, game_ended, game_abandoned, purchase_made, payment_made, gamePage_visit, session_started")
            sys.exit(1)
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS!")
        print("=" * 70)
        print("\n🔍 Verification Steps:")
        print("1. Check RabbitMQ Management UI:")
        print("   http://localhost:15672 (admin/admin)")
        print("   → Navigate to Queues tab")
        print("   → Look for the corresponding queue")
        print("\n2. Wait ~30 seconds for Logstash to process the event")
        print("\n3. Verify in Elasticsearch:")
        print(f'   curl -u elastic:changeme "http://localhost:9200/platform-events-*/_search?q=event_type:{event_type}&sort=@timestamp:desc&pretty"')
        print("\n4. Check Kibana Discover:")
        print("   http://localhost:5601/app/discover")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
    finally:
        tester.close()


if __name__ == '__main__':
    main()

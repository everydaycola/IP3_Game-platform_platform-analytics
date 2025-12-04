#!/usr/bin/env python3
"""
Test Data Generator for Platform Events
Generates realistic game platform events and sends them to RabbitMQ
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import pika
import uuid


class EventGenerator:
    """Generates realistic platform events for testing"""
    
    # Sample data
    USERS = [
        {"id": "user_001", "username": "Jan_Jansen", "email": "jan@example.com", "gender": "male"},
        {"id": "user_002", "username": "Piet_Pieters", "email": "piet@example.com", "gender": "male"},
        {"id": "user_003", "username": "Sara_Smith", "email": "sara@example.com", "gender": "female"},
        {"id": "user_004", "username": "Lisa_De_Vries", "email": "lisa@example.com", "gender": "female"},
        {"id": "user_005", "username": "Tom_Van_Berg", "email": "tom@example.com", "gender": "male"},
        {"id": "user_006", "username": "Emma_Bakker", "email": "emma@example.com", "gender": "female"},
        {"id": "user_007", "username": "Max_Mueller", "email": "max@example.com", "gender": "male"},
        {"id": "user_008", "username": "Sophie_Dubois", "email": "sophie@example.com", "gender": "female"},
        {"id": "user_009", "username": "Alex_Chen", "email": "alex@example.com", "gender": "other"},
        {"id": "user_010", "username": "Maria_Garcia", "email": "maria@example.com", "gender": "female"},
    ]
    
    GAMES = [
        {"id": "game_001", "name": "Tic-Tac-Toe", "avg_duration": 120, "price": 0.0},
        {"id": "game_002", "name": "Chess", "avg_duration": 1800, "price": 9.99},
        {"id": "game_003", "name": "Checkers", "avg_duration": 900, "price": 4.99},
        {"id": "game_004", "name": "Connect Four", "avg_duration": 300, "price": 2.99},
        {"id": "game_005", "name": "Reversi", "avg_duration": 600, "price": 6.99},
        {"id": "game_006", "name": "Sudoku", "avg_duration": 1200, "price": 3.99},
        {"id": "game_007", "name": "Mahjong", "avg_duration": 1500, "price": 7.99},
    ]
    
    ACHIEVEMENTS = [
        {"id": "ach_001", "name": "First Victory", "points": 100},
        {"id": "ach_002", "name": "5 Game Win Streak", "points": 250},
        {"id": "ach_003", "name": "Speed Demon", "points": 150},
        {"id": "ach_004", "name": "Master Tactician", "points": 500},
        {"id": "ach_005", "name": "Social Butterfly", "points": 200},
        {"id": "ach_006", "name": "Night Owl", "points": 100},
        {"id": "ach_007", "name": "Early Bird", "points": 100},
        {"id": "ach_008", "name": "Comeback King", "points": 300},
    ]
    
    PAYMENT_METHODS = ["credit_card", "paypal", "ideal", "bancontact", "mastercard", "visa"]
    DEVICES = ["desktop", "mobile", "tablet"]
    BROWSERS = ["Chrome", "Firefox", "Safari", "Edge"]
    PLATFORMS = ["Windows", "macOS", "Linux", "iOS", "Android"]
    
    def __init__(self, rabbitmq_host: str = "localhost", rabbitmq_port: int = 5672,
                 rabbitmq_user: str = "admin", rabbitmq_password: str = "admin"):
        """Initialize connection to RabbitMQ"""
        print(f"🔌 Connecting to RabbitMQ at {rabbitmq_host}:{rabbitmq_port}...")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
            virtual_host='/'
        )
        
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declare exchange
            self.exchange_name = 'platform.events'
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type='topic',
                durable=True
            )
            print(f"✓ Exchange '{self.exchange_name}' (topic) declared")
            
            # Declare queues for each event type
            self.event_queues = {
                # Platform events
                'user_logged_in': 'platform.user.logged_in',
                'user_logged_out': 'platform.user.logg ed_out',
                'user_registered': 'platform.user.registered',
                'friend_request_sent': 'platform.friend.request_sent',
                'friend_request_accepted': 'platform.friend.request_accepted',
                'game_purchased': 'platform.game.purchased',
                'user_platform_retention': 'platform.user.retention',
                
                # Game events
                'game_ended': 'game.session.ended',
                'achievement_unlocked': 'game.achievement.unlocked',
                'game_favorited': 'game.favorited',
                'user_game_retention': 'game.user.retention',
            }
            
            # Create queues and bind to exchange with routing keys
            for event_type, routing_key in self.event_queues.items():
                queue_name = f"queue.{routing_key}"
                
                # Declare queue
                self.channel.queue_declare(queue=queue_name, durable=True)
                
                # Bind queue to exchange with routing key
                self.channel.queue_bind(
                    exchange=self.exchange_name,
                    queue=queue_name,
                    routing_key=routing_key
                )
            
            print(f"✓ Created {len(self.event_queues)} queues with routing keys")
            print("✓ RabbitMQ setup complete!")
            
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            print("\n💡 Make sure RabbitMQ is running:")
            print("   docker-compose ps app_rabbitmq")
            raise
        
    def close(self):
        """Close RabbitMQ connection"""
        self.connection.close()
    
    def send_event(self, event: Dict):
        """Send event to RabbitMQ with proper routing"""
        try:
            event_type = event['event_type']
            
            # Get routing key for this event type
            routing_key = self.event_queues.get(event_type, 'platform.unknown')
            
            # Publish to exchange with routing key
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                    content_type='application/json',
                    headers={'event_type': event_type}
                )
            )
            print(f"✓ Sent: {event_type} → {routing_key}")
        except Exception as e:
            print(f"❌ Failed to send {event.get('event_type', 'unknown')}: {e}")
            raise
    
    # ========== PLATFORM EVENTS ==========
    
    def generate_user_logged_in(self, user: Dict, timestamp: Optional[datetime] = None) -> Dict:
        """1.1 UserLoggedIn - Generate user login event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        return {
            "event_type": "user_logged_in",
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            "user_id": user["id"],
            "username": user["username"],
            "session_id": str(uuid.uuid4()),
            "ip_address": f"192.168.1.{random.randint(1, 254)}",
            "device_type": random.choice(self.DEVICES),
            "browser": random.choice(self.BROWSERS),
            "platform": random.choice(self.PLATFORMS),
        }
    
    def generate_user_logged_out(self, user: Dict, session_id: str, login_time) -> Dict:
        """1.2 UserLoggedOut - Generate user logout event"""
        # Convert string to datetime if needed
        if isinstance(login_time, str):
            login_time = datetime.fromisoformat(login_time.replace('Z', '+00:00'))
        
        # Realistische sessie duur: 15 min tot 3 uur
        session_duration = random.randint(15, 180)
        logout_time = login_time + timedelta(minutes=session_duration)
        
        return {
            "event_type": "user_logged_out",
            "timestamp": logout_time.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "session_id": session_id,
            "logged_in_at": login_time.isoformat(),
            "logged_out_at": logout_time.isoformat(),
            "session_duration_minutes": session_duration,
        }
    
    def generate_user_registered(self, timestamp: Optional[datetime] = None) -> Dict:
        """1.3 UserRegistered - Generate user registration event with gender"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        new_user_id = f"user_{random.randint(100, 999)}"
        gender = random.choice(["male", "female", "other", "prefer_not_to_say"])
        
        return {
            "event_type": "user_registered",
            "timestamp": timestamp.isoformat(),
            "user_id": new_user_id,
            "username": f"Player_{random.randint(1000, 9999)}",
            "email": f"player{random.randint(100, 999)}@example.com",
            "gender": gender,
            "registration_source": random.choice(["web", "mobile_app", "social_media"]),
            "ip_address": f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
        }
    
    def generate_friend_request_sent(self, user: Dict, target_user: Dict, timestamp: Optional[datetime] = None) -> Dict:
        """1.4 FriendRequestSent - Generate friend request sent event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return {
            "event_type": "friend_request_sent",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "target_user_id": target_user["id"],
            "target_username": target_user["username"],
            "request_id": str(uuid.uuid4()),
        }
    
    def generate_friend_request_accepted(self, user: Dict, requester: Dict, request_id: str, 
                                        timestamp: Optional[datetime] = None) -> Dict:
        """1.4 FriendRequestAccepted - Generate friend request accepted event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return {
            "event_type": "friend_request_accepted",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "requester_id": requester["id"],
            "requester_username": requester["username"],
            "request_id": request_id,
        }
    
    def generate_game_purchased(self, user: Dict, game: Dict, timestamp: Optional[datetime] = None) -> Dict:
        """1.5 GamePurchased - Generate game purchase event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return {
            "event_type": "game_purchased",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "game_id": game["id"],
            "game_name": game["name"],
            "price": game["price"],
            "currency": "EUR",
            "payment_method": random.choice(self.PAYMENT_METHODS),
            "purchase_id": str(uuid.uuid4()),
        }
    
    def generate_user_platform_retention(self, user: Dict, days_since_last_visit: int,
                                        timestamp: Optional[datetime] = None) -> Dict:
        """1.6 UserPlatformRetention - Generate platform retention event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        last_visit = timestamp - timedelta(days=days_since_last_visit)
        
        return {
            "event_type": "user_platform_retention",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "logged_in_at": timestamp.isoformat(),
            "last_login_at": last_visit.isoformat(),
            "days_since_last_visit": days_since_last_visit,
            "retention_category": "3_day" if days_since_last_visit <= 3 else "10_day" if days_since_last_visit <= 10 else "30_day",
        }
    
    # ========== GAME EVENTS ==========
    
    def generate_game_ended(self, user: Dict, game: Dict, timestamp: Optional[datetime] = None) -> Dict:
        """2.1 GameEnded - Generate game ended event with realistic patterns"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Realistische game duur gebaseerd op game type
        base_duration = game["avg_duration"]
        variation = random.uniform(0.5, 1.5)
        duration_ms = int(base_duration * variation * 1000)
        
        # AI opponent (70% van de tijd)
        vs_ai = random.random() < 0.7
        
        # Resultaat bepalen - AI wint 40% van de tijd
        if vs_ai:
            result = random.choices(["win", "loss", "draw", "cancelled"], weights=[35, 40, 20, 5])[0]
        else:
            result = random.choices(["win", "loss", "draw", "cancelled"], weights=[45, 45, 8, 2])[0]
        
        # Moves gebaseerd op game duur (ongeveer 1 move per 5 seconden)
        moves_total = random.randint(int(duration_ms / 5000), int(duration_ms / 3000))
        
        return {
            "event_type": "game_ended",
            "timestamp": timestamp.isoformat(),
            "session_id": str(uuid.uuid4()),
            "game_id": game["id"],
            "game_name": game["name"],
            "player_id": user["id"],
            "username": user["username"],
            "duration_ms": duration_ms,
            "duration_seconds": duration_ms // 1000,
            "moves_total": moves_total,
            "vs_ai": vs_ai,
            "result": result,
        }
    
    def generate_achievement_unlocked(self, user: Dict, achievement: Dict, game: Dict,
                                     timestamp: Optional[datetime] = None) -> Dict:
        """2.2 AchievementUnlocked - Generate achievement unlocked event with points"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return {
            "event_type": "achievement_unlocked",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "achievement_id": achievement["id"],
            "achievement_name": achievement["name"],
            "game_id": game["id"],
            "game_name": game["name"],
            "points_awarded": achievement["points"],
        }
    
    def generate_game_favorited(self, user: Dict, game: Dict, timestamp: Optional[datetime] = None) -> Dict:
        """2.3 GameFavorited - Generate game favorited event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
            
        return {
            "event_type": "game_favorited",
            "timestamp": timestamp.isoformat(),
            "game_id": game["id"],
            "game_name": game["name"],
            "user_id": user["id"],
            "username": user["username"],
        }
    
    def generate_user_game_retention(self, user: Dict, game: Dict, days_since_last_play: int,
                                    timestamp: Optional[datetime] = None) -> Dict:
        """2.4 UserGameRetention - Generate game retention event"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        last_play = timestamp - timedelta(days=days_since_last_play)
        # Game sessie duur: 5-60 minuten
        session_duration = random.randint(5, 60)
        end_timestamp = timestamp + timedelta(minutes=session_duration)
        
        return {
            "event_type": "user_game_retention",
            "timestamp": timestamp.isoformat(),
            "user_id": user["id"],
            "username": user["username"],
            "game_id": game["id"],
            "game_name": game["name"],
            "timestamp_start_game": timestamp.isoformat(),
            "timestamp_end_game": end_timestamp.isoformat(),
            "last_played_at": last_play.isoformat(),
            "days_since_last_play": days_since_last_play,
            "retention_category": "3_day" if days_since_last_play <= 3 else "10_day" if days_since_last_play <= 10 else "30_day",
            "session_duration_minutes": session_duration,
        }
    
    # ========== SESSION GENERATORS ==========
    
    def generate_realistic_session(self, base_timestamp: Optional[datetime] = None):
        """Generate a realistic user session with all event types"""
        if base_timestamp is None:
            base_timestamp = datetime.now(timezone.utc)
        
        user = random.choice(self.USERS)
        current_time = base_timestamp
        
        # 1. Login event
        login_event = self.generate_user_logged_in(user, current_time)
        session_id = login_event["session_id"]
        login_timestamp = current_time  # Keep datetime object for logout
        self.send_event(login_event)
        time.sleep(0.05)
        current_time += timedelta(seconds=2)
        
        # 2. Platform retention check (30% kans)
        if random.random() < 0.3:
            days_since = random.choice([1, 2, 3, 5, 7, 10, 15, 30])
            retention_event = self.generate_user_platform_retention(user, days_since, current_time)
            self.send_event(retention_event)
            time.sleep(0.05)
            current_time += timedelta(seconds=1)
        
        # 3. Session activities (2-6 activiteiten)
        num_activities = random.randint(2, 6)
        for i in range(num_activities):
            activity_type = random.choices(
                ["play_game", "friend_interaction", "purchase_game", "favorite_game"],
                weights=[60, 20, 10, 10]
            )[0]
            
            if activity_type == "play_game":
                game = random.choice(self.GAMES)
                
                # Game retention event (50% kans)
                if random.random() < 0.5:
                    days_since = random.choice([1, 2, 3, 5, 7, 10, 14, 30])
                    retention = self.generate_user_game_retention(user, game, days_since, current_time)
                    self.send_event(retention)
                    time.sleep(0.05)
                    current_time += timedelta(seconds=1)
                
                # Game ended event
                game_ended = self.generate_game_ended(user, game, current_time)
                self.send_event(game_ended)
                time.sleep(0.05)
                current_time += timedelta(seconds=game_ended["duration_seconds"])
                
                # Achievement (15% kans bij win)
                if game_ended["result"] == "win" and random.random() < 0.15:
                    achievement = random.choice(self.ACHIEVEMENTS)
                    ach_event = self.generate_achievement_unlocked(user, achievement, game, current_time)
                    self.send_event(ach_event)
                    time.sleep(0.05)
                    current_time += timedelta(seconds=2)
            
            elif activity_type == "friend_interaction":
                # Friend request flow
                target_user = random.choice([u for u in self.USERS if u["id"] != user["id"]])
                friend_req = self.generate_friend_request_sent(user, target_user, current_time)
                self.send_event(friend_req)
                time.sleep(0.05)
                current_time += timedelta(minutes=random.randint(1, 30))
                
                # 70% kans dat request geaccepteerd wordt
                if random.random() < 0.7:
                    accepted = self.generate_friend_request_accepted(
                        target_user, user, friend_req["request_id"], current_time
                    )
                    self.send_event(accepted)
                    time.sleep(0.05)
                    current_time += timedelta(seconds=1)
            
            elif activity_type == "purchase_game":
                # Alleen betaalde games
                paid_games = [g for g in self.GAMES if g["price"] > 0]
                if paid_games:
                    game = random.choice(paid_games)
                    purchase = self.generate_game_purchased(user, game, current_time)
                    self.send_event(purchase)
                    time.sleep(0.05)
                    current_time += timedelta(seconds=5)
            
            elif activity_type == "favorite_game":
                game = random.choice(self.GAMES)
                favorite = self.generate_game_favorited(user, game, current_time)
                self.send_event(favorite)
                time.sleep(0.05)
                current_time += timedelta(seconds=1)
            
            # Pauze tussen activiteiten
            current_time += timedelta(minutes=random.randint(1, 10))
        
        # 4. Logout event
        logout_event = self.generate_user_logged_out(user, session_id, login_timestamp)
        self.send_event(logout_event)
        time.sleep(0.05)
    
    def generate_new_user_registration(self, timestamp: Optional[datetime] = None):
        """Generate a new user registration with first session"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Registration
        reg_event = self.generate_user_registered(timestamp)
        self.send_event(reg_event)
        time.sleep(0.1)
        
        print(f"   📝 New user registered: {reg_event['username']}")
    
    def generate_historical_data(self, days: int = 30):
        """Generate historical data for the past N days"""
        print(f"\n📊 Generating {days} days of historical data...")
        print("=" * 60)
        
        now = datetime.now(timezone.utc)
        total_events = 0
        
        for day in range(days, 0, -1):
            day_timestamp = now - timedelta(days=day)
            
            # Variabel aantal sessies per dag (5-20)
            # Meer sessies in weekend
            is_weekend = day_timestamp.weekday() in [5, 6]
            num_sessions = random.randint(12, 25) if is_weekend else random.randint(5, 15)
            
            # Nieuwe registraties (0-3 per dag)
            num_registrations = random.randint(0, 3)
            
            print(f"\n📅 Day -{day} ({day_timestamp.strftime('%Y-%m-%d')}): {num_sessions} sessions, {num_registrations} new users")
            
            # Registraties
            for _ in range(num_registrations):
                reg_time = day_timestamp + timedelta(hours=random.randint(8, 22))
                self.generate_new_user_registration(reg_time)
                total_events += 1
            
            # Sessies verspreid over de dag
            for i in range(num_sessions):
                # Peak hours: 18:00-23:00 (avond)
                hour = random.choices(
                    range(24),
                    weights=[1,1,1,1,1,2,3,5,7,10,8,6,5,4,3,5,8,12,15,18,15,10,5,3]
                )[0]
                
                session_time = day_timestamp + timedelta(
                    hours=hour,
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                
                self.generate_realistic_session(session_time)
                total_events += 5  # Gemiddeld aantal events per sessie
                
                if (i + 1) % 5 == 0:
                    print(f"   ✓ {i + 1}/{num_sessions} sessions generated")
        
        print("\n" + "=" * 60)
        print(f"✅ Historical data generation complete!")
        print(f"📈 Approximate total events: {total_events}")
        return total_events


def main():
    """Main function to generate test data"""
    print("🎮 Analytics Platform - Realistic Test Data Generator")
    print("=" * 70)
    print("\nThis generator creates realistic events for:")
    print("  • Platform Events: Login, Logout, Registration, Friends, Purchases")
    print("  • Game Events: Game Ended, Achievements, Favorites, Retention")
    print("  • Retention Analysis: Platform & Game retention patterns")
    print("=" * 70)
    
    generator = EventGenerator(
        rabbitmq_host="localhost",
        rabbitmq_port=5672,
        rabbitmq_user="admin",
        rabbitmq_password="admin"
    )
    
    try:
        print("\n📋 Choose generation mode:")
        print("  1. Quick test (10 recent sessions)")
        print("  2. Medium dataset (30 days historical data)")
        print("  3. Large dataset (90 days historical data)")
        print("  4. Custom sessions (specify amount)")
        
        choice = input("\nYour choice (1-4): ").strip()
        
        if choice == "1":
            print("\n🚀 Generating 10 recent sessions...")
            for i in range(10):
                print(f"\n📊 Session {i + 1}/10")
                generator.generate_realistic_session()
                time.sleep(0.3)
            print("\n✅ Quick test complete!")
        
        elif choice == "2":
            generator.generate_historical_data(days=30)
        
        elif choice == "3":
            generator.generate_historical_data(days=90)
        
        elif choice == "4":
            num_sessions = int(input("How many sessions to generate? ") or "10")
            print(f"\nGenerating {num_sessions} sessions...")
            for i in range(num_sessions):
                print(f"\n📊 Session {i + 1}/{num_sessions}")
                generator.generate_realistic_session()
                time.sleep(0.3)
            print(f"\n✅ Generated {num_sessions} sessions!")
        
        else:
            print("❌ Invalid choice")
            return
        
        print("\n" + "=" * 70)
        print("✅ Data generation complete!")
        print("\n📊 Next steps:")
        print("  1. Check Kibana at http://localhost:5601")
        print("  2. View RabbitMQ at http://localhost:15672")
        print("  3. Verify data in Elasticsearch indices")
        print("\n💡 Events are being processed by Logstash and stored in Elasticsearch")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        generator.close()
        print("\n🔌 RabbitMQ connection closed")


if __name__ == "__main__":
    main()

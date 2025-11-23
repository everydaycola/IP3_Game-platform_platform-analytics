#!/usr/bin/env python3
"""
Test Data Generator for Platform Events
Generates realistic game platform events and sends them to RabbitMQ
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List
import pika
import uuid


class EventGenerator:
    """Generates realistic platform events for testing"""
    
    # Sample data
    USERS = [
        {"id": "user_001", "username": "Jan_Jansen", "email": "jan@example.com"},
        {"id": "user_002", "username": "Piet_Pieters", "email": "piet@example.com"},
        {"id": "user_003", "username": "Sara_Smith", "email": "sara@example.com"},
        {"id": "user_004", "username": "Lisa_De_Vries", "email": "lisa@example.com"},
        {"id": "user_005", "username": "Tom_Van_Berg", "email": "tom@example.com"},
        {"id": "user_006", "username": "Emma_Bakker", "email": "emma@example.com"},
        {"id": "user_007", "username": "Max_Mueller", "email": "max@example.com"},
        {"id": "user_008", "username": "Sophie_Dubois", "email": "sophie@example.com"},
    ]
    
    GAMES = [
        {"id": "tictactoe", "name": "Tic-Tac-Toe", "avg_duration": 120},
        {"id": "chess", "name": "Chess", "avg_duration": 1800},
        {"id": "checkers", "name": "Checkers", "avg_duration": 900},
        {"id": "connect4", "name": "Connect Four", "avg_duration": 300},
        {"id": "reversi", "name": "Reversi", "avg_duration": 600},
    ]
    
    ACHIEVEMENTS = [
        {"id": "first_win", "name": "First Victory"},
        {"id": "win_streak_5", "name": "5 Game Win Streak"},
        {"id": "speed_demon", "name": "Speed Demon"},
        {"id": "master_tactician", "name": "Master Tactician"},
        {"id": "social_butterfly", "name": "Social Butterfly"},
    ]
    
    DIFFICULTY_LEVELS = ["easy", "medium", "hard", "expert"]
    DEVICES = ["desktop", "mobile", "tablet"]
    BROWSERS = ["Chrome", "Firefox", "Safari", "Edge"]
    PLATFORMS = ["Windows", "macOS", "Linux", "iOS", "Android"]
    
    def __init__(self, rabbitmq_host: str = "localhost", rabbitmq_port: int = 5672,
                 rabbitmq_user: str = "admin", rabbitmq_password: str = "admin"):
        """Initialize connection to RabbitMQ"""
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials
        )
        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()
        
        # Declare queue
        self.channel.queue_declare(queue='platform.events', durable=True)
        
    def close(self):
        """Close RabbitMQ connection"""
        self.connection.close()
    
    def send_event(self, event: Dict):
        """Send event to RabbitMQ"""
        self.channel.basic_publish(
            exchange='',
            routing_key='platform.events',
            body=json.dumps(event),
            properties=pika.BasicProperties(
                delivery_mode=2,  # make message persistent
            )
        )
        print(f"✓ Sent: {event['event_type']}")
    
    def generate_user_logged_in(self, user: Dict) -> Dict:
        """Generate user login event"""
        return {
            "event_type": "user_logged_in",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "session_id": str(uuid.uuid4()),
            "ip_address": f"192.168.1.{random.randint(1, 254)}",
            "device_type": random.choice(self.DEVICES),
            "browser": random.choice(self.BROWSERS),
            "platform": random.choice(self.PLATFORMS),
        }
    
    def generate_user_logged_out(self, user: Dict, session_id: str, login_time: datetime) -> Dict:
        """Generate user logout event"""
        logout_time = login_time + timedelta(minutes=random.randint(15, 180))
        return {
            "event_type": "user_logged_out",
            "timestamp": logout_time.isoformat() + "Z",
            "user_id": user["id"],
            "username": user["username"],
            "session_id": session_id,
            "session_start": login_time.isoformat() + "Z",
            "session_end": logout_time.isoformat() + "Z",
        }
    
    def generate_user_registered(self) -> Dict:
        """Generate user registration event"""
        new_user_id = f"user_{random.randint(100, 999)}"
        return {
            "event_type": "user_registered",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": new_user_id,
            "username": f"NewUser_{random.randint(1000, 9999)}",
            "email": f"user{random.randint(100, 999)}@example.com",
            "ip_address": f"192.168.1.{random.randint(1, 254)}",
        }
    
    def generate_game_started(self, user: Dict, game: Dict) -> Dict:
        """Generate game started event"""
        has_ai = random.choice([True, False])
        player_count = 1 if has_ai else 2
        
        return {
            "event_type": "game_started",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "game_id": str(uuid.uuid4()),
            "game_type": game["id"],
            "game_name": game["name"],
            "user_id": user["id"],
            "username": user["username"],
            "player_count": player_count,
            "has_ai_player": has_ai,
            "difficulty_level": random.choice(self.DIFFICULTY_LEVELS) if has_ai else None,
        }
    
    def generate_game_ended(self, game_started_event: Dict) -> Dict:
        """Generate game ended event"""
        duration = random.randint(60, 3600)
        return {
            "event_type": "game_ended",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "game_id": game_started_event["game_id"],
            "game_type": game_started_event["game_type"],
            "user_id": game_started_event["user_id"],
            "game_duration_seconds": duration,
            "completed": True,
        }
    
    def generate_winner_declared(self, game_started_event: Dict) -> Dict:
        """Generate winner declared event"""
        is_ai_winner = game_started_event["has_ai_player"] and random.choice([True, False])
        
        return {
            "event_type": "winner_declared",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "game_id": game_started_event["game_id"],
            "game_type": game_started_event["game_type"],
            "winner_id": "ai_player" if is_ai_winner else game_started_event["user_id"],
            "winner_type": "ai" if is_ai_winner else "human",
            "winning_score": random.randint(1, 100),
        }
    
    def generate_game_abandoned(self, game_started_event: Dict) -> Dict:
        """Generate game abandoned event"""
        return {
            "event_type": "game_abandoned",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "game_id": game_started_event["game_id"],
            "game_type": game_started_event["game_type"],
            "user_id": game_started_event["user_id"],
            "game_duration_seconds": random.randint(10, 300),
        }
    
    def generate_achievement_unlocked(self, user: Dict, achievement: Dict) -> Dict:
        """Generate achievement unlocked event"""
        return {
            "event_type": "achievement_unlocked",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user["id"],
            "username": user["username"],
            "achievement_id": achievement["id"],
            "achievement_name": achievement["name"],
        }
    
    def generate_friend_added(self, user: Dict, friend: Dict) -> Dict:
        """Generate friend added event"""
        return {
            "event_type": "friend_added",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user["id"],
            "username": user["username"],
            "friend_id": friend["id"],
            "friend_username": friend["username"],
        }
    
    def generate_gamepage_visit(self, user: Dict, game: Dict) -> Dict:
        """Generate game page visit event"""
        return {
            "event_type": "gamePage_visit",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user["id"],
            "game_id": game["id"],
            "game_name": game["name"],
            "page_url": f"/games/{game['id']}",
            "referrer": random.choice(["/", "/games", "/profile", "/leaderboard"]),
        }
    
    def generate_purchase_made(self, user: Dict) -> Dict:
        """Generate purchase made event"""
        products = [
            {"id": "premium_monthly", "amount": 4.99},
            {"id": "premium_yearly", "amount": 49.99},
            {"id": "game_pack_1", "amount": 9.99},
            {"id": "avatar_pack", "amount": 2.99},
        ]
        product = random.choice(products)
        
        return {
            "event_type": "purchase_made",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": user["id"],
            "purchase_id": str(uuid.uuid4()),
            "product_id": product["id"],
            "amount": product["amount"],
            "currency": "EUR",
        }
    
    def generate_payment_made(self, purchase_event: Dict) -> Dict:
        """Generate payment made event"""
        return {
            "event_type": "payment_made",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "user_id": purchase_event["user_id"],
            "purchase_id": purchase_event["purchase_id"],
            "amount": purchase_event["amount"],
            "currency": purchase_event["currency"],
            "payment_method": random.choice(["credit_card", "paypal", "ideal", "bancontact"]),
            "payment_status": random.choice(["completed", "completed", "completed", "failed"]),
        }
    
    def generate_realistic_session(self):
        """Generate a realistic user session with multiple events"""
        user = random.choice(self.USERS)
        
        # Login
        login_time = datetime.utcnow()
        login_event = self.generate_user_logged_in(user)
        session_id = login_event["session_id"]
        self.send_event(login_event)
        time.sleep(0.1)
        
        # Random activities during session
        num_activities = random.randint(2, 8)
        for _ in range(num_activities):
            activity = random.choice([
                "game", "gamepage_visit", "friend_add", "achievement", "purchase"
            ])
            
            if activity == "game":
                # Complete game flow
                game = random.choice(self.GAMES)
                game_started = self.generate_game_started(user, game)
                self.send_event(game_started)
                time.sleep(0.1)
                
                # 80% chance game completes, 20% abandoned
                if random.random() < 0.8:
                    winner = self.generate_winner_declared(game_started)
                    self.send_event(winner)
                    time.sleep(0.1)
                    
                    game_ended = self.generate_game_ended(game_started)
                    self.send_event(game_ended)
                    time.sleep(0.1)
                    
                    # 10% chance of achievement
                    if random.random() < 0.1:
                        achievement = random.choice(self.ACHIEVEMENTS)
                        ach_event = self.generate_achievement_unlocked(user, achievement)
                        self.send_event(ach_event)
                        time.sleep(0.1)
                else:
                    abandoned = self.generate_game_abandoned(game_started)
                    self.send_event(abandoned)
                    time.sleep(0.1)
            
            elif activity == "gamepage_visit":
                game = random.choice(self.GAMES)
                visit = self.generate_gamepage_visit(user, game)
                self.send_event(visit)
                time.sleep(0.1)
            
            elif activity == "friend_add":
                friend = random.choice([u for u in self.USERS if u != user])
                friend_event = self.generate_friend_added(user, friend)
                self.send_event(friend_event)
                time.sleep(0.1)
            
            elif activity == "purchase" and random.random() < 0.1:  # 10% chance
                purchase = self.generate_purchase_made(user)
                self.send_event(purchase)
                time.sleep(0.1)
                
                payment = self.generate_payment_made(purchase)
                self.send_event(payment)
                time.sleep(0.1)
        
        # Logout
        logout_event = self.generate_user_logged_out(user, session_id, login_time)
        self.send_event(logout_event)
        time.sleep(0.1)


def main():
    """Main function to generate test data"""
    print("🎮 Platform Events Test Data Generator")
    print("=" * 50)
    
    generator = EventGenerator(
        rabbitmq_host="localhost",
        rabbitmq_port=5672,
        rabbitmq_user="admin",
        rabbitmq_password="admin"
    )
    
    try:
        # Generate multiple user sessions
        num_sessions = int(input("How many user sessions to generate? (default: 10): ") or "10")
        
        print(f"\nGenerating {num_sessions} realistic user sessions...")
        print("-" * 50)
        
        for i in range(num_sessions):
            print(f"\n📊 Session {i + 1}/{num_sessions}")
            generator.generate_realistic_session()
            time.sleep(0.5)  # Small delay between sessions
        
        print("\n" + "=" * 50)
        print(f"✅ Successfully generated events for {num_sessions} sessions!")
        print("\n💡 Check your Kibana dashboard at http://localhost:5601")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        generator.close()
        print("🔌 Connection closed")


if __name__ == "__main__":
    main()

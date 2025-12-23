#!/usr/bin/env python3
"""
User Retention & Engagement Data Generator
Generates realistic session events for retention analysis with proper cohort behavior

This script simulates:
- New user onboarding
- Returning users with realistic patterns
- Gradual churn (D1 > D7 > D30)
- Power users and casual users
- Daily and weekly usage patterns
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set
import pika
import uuid
from collections import defaultdict


class RetentionDataGenerator:
    """Generates realistic user retention and engagement events"""
    
    # User behavior profiles
    USER_PROFILES = {
        'power_user': {
            'weight': 0.15,  # 15% of users
            'd1_retention': 0.90,
            'd7_retention': 0.85,
            'd30_retention': 0.75,
            'sessions_per_day': (3, 8),
            'session_duration': (1800, 7200)  # 30min - 2h
        },
        'regular_user': {
            'weight': 0.35,  # 35% of users
            'd1_retention': 0.60,
            'd7_retention': 0.40,
            'd30_retention': 0.25,
            'sessions_per_day': (1, 3),
            'session_duration': (900, 3600)  # 15min - 1h
        },
        'casual_user': {
            'weight': 0.30,  # 30% of users
            'd1_retention': 0.30,
            'd7_retention': 0.15,
            'd30_retention': 0.05,
            'sessions_per_day': (1, 2),
            'session_duration': (300, 1800)  # 5min - 30min
        },
        'churned_user': {
            'weight': 0.20,  # 20% of users
            'd1_retention': 0.10,
            'd7_retention': 0.02,
            'd30_retention': 0.00,
            'sessions_per_day': (1, 1),
            'session_duration': (180, 900)  # 3min - 15min
        }
    }
    
    GAMES = [
        {"id": "game_chess", "name": "Chess"},
        {"id": "game_catan", "name": "Catan"},
        {"id": "game_risk", "name": "Risk"},
        {"id": "game_monopoly", "name": "Monopoly"},
        {"id": "game_scrabble", "name": "Scrabble"},
        {"id": "game_tictactoe", "name": "Tic-Tac-Toe"},
    ]
    
    def __init__(self, rabbitmq_host: str = "localhost", rabbitmq_port: int = 5672,
                 rabbitmq_user: str = "admin", rabbitmq_password: str = "admin"):
        """Initialize RabbitMQ connection"""
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
            
            self.exchange_name = 'platform.events'
            self.channel.exchange_declare(
                exchange=self.exchange_name,
                exchange_type='topic',
                durable=True
            )
            
            # Ensure queue exists for session events
            queue_name = 'queue.game.session.started'
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.queue_bind(
                exchange=self.exchange_name,
                queue=queue_name,
                routing_key='game.session.started'
            )
            
            print("✅ RabbitMQ connection established")
            
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
    
    def send_event(self, event: Dict):
        """Send event to RabbitMQ"""
        routing_key = 'game.session.started'
        
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                    headers={'event_type': 'session_started'}
                )
            )
        except Exception as e:
            print(f"❌ Failed to send event: {e}")
            raise
    
    def assign_user_profile(self) -> str:
        """Randomly assign a user behavior profile based on weights"""
        profiles = list(self.USER_PROFILES.keys())
        weights = [self.USER_PROFILES[p]['weight'] for p in profiles]
        return random.choices(profiles, weights=weights)[0]
    
    def should_user_return(self, profile: str, days_since_first: int) -> bool:
        """Determine if user should return based on profile and days since first session"""
        config = self.USER_PROFILES[profile]
        
        if days_since_first == 1:
            return random.random() < config['d1_retention']
        elif days_since_first <= 7:
            return random.random() < config['d7_retention']
        elif days_since_first <= 30:
            return random.random() < config['d30_retention']
        else:
            # Long-term retention decreases gradually
            retention_rate = config['d30_retention'] * (0.95 ** (days_since_first - 30))
            return random.random() < retention_rate
    
    def generate_session_event(self, player_id: str, timestamp: datetime, game: Dict = None) -> Dict:
        """Generate a session_started event"""
        if game is None:
            game = random.choice(self.GAMES)
        
        return {
            "event_type": "session_started",
            "@timestamp": timestamp.isoformat().replace('+00:00', 'Z'),
            "player_id": player_id,
            "session_id": str(uuid.uuid4()),
            "game_id": game["id"],
            "game_name": game["name"]
        }
    
    def generate_historical_retention_data(self, days: int = 60, new_users_per_day: int = 20):
        """
        Generate historical retention data with realistic cohort behavior
        
        Args:
            days: Number of days of historical data to generate
            new_users_per_day: Average number of new users registering per day
        """
        print(f"\n📊 Generating {days} days of retention data...")
        print(f"   Target: ~{new_users_per_day} new users per day")
        print("=" * 70)
        
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)
        
        # Track user cohorts: {user_id: {profile, first_session_date, last_session_date}}
        users: Dict[str, Dict] = {}
        events_sent = 0
        total_sessions = 0
        
        # Generate events day by day
        for day_offset in range(days + 1):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Determine new users for this day (with some randomness)
            is_weekend = current_date.weekday() in [5, 6]
            new_users_today = random.randint(
                int(new_users_per_day * 0.7),
                int(new_users_per_day * 1.3)
            )
            if is_weekend:
                new_users_today = int(new_users_today * 1.4)  # More signups on weekends
            
            sessions_today = 0
            
            # Add new users (onboarding)
            for _ in range(new_users_today):
                user_id = f"player_{len(users) + 1:05d}"
                profile = self.assign_user_profile()
                
                users[user_id] = {
                    'profile': profile,
                    'first_session': current_date,
                    'last_session': current_date
                }
                
                # New user first session (usually during peak hours)
                session_time = self.get_random_session_time(current_date, is_first_session=True)
                event = self.generate_session_event(user_id, session_time)
                self.send_event(event)
                
                events_sent += 1
                sessions_today += 1
            
            # Check existing users for returning sessions
            for user_id, user_data in list(users.items()):
                days_since_first = (current_date - user_data['first_session']).days
                
                # Skip if this is their first day (already generated session above)
                if days_since_first == 0:
                    continue
                
                # Check if user should return today
                if self.should_user_return(user_data['profile'], days_since_first):
                    profile_config = self.USER_PROFILES[user_data['profile']]
                    sessions_count = random.randint(*profile_config['sessions_per_day'])
                    
                    # Generate multiple sessions for active users
                    for _ in range(sessions_count):
                        session_time = self.get_random_session_time(current_date)
                        event = self.generate_session_event(user_id, session_time)
                        self.send_event(event)
                        
                        events_sent += 1
                        sessions_today += 1
                    
                    # Update last session date
                    user_data['last_session'] = current_date
            
            total_sessions += sessions_today
            
            # Progress update
            if (day_offset + 1) % 10 == 0 or day_offset == 0 or day_offset == days:
                print(f"  Day {day_offset + 1:3d}/{days} ({date_str}): "
                      f"{sessions_today:4d} sessions, {new_users_today:3d} new users, "
                      f"{len(users):5d} total users")
        
        print("\n" + "=" * 70)
        print("✅ Historical retention data generation complete!")
        print(f"\n📈 Statistics:")
        print(f"   Total users created: {len(users)}")
        print(f"   Total sessions: {total_sessions}")
        print(f"   Events sent: {events_sent}")
        print(f"   Average sessions per day: {total_sessions / (days + 1):.1f}")
        print(f"\n👥 User Profile Distribution:")
        
        profile_counts = defaultdict(int)
        for user_data in users.values():
            profile_counts[user_data['profile']] += 1
        
        for profile, count in profile_counts.items():
            percentage = (count / len(users)) * 100
            print(f"   {profile:15s}: {count:5d} ({percentage:5.1f}%)")
        
        # Calculate actual retention metrics
        print(f"\n📊 Retention Metrics Preview:")
        self.calculate_retention_preview(users, now)
        
        return events_sent
    
    def get_random_session_time(self, date: datetime, is_first_session: bool = False) -> datetime:
        """Generate a realistic session time with peak hours"""
        if is_first_session:
            # New users typically join during peak hours (18:00-22:00)
            hour = random.choices(
                range(24),
                weights=[1,1,1,1,1,2,2,3,4,5,5,5,4,3,3,4,6,10,15,18,15,10,5,3]
            )[0]
        else:
            # Regular sessions distributed throughout the day with evening peak
            hour = random.choices(
                range(24),
                weights=[1,1,1,1,1,2,3,5,7,10,9,7,6,5,4,5,8,12,15,16,14,10,6,3]
            )[0]
        
        return date.replace(
            hour=hour,
            minute=random.randint(0, 59),
            second=random.randint(0, 59),
            microsecond=0
        )
    
    def calculate_retention_preview(self, users: Dict, reference_date: datetime):
        """Calculate and display retention metrics preview"""
        # Find users who started 1, 7, and 30 days ago
        cohorts = {
            1: [],
            7: [],
            30: []
        }
        
        for user_id, user_data in users.items():
            days_since_first = (reference_date - user_data['first_session']).days
            
            for cohort_day in cohorts.keys():
                if days_since_first >= cohort_day:
                    cohorts[cohort_day].append(user_data)
        
        # Calculate retention for each cohort
        for cohort_day, cohort_users in cohorts.items():
            if not cohort_users:
                continue
            
            retained = 0
            for user_data in cohort_users:
                days_since_first = (reference_date - user_data['first_session']).days
                days_since_last = (reference_date - user_data['last_session']).days
                
                # User is retained if they had a session within the retention window
                if cohort_day == 1 and days_since_last <= 1:
                    retained += 1
                elif cohort_day == 7 and days_since_last <= 7:
                    retained += 1
                elif cohort_day == 30 and days_since_last <= 30:
                    retained += 1
            
            retention_rate = (retained / len(cohort_users)) * 100 if cohort_users else 0
            print(f"   D{cohort_day:2d} Retention: {retention_rate:5.1f}% "
                  f"({retained}/{len(cohort_users)} users)")


def main():
    """Main function"""
    print("🎯 User Retention & Engagement Data Generator")
    print("=" * 70)
    print("\nThis generator creates realistic session events for retention analysis:")
    print("  • Simulates different user behavior profiles")
    print("  • Generates realistic retention curves (D1 > D7 > D30)")
    print("  • Power users, regular users, casual users, and churned users")
    print("  • Peak hours and weekend patterns")
    print("=" * 70)
    
    generator = RetentionDataGenerator(
        rabbitmq_host="localhost",
        rabbitmq_port=5672,
        rabbitmq_user="admin",
        rabbitmq_password="admin"
    )
    
    try:
        print("\n📋 Choose generation mode:")
        print("  1. Small dataset (30 days, 15 users/day)")
        print("  2. Medium dataset (60 days, 20 users/day) - RECOMMENDED")
        print("  3. Large dataset (90 days, 25 users/day)")
        print("  4. Custom (specify days and users per day)")
        
        choice = input("\nYour choice (1-4): ").strip() or "2"
        
        if choice == "1":
            generator.generate_historical_retention_data(days=30, new_users_per_day=15)
        elif choice == "2":
            generator.generate_historical_retention_data(days=60, new_users_per_day=20)
        elif choice == "3":
            generator.generate_historical_retention_data(days=90, new_users_per_day=25)
        elif choice == "4":
            days = int(input("Number of days: ") or "60")
            users_per_day = int(input("New users per day: ") or "20")
            generator.generate_historical_retention_data(days=days, new_users_per_day=users_per_day)
        else:
            print("❌ Invalid choice, using default (option 2)")
            generator.generate_historical_retention_data(days=60, new_users_per_day=20)
        
        print("\n" + "=" * 70)
        print("✅ Data generation complete!")
        print("\n📊 Next steps:")
        print("  1. Wait 30-60 seconds for Logstash to process events")
        print("  2. Run: python setup/create_retention_transforms.py")
        print("  3. Run: python scripts/create_retention_dashboard_complete.py")
        print("  4. Check Kibana at http://localhost:5601")
        print("\n💡 Events are being processed and stored in Elasticsearch")
        
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

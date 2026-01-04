#!/usr/bin/env python3
"""
Game Performance Data Generator
Generates realistic game session events for game performance analysis

This script simulates:
- Game sessions (started, ended, abandoned)
- Different games with varying popularity
- Session duration patterns
- Completion and abandonment rates
- Unique players per game
- Daily activity patterns (weekday vs weekend)
- Hourly patterns (peak times)
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict
import pika
import uuid
from collections import defaultdict


class GamePerformanceDataGenerator:
    """Generates realistic game performance events"""

    # Games with different characteristics
    GAMES = [
        {
            "id": "game_catan",
            "name": "Catan",
            "popularity_weight": 0.35,  # Most popular - 35%
            "avg_duration_minutes": 45,  # Long strategy game
            "completion_rate": 0.68,
            "abandon_rate": 0.32
        },
        {
            "id": "game_ticket_to_ride",
            "name": "Ticket to Ride",
            "popularity_weight": 0.30,  # 30%
            "avg_duration_minutes": 30,  # Medium length
            "completion_rate": 0.72,
            "abandon_rate": 0.28
        },
        {
            "id": "game_prototype",
            "name": "Prototype spel",
            "popularity_weight": 0.20,  # 20% - New game being tested
            "avg_duration_minutes": 15,  # Short test sessions
            "completion_rate": 0.58,  # Lower completion due to bugs
            "abandon_rate": 0.42
        },
        {
            "id": "game_chess",
            "name": "Chess",
            "popularity_weight": 0.08,  # 8%
            "avg_duration_minutes": 12,  # Quick chess games
            "completion_rate": 0.75,
            "abandon_rate": 0.25
        },
        {
            "id": "game_risk",
            "name": "Risk",
            "popularity_weight": 0.05,  # 5%
            "avg_duration_minutes": 75,  # Very long strategy game
            "completion_rate": 0.60,
            "abandon_rate": 0.40
        },
        {
            "id": "game_monopoly",
            "name": "Monopoly",
            "popularity_weight": 0.02,  # 2% - Least popular
            "avg_duration_minutes": 90,  # Notorious for long games
            "completion_rate": 0.55,
            "abandon_rate": 0.45
        }
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

            # Ensure queues exist
            for queue_suffix in ['started', 'ended', 'abandoned']:
                queue_name = f'queue.game.session.{queue_suffix}'
                self.channel.queue_declare(queue=queue_name, durable=True)
                self.channel.queue_bind(
                    exchange=self.exchange_name,
                    queue=queue_name,
                    routing_key=f'game.session.{queue_suffix}'
                )

            print("✅ RabbitMQ connection established")

        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            raise

    def close(self):
        """Close RabbitMQ connection"""
        if self.connection and not self.connection.is_closed:
            self.connection.close()

    def send_event(self, event: Dict, routing_key: str):
        """Send event to RabbitMQ"""
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json',
                    headers={'event_type': event['event_type']}
                )
            )
        except Exception as e:
            print(f"❌ Failed to send event: {e}")
            raise

    def get_random_time_in_day(self, date: datetime) -> datetime:
        """Generate random time during the day with realistic hourly distribution"""
        # Peak hours: 14:00-22:00 (higher probability)
        # Off-peak: 00:00-08:00 (lower probability)
        hour_weights = [
            2, 2, 1, 1, 1, 1, 2, 3,        # 00-07 (8 hours: low activity)
            4, 5, 6, 7, 8, 9,              # 08-13 (6 hours: morning rise)
            10, 10, 10, 10, 10, 10, 10, 10,  # 14-21 (8 hours: PEAK)
            9, 8                           # 22-23 (2 hours: evening decline)
        ]  # Total: 24 hours (0-23)

        hour = random.choices(range(24), weights=hour_weights)[0]
        minute = random.randint(0, 59)
        second = random.randint(0, 59)

        return date.replace(hour=hour, minute=minute, second=second, microsecond=0)

    def generate_game_session(self, game: Dict, player_id: str, session_time: datetime):
        """Generate a complete game session (started + ended/abandoned)"""
        session_id = str(uuid.uuid4())

        # Game started event
        started_event = {
            "event_type": "game_started",
            "@timestamp": session_time.isoformat().replace('+00:00', 'Z'),
            "game_id": game["id"],
            "game_name": game["name"],
            "player_id": player_id,
            "session_id": session_id,
            "player_count": random.choice([1, 2, 2, 3, 4]),  # Most games 2 players
            "started_at": session_time.isoformat().replace('+00:00', 'Z')
        }

        self.send_event(started_event, 'game.session.started')

        # Determine if completed or abandoned
        is_completed = random.random() < game["completion_rate"]

        # Calculate session duration (in seconds)
        # Add variance: ±40% of average duration
        avg_seconds = game["avg_duration_minutes"] * 60
        variance = avg_seconds * 0.4
        duration_seconds = int(random.gauss(avg_seconds, variance / 2))
        duration_seconds = max(60, min(duration_seconds, avg_seconds * 2))  # Min 1 min, max 2x average

        # End time
        end_time = session_time + timedelta(seconds=duration_seconds)

        if is_completed:
            # Game ended event
            ended_event = {
                "event_type": "game_ended",
                "@timestamp": end_time.isoformat().replace('+00:00', 'Z'),
                "game_id": game["id"],
                "game_name": game["name"],
                "player_id": player_id,
                "session_id": session_id,
                "session_duration_seconds": duration_seconds,
                "completed": True,
                "ended_at": end_time.isoformat().replace('+00:00', 'Z')
            }
            self.send_event(ended_event, 'game.session.ended')
        else:
            # Game abandoned event
            # Abandoned sessions are typically shorter
            abandoned_duration = int(duration_seconds * random.uniform(0.3, 0.7))
            abandon_time = session_time + timedelta(seconds=abandoned_duration)

            abandoned_event = {
                "event_type": "game_abandoned",
                "@timestamp": abandon_time.isoformat().replace('+00:00', 'Z'),
                "game_id": game["id"],
                "game_name": game["name"],
                "player_id": player_id,
                "session_id": session_id,
                "session_duration_seconds": abandoned_duration,
                "completed": False,
                "reason": random.choice(["player_quit", "player_quit", "timeout", "error"]),
                "abandoned_at": abandon_time.isoformat().replace('+00:00', 'Z')
            }
            self.send_event(abandoned_event, 'game.session.abandoned')

        return is_completed, duration_seconds

    def get_highest_player_id(self) -> int:
        """Get the highest existing player_id number from Elasticsearch"""
        try:
            import requests
            from requests.auth import HTTPBasicAuth

            url = "http://localhost:9200/platform-events-*/_search"
            query = {
                "size": 1,
                "sort": [{"player_id.keyword": "desc"}],
                "_source": ["player_id"]
            }

            response = requests.post(url, json=query, auth=HTTPBasicAuth('elastic', 'changeme'))
            if response.status_code == 200:
                hits = response.json().get('hits', {}).get('hits', [])
                if hits:
                    player_id = hits[0]['_source'].get('player_id', 'player_00000')
                    if player_id.startswith('player_'):
                        return int(player_id.split('_')[1])
            return 0
        except Exception as e:
            print(f"   ⚠️  Could not fetch highest player_id: {e}")
            return 0

    def generate_historical_data(self, days: int = 7, target_sessions_per_day: int = 140):
        """
        Generate historical game performance data

        Args:
            days: Number of days of historical data
            target_sessions_per_day: Average number of game sessions per day
        """
        print(f"\n🎮 Generating {days} days of game performance data...")
        print(f"   Target: ~{target_sessions_per_day} sessions per day")
        print("=" * 70)

        # Get starting player_id
        starting_player_num = self.get_highest_player_id() + 1
        print(f"   📍 Starting from player_{starting_player_num:05d}")
        print("=" * 70)

        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)

        # Track statistics
        total_sessions = 0
        completed_sessions = 0
        abandoned_sessions = 0
        game_stats = defaultdict(lambda: {'sessions': 0, 'unique_players': set(), 'completed': 0, 'abandoned': 0})

        # Player pool - simulate realistic player behavior
        total_players = int(target_sessions_per_day * days / 5)  # Each player plays ~5 games on average
        player_pool = [f"player_{starting_player_num + i:05d}" for i in range(total_players)]

        # Generate events day by day
        for day_offset in range(days + 1):
            current_date = start_date + timedelta(days=day_offset)
            date_str = current_date.strftime('%Y-%m-%d')

            # Weekend has more activity
            is_weekend = current_date.weekday() in [5, 6]
            sessions_today = int(target_sessions_per_day * (1.5 if is_weekend else 1.0))
            sessions_today += random.randint(-20, 20)  # Add variance

            daily_sessions = 0

            print(f"   📅 {date_str} ({'Weekend' if is_weekend else 'Weekday'}): Generating {sessions_today} sessions...", end=" ")

            for _ in range(sessions_today):
                # Select game based on popularity weight
                game = random.choices(self.GAMES, weights=[g["popularity_weight"] for g in self.GAMES])[0]

                # Select random player
                player_id = random.choice(player_pool)

                # Generate session time
                session_time = self.get_random_time_in_day(current_date)

                # Don't generate future events
                if session_time > now:
                    continue

                # Generate session
                is_completed, duration = self.generate_game_session(game, player_id, session_time)

                # Track stats
                total_sessions += 1
                daily_sessions += 1
                game_stats[game["name"]]['sessions'] += 1
                game_stats[game["name"]]['unique_players'].add(player_id)

                if is_completed:
                    completed_sessions += 1
                    game_stats[game["name"]]['completed'] += 1
                else:
                    abandoned_sessions += 1
                    game_stats[game["name"]]['abandoned'] += 1

                # Small delay to avoid overwhelming RabbitMQ
                if total_sessions % 100 == 0:
                    time.sleep(0.1)

            print(f"✅ {daily_sessions} sessions")

        # Print summary
        print("\n" + "=" * 70)
        print("📊 GENERATION SUMMARY")
        print("=" * 70)
        print(f"Total Sessions: {total_sessions:,}")
        print(f"Completed: {completed_sessions:,} ({completed_sessions/total_sessions*100:.1f}%)")
        print(f"Abandoned: {abandoned_sessions:,} ({abandoned_sessions/total_sessions*100:.1f}%)")
        print(f"\nGame Breakdown:")
        print("-" * 70)

        for game_name in sorted(game_stats.keys(), key=lambda x: game_stats[x]['sessions'], reverse=True):
            stats = game_stats[game_name]
            sessions = stats['sessions']
            unique_players = len(stats['unique_players'])
            completion_rate = stats['completed'] / sessions * 100 if sessions > 0 else 0

            print(f"  {game_name:20s}: {sessions:4d} sessions | {unique_players:3d} unique players | {completion_rate:5.1f}% completion")

        print("=" * 70)
        print("✅ Data generation complete!")
        print(f"⏳ Wait ~30 seconds for Logstash to process events...")
        print("=" * 70)


def main():
    """Main entry point"""
    print("=" * 70)
    print("🎮 GAME PERFORMANCE DATA GENERATOR")
    print("=" * 70)
    print("\nThis script generates realistic game session events including:")
    print("  - Game started/ended/abandoned events")
    print("  - Multiple games with varying popularity")
    print("  - Realistic session durations and completion rates")
    print("  - Daily and hourly activity patterns")
    print("  - Unique players per game")
    print("\n" + "=" * 70)

    print("\nSelect data generation option:")
    print("  1. Last 60 days (full historical data - recommended)")
    print("  2. Last 7 days (quick test)")
    print("  3. Custom period")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        days = 60
        sessions_per_day = 140
    elif choice == "2":
        days = 7
        sessions_per_day = 140
    elif choice == "3":
        days = int(input("Number of days: ").strip())
        sessions_per_day = int(input("Target sessions per day: ").strip())
    else:
        print("Invalid choice. Using default: 60 days")
        days = 60
        sessions_per_day = 140

    try:
        generator = GamePerformanceDataGenerator()
        generator.generate_historical_data(days=days, target_sessions_per_day=sessions_per_day)
        generator.close()
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


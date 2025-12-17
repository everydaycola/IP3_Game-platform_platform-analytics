#!/usr/bin/env python3
"""
Revenue Dashboard - Test Data Generator
Generates realistic purchase and payment events for the Opbrengsten Dashboard
"""

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List
import pika
import uuid


class RevenueDataGenerator:
    """Generates realistic revenue events for Opbrengsten Dashboard"""
    
    # Realistische game prijzen gebaseerd op populariteit
    GAMES = [
        {"id": "game_chess", "name": "Chess Master Pro", "base_price": 12.99, "popularity": 0.25},
        {"id": "game_catan", "name": "Catan Digital", "base_price": 15.99, "popularity": 0.20},
        {"id": "game_risk", "name": "Risk: Global Domination", "base_price": 14.99, "popularity": 0.18},
        {"id": "game_monopoly", "name": "Monopoly Plus", "base_price": 11.99, "popularity": 0.15},
        {"id": "game_scrabble", "name": "Scrabble GO", "base_price": 9.99, "popularity": 0.12},
        {"id": "game_cards", "name": "Ultimate Card Collection", "base_price": 7.99, "popularity": 0.10},
    ]
    
    # Payment methods met realistische distributie
    PAYMENT_METHODS = [
        {"method": "credit_card", "weight": 0.45, "success_rate": 0.95},
        {"method": "paypal", "weight": 0.30, "success_rate": 0.97},
        {"method": "ideal", "weight": 0.15, "success_rate": 0.98},
        {"method": "bancontact", "weight": 0.08, "success_rate": 0.96},
        {"method": "mastercard", "weight": 0.02, "success_rate": 0.94},
    ]
    
    # Product types voor revenue streams
    PRODUCT_TYPES = [
        {"type": "game_purchase", "weight": 0.60},
        {"type": "subscription_monthly", "price": 9.99, "weight": 0.25},
        {"type": "subscription_yearly", "price": 89.99, "weight": 0.10},
        {"type": "premium_feature", "price": 4.99, "weight": 0.05},
    ]
    
    def __init__(self, rabbitmq_host: str = "localhost", rabbitmq_port: int = 5672,
                 rabbitmq_user: str = "admin", rabbitmq_password: str = "admin"):
        """Initialize RabbitMQ connection"""
        print(f"💰 Revenue Data Generator - Connecting to RabbitMQ...")
        
        credentials = pika.PlainCredentials(rabbitmq_user, rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=rabbitmq_host,
            port=rabbitmq_port,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
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
            print(f"✓ Connected to exchange '{self.exchange_name}'")
            
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def generate_user_id(self) -> str:
        """Generate a realistic user ID"""
        return f"user_{random.randint(1000, 9999)}"
    
    def select_game_by_popularity(self) -> Dict:
        """Select a game based on popularity weights"""
        games = self.GAMES
        weights = [g["popularity"] for g in games]
        return random.choices(games, weights=weights)[0]
    
    def select_payment_method(self) -> Dict:
        """Select payment method based on usage weights"""
        methods = self.PAYMENT_METHODS
        weights = [m["weight"] for m in methods]
        return random.choices(methods, weights=weights)[0]
    
    def select_product_type(self) -> Dict:
        """Select product type based on sales distribution"""
        products = self.PRODUCT_TYPES
        weights = [p["weight"] for p in products]
        return random.choices(products, weights=weights)[0]
    
    def calculate_price_with_variation(self, base_price: float) -> float:
        """Add realistic price variation (discounts, bundles)"""
        # 20% kans op discount (5-30% off)
        if random.random() < 0.20:
            discount = random.uniform(0.05, 0.30)
            return round(base_price * (1 - discount), 2)
        
        # 5% kans op bundle upsell (+20-50%)
        elif random.random() < 0.05:
            upsell = random.uniform(1.20, 1.50)
            return round(base_price * upsell, 2)
        
        return base_price
    
    def generate_purchase_made_event(self, timestamp: datetime = None) -> Dict:
        """Generate purchase_made event volgens EVENT_SPECIFICATION.md"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        user_id = self.generate_user_id()
        product = self.select_product_type()
        
        # Determine game and price
        if product["type"] == "game_purchase":
            game = self.select_game_by_popularity()
            game_id = game["id"]
            game_name = game["name"]
            amount = self.calculate_price_with_variation(game["base_price"])
        else:
            game_id = "platform_service"
            game_name = product["type"].replace("_", " ").title()
            amount = product["price"]
        
        transaction_id = str(uuid.uuid4())
        
        event = {
            "event_type": "purchase_made",
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "game_id": game_id,
            "game_name": game_name,
            "product_type": product["type"],
            "amount": amount,
            "currency": "EUR",
            "transaction_id": transaction_id
        }
        
        return event, transaction_id
    
    def generate_payment_made_event(self, transaction_id: str, amount: float, 
                                    timestamp: datetime = None, user_id: str = None) -> Dict:
        """Generate payment_made event volgens EVENT_SPECIFICATION.md"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        payment_method_info = self.select_payment_method()
        payment_method = payment_method_info["method"]
        success_rate = payment_method_info["success_rate"]
        
        # Determine payment status based on success rate
        is_success = random.random() < success_rate
        status = "completed" if is_success else random.choice(["failed", "pending"])
        
        event = {
            "event_type": "payment_made",
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "transaction_id": transaction_id,
            "payment_method": payment_method,
            "amount": amount,
            "currency": "EUR",
            "status": status
        }
        
        return event
    
    def generate_gamepage_visit_event(self, user_id: str, game_id: str, game_name: str,
                                     timestamp: datetime = None) -> Dict:
        """Generate gamePage_visit event for conversion funnel"""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        referrers = ["homepage", "search", "direct", "social_media", "recommendation"]
        
        event = {
            "event_type": "gamePage_visit",
            "timestamp": timestamp.isoformat(),
            "user_id": user_id,
            "game_id": game_id,
            "game_name": game_name,
            "referrer": random.choice(referrers),
            "session_id": str(uuid.uuid4())
        }
        
        return event
    
    def send_event(self, event: Dict, routing_key: str):
        """Send event to RabbitMQ"""
        try:
            self.channel.basic_publish(
                exchange=self.exchange_name,
                routing_key=routing_key,
                body=json.dumps(event),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # persistent
                    content_type='application/json'
                )
            )
            print(f"✓ Sent: {event['event_type']} → {routing_key}")
            return True
        except Exception as e:
            print(f"❌ Failed to send event: {e}")
            return False
    
    def generate_complete_purchase_flow(self, timestamp: datetime = None):
        """
        Generate complete purchase flow:
        1. gamePage_visit (70% of time)
        2. purchase_made (always)
        3. payment_made (always, 95% success rate)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Generate purchase
        purchase_event, transaction_id = self.generate_purchase_made_event(timestamp)
        user_id = purchase_event["user_id"]
        game_id = purchase_event["game_id"]
        game_name = purchase_event["game_name"]
        amount = purchase_event["amount"]
        
        # 70% chance: user visited game page first (conversion funnel)
        if random.random() < 0.70:
            visit_timestamp = timestamp - timedelta(seconds=random.randint(30, 300))
            visit_event = self.generate_gamepage_visit_event(
                user_id, game_id, game_name, visit_timestamp
            )
            self.send_event(visit_event, "platform.page.visited")
            time.sleep(0.05)
        
        # Send purchase event
        self.send_event(purchase_event, "platform.transaction.purchase")
        time.sleep(0.05)
        
        # Payment happens 1-5 seconds after purchase
        payment_timestamp = timestamp + timedelta(seconds=random.randint(1, 5))
        payment_event = self.generate_payment_made_event(
            transaction_id, amount, payment_timestamp, user_id
        )
        self.send_event(payment_event, "platform.transaction.payment")
        
        return purchase_event["status"] if "status" in purchase_event else "completed"
    
    def generate_historical_data(self, days: int = 30, transactions_per_day: int = 50):
        """
        Generate historical revenue data for past X days
        Simulates realistic patterns: more sales on weekends, evening peaks
        """
        print(f"\n💰 Generating {days} days of historical revenue data...")
        print(f"📊 Target: ~{transactions_per_day} transactions per day")
        print(f"=" * 60)
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        total_transactions = 0
        total_revenue = 0.0
        
        current_date = start_date
        while current_date <= end_date:
            # Adjust transaction count based on day of week
            day_of_week = current_date.weekday()
            is_weekend = day_of_week >= 5  # Saturday, Sunday
            
            # More transactions on weekends (30% increase)
            daily_transactions = int(transactions_per_day * (1.3 if is_weekend else 1.0))
            
            print(f"\n📅 {current_date.strftime('%Y-%m-%d')} ({current_date.strftime('%A')})")
            
            for i in range(daily_transactions):
                # Spread transactions throughout the day
                # Peak hours: 14:00-16:00 and 19:00-22:00
                hour = random.choices(
                    range(0, 24),
                    weights=[1,1,1,1,1,1,2,3,4,5,6,7,8,9,10,9,8,10,12,15,14,12,8,5]
                )[0]
                
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                
                transaction_time = current_date.replace(
                    hour=hour, minute=minute, second=second
                )
                
                # Generate purchase flow
                self.generate_complete_purchase_flow(transaction_time)
                total_transactions += 1
                
                # Small delay to prevent overwhelming
                if i % 10 == 0:
                    time.sleep(0.1)
            
            print(f"   ✓ Generated {daily_transactions} transactions")
            
            # Move to next day
            current_date += timedelta(days=1)
        
        print(f"\n" + "=" * 60)
        print(f"✅ Historical data generation complete!")
        print(f"📊 Total transactions: {total_transactions}")
        print(f"🎯 Average per day: {total_transactions / days:.1f}")
        print(f"\n💡 Check Kibana Discover for the events!")
    
    def generate_realtime_simulation(self, duration_minutes: int = 10):
        """
        Simulate real-time purchases for X minutes
        Useful for testing live dashboard updates
        """
        print(f"\n🔴 LIVE: Simulating real-time purchases for {duration_minutes} minutes...")
        print(f"=" * 60)
        
        end_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        transaction_count = 0
        
        while datetime.now(timezone.utc) < end_time:
            self.generate_complete_purchase_flow()
            transaction_count += 1
            
            # Random delay between purchases (2-15 seconds)
            delay = random.uniform(2, 15)
            print(f"   💤 Waiting {delay:.1f}s for next transaction...")
            time.sleep(delay)
        
        print(f"\n✅ Real-time simulation complete! Generated {transaction_count} transactions")
    
    def close(self):
        """Close RabbitMQ connection"""
        if self.connection:
            self.connection.close()
            print("🔌 RabbitMQ connection closed")


def main():
    """Main function with interactive menu"""
    print("=" * 70)
    print("REVENUE DASHBOARD - TEST DATA GENERATOR")
    print("=" * 70)
    print("\nThis generator creates realistic purchase and payment events")
    print("for testing the Opbrengsten (Revenue) Dashboard in Kibana.\n")
    
    try:
        generator = RevenueDataGenerator()
        
        print("\n📋 Choose generation mode:")
        print("  1. Quick test (10 recent transactions)")
        print("  2. Historical data (30 days, ~50 transactions/day)")
        print("  3. Historical data (90 days, ~50 transactions/day)")
        print("  4. Real-time simulation (10 minutes live)")
        print("  5. Custom historical period")
        
        choice = input("\nYour choice (1-5): ").strip()
        
        if choice == "1":
            print("\n🚀 Generating 10 quick test transactions...")
            for i in range(10):
                generator.generate_complete_purchase_flow()
                time.sleep(0.5)
            print("\n✅ Quick test complete!")
        
        elif choice == "2":
            generator.generate_historical_data(days=30, transactions_per_day=50)
        
        elif choice == "3":
            generator.generate_historical_data(days=90, transactions_per_day=50)
        
        elif choice == "4":
            generator.generate_realtime_simulation(duration_minutes=10)
        
        elif choice == "5":
            days = int(input("Number of days: "))
            transactions = int(input("Transactions per day: "))
            generator.generate_historical_data(days=days, transactions_per_day=transactions)
        
        else:
            print("❌ Invalid choice")
        
        generator.close()
        
        print("\n" + "=" * 70)
        print("💡 NEXT STEPS:")
        print("  1. Open Kibana: http://localhost:5601")
        print("  2. Go to Discover")
        print("  3. Select 'platform-events-*' index pattern")
        print("  4. Filter by: event_type:(purchase_made OR payment_made)")
        print("  5. Create visualizations for Revenue Dashboard!")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Create Kibana Data View (Index Pattern)
"""

import requests
import time
import json
import uuid
import os

KIBANA_URL = os.getenv("KIBANA_HOST", "http://localhost:5601")
USERNAME = os.getenv("KIBANA_USER", "elastic")
PASSWORD = os.getenv("KIBANA_PASSWORD", "changeme")

def wait_for_kibana():
    """Wait for Kibana to be ready"""
    print("⏳ Waiting for Kibana to be ready...")
    for _ in range(60):
        try:
            response = requests.get(f"{KIBANA_URL}/api/status", 
                                  auth=(USERNAME, PASSWORD),
                                  timeout=5)
            if response.status_code == 200:
                print("✅ Kibana is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    
    print("❌ Kibana did not become ready in time")
    return False

def create_data_view():
    """Create the data view in Kibana"""
    
    if not wait_for_kibana():
        return False
    
    print("\n" + "="*70)
    print("📊 CREATING KIBANA DATA VIEW")
    print("="*70)
    
    # Check if data view already exists
    data_view_id = "platform-events-*"
    
    try:
        response = requests.get(
            f"{KIBANA_URL}/api/saved_objects/index-pattern/{data_view_id}",
            auth=(USERNAME, PASSWORD),
            headers={
                "kbn-xsrf": "true",
                "Content-Type": "application/json"
            }
        )
        
        if response.status_code == 200:
            print(f"✅ Data view '{data_view_id}' already exists!")
            return True
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error checking existing data view: {e}")
    
    # Create the data view
    data_view_payload = {
        "attributes": {
            "title": "platform-events-*",
            "timeFieldName": "@timestamp"
        }
    }
    
    try:
        response = requests.post(
            f"{KIBANA_URL}/api/saved_objects/index-pattern/{data_view_id}",
            auth=(USERNAME, PASSWORD),
            headers={
                "kbn-xsrf": "true",
                "Content-Type": "application/json"
            },
            json=data_view_payload
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Data view '{data_view_id}' created successfully!")
            return True
        else:
            print(f"❌ Failed to create data view: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating data view: {e}")
        return False

if __name__ == "__main__":
    success = create_data_view()
    
    if success:
        print("\n" + "="*70)
        print("✅ Data view setup complete!")
        print("="*70)
    else:
        print("\n" + "="*70)
        print("❌ Data view setup failed!")
        print("="*70)
        exit(1)

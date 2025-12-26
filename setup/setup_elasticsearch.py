#!/usr/bin/env python3
"""
Setup Elasticsearch Index Template
Uploads the platform-events index template to Elasticsearch
"""

import requests
import json
import time
from requests.auth import HTTPBasicAuth

ES_HOST = "http://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"

def wait_for_elasticsearch():
    """Wait for Elasticsearch to be ready"""
    print("⏳ Waiting for Elasticsearch to be ready...")
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = requests.get(f"{ES_HOST}/_cluster/health", 
                                   auth=HTTPBasicAuth(ES_USER, ES_PASS),
                                   timeout=5)
            if response.status_code == 200:
                print("✅ Elasticsearch is ready!")
                return True
        except:
            pass
        time.sleep(2)
        if (i + 1) % 5 == 0:
            print(f"   Still waiting... ({i + 1}/{max_attempts})")
    
    print("❌ Elasticsearch not ready after 60 seconds")
    return False

def upload_template():
    """Upload index template to Elasticsearch"""
    template_path = "elasticsearch/templates/platform-events-template.json"
    
    print(f"\n📄 Reading template from {template_path}")
    with open(template_path, 'r') as f:
        template = json.load(f)
    
    print("📤 Uploading template to Elasticsearch...")
    response = requests.put(
        f"{ES_HOST}/_index_template/platform-events",
        auth=HTTPBasicAuth(ES_USER, ES_PASS),
        headers={"Content-Type": "application/json"},
        json=template
    )
    
    if response.status_code in [200, 201]:
        print("✅ Template uploaded successfully!")
        print(f"   Response: {response.json()}")
        return True
    else:
        print(f"❌ Failed to upload template: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def setup_users():
    """Setup user passwords for Kibana and Logstash"""
    print("\n👤 Setting up user passwords...")
    
    # Set password for built-in kibana_system user
    try:
        response = requests.post(
            f"{ES_HOST}/_security/user/kibana_system/_password",
            auth=HTTPBasicAuth(ES_USER, ES_PASS),
            headers={"Content-Type": "application/json"},
            json={"password": "changeme"}
        )
        
        if response.status_code == 200:
            print(f"✅ Password set for kibana_system")
        else:
            print(f"⚠️  Could not set password for kibana_system: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Error setting password for kibana_system: {e}")
    
    # Create a custom role for logstash with index creation privileges
    try:
        response = requests.post(
            f"{ES_HOST}/_security/role/logstash_writer_role",
            auth=HTTPBasicAuth(ES_USER, ES_PASS),
            headers={"Content-Type": "application/json"},
            json={
                "cluster": ["manage_index_templates", "monitor"],
                "indices": [
                    {
                        "names": ["platform-events-*"],
                        "privileges": ["create_index", "write", "delete", "create", "index", "auto_configure"]
                    }
                ]
            }
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Created custom logstash_writer_role")
        else:
            print(f"⚠️  Could not create role: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"⚠️  Error creating role: {e}")
    
    # Create logstash_internal user with the custom role
    try:
        response = requests.post(
            f"{ES_HOST}/_security/user/logstash_internal",
            auth=HTTPBasicAuth(ES_USER, ES_PASS),
            headers={"Content-Type": "application/json"},
            json={
                "password": "changeme",
                "roles": ["logstash_writer_role"],
                "full_name": "Internal Logstash User"
            }
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Created user logstash_internal with logstash_writer_role")
        else:
            print(f"⚠️  Could not create logstash_internal: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"⚠️  Error creating logstash_internal: {e}")
    
    return True

def create_initial_index():
    """Create initial index with alias"""
    print("\n📊 Creating initial index...")
    
    index_name = "platform-events-2025.11.21"
    response = requests.put(
        f"{ES_HOST}/{index_name}",
        auth=HTTPBasicAuth(ES_USER, ES_PASS),
        headers={"Content-Type": "application/json"},
        json={
            "aliases": {
                "platform-events": {}
            }
        }
    )
    
    if response.status_code in [200, 201]:
        print(f"✅ Index '{index_name}' created with alias 'platform-events'")
        return True
    elif response.status_code == 400 and "resource_already_exists" in response.text:
        print(f"ℹ️  Index already exists")
        return True
    else:
        print(f"❌ Failed to create index: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    print("🔧 Elasticsearch Setup Script")
    print("=" * 50)
    
    if not wait_for_elasticsearch():
        exit(1)
    
    if not setup_users():
        exit(1)
    
    if not upload_template():
        exit(1)
    
    if not create_initial_index():
        exit(1)
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()

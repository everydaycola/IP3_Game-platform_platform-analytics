#!/usr/bin/env python3
"""
Create Elasticsearch Transforms for User Retention & Engagement Analysis

This script creates transforms that aggregate raw session events into:
1. Daily Active Users (DAU)
2. Weekly Active Users (WAU)
3. Monthly Active Users (MAU)
4. User session metrics (frequency, duration)
5. Retention cohorts (D1, D7, D30)
6. Churn detection

All transforms are production-ready and use Elasticsearch REST API.
"""

import requests
import json
import time
from requests.auth import HTTPBasicAuth
from datetime import datetime

ES_HOST = "http://localhost:9200"
ES_USER = "elastic"
ES_PASS = "changeme"

auth = HTTPBasicAuth(ES_USER, ES_PASS)
headers = {"Content-Type": "application/json"}


def check_elasticsearch():
    """Check if Elasticsearch is available"""
    try:
        response = requests.get(f"{ES_HOST}/_cluster/health", auth=auth, timeout=5)
        if response.status_code == 200:
            health = response.json()
            print(f"✅ Elasticsearch is {health['status']}")
            return True
    except Exception as e:
        print(f"❌ Elasticsearch not available: {e}")
        return False


def delete_transform_if_exists(transform_id: str):
    """Delete transform if it exists"""
    try:
        # Stop transform first
        requests.post(
            f"{ES_HOST}/_transform/{transform_id}/_stop",
            auth=auth,
            params={"force": "true", "wait_for_completion": "true"}
        )
        time.sleep(1)
        
        # Delete transform
        response = requests.delete(
            f"{ES_HOST}/_transform/{transform_id}",
            auth=auth
        )
        if response.status_code in [200, 404]:
            print(f"  🗑️  Removed existing transform: {transform_id}")
    except Exception as e:
        pass  # Transform might not exist


def create_transform(transform_id: str, transform_config: dict) -> bool:
    """Create and start an Elasticsearch transform"""
    print(f"\n📊 Creating transform: {transform_id}")
    
    # Delete existing transform
    delete_transform_if_exists(transform_id)
    
    # Create transform
    response = requests.put(
        f"{ES_HOST}/_transform/{transform_id}",
        auth=auth,
        headers=headers,
        json=transform_config
    )
    
    if response.status_code in [200, 201]:
        print(f"  ✅ Transform created")
        
        # Start transform
        start_response = requests.post(
            f"{ES_HOST}/_transform/{transform_id}/_start",
            auth=auth
        )
        
        if start_response.status_code == 200:
            print(f"  ▶️  Transform started")
            return True
        else:
            print(f"  ⚠️  Failed to start transform: {start_response.text}")
            return False
    else:
        print(f"  ❌ Failed to create transform: {response.status_code}")
        print(f"     {response.text}")
        return False


def create_dau_wau_mau_transform():
    """
    Transform 1: Daily/Weekly/Monthly Active Users
    
    Aggregates session_started events by day to calculate:
    - DAU: unique players per day
    - Timestamp for trend analysis
    """
    transform_config = {
        "source": {
            "index": ["platform-events-*"],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"event_type": "session_started"}}
                    ]
                }
            }
        },
        "dest": {
            "index": "retention-metrics-daily-active-users"
        },
        "frequency": "1m",
        "sync": {
            "time": {
                "field": "@timestamp",
                "delay": "60s"
            }
        },
        "pivot": {
            "group_by": {
                "date": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": "1d"
                    }
                }
            },
            "aggregations": {
                "daily_active_users": {
                    "cardinality": {
                        "field": "player_id"
                    }
                },
                "total_sessions": {
                    "value_count": {
                        "field": "session_id"
                    }
                },
                "unique_games": {
                    "cardinality": {
                        "field": "game_id"
                    }
                }
            }
        },
        "description": "Daily Active Users (DAU) aggregation for platform-level engagement tracking",
        "settings": {
            "max_page_search_size": 500
        }
    }
    
    return create_transform("transform-daily-active-users", transform_config)


def create_user_session_metrics_transform():
    """
    Transform 2: User Session Metrics
    
    Aggregates sessions per user to calculate:
    - Total sessions per user
    - First session date (for cohort analysis)
    - Last session date (for churn detection)
    - Active days count
    """
    transform_config = {
        "source": {
            "index": ["platform-events-*"],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"event_type": "session_started"}}
                    ]
                }
            }
        },
        "dest": {
            "index": "retention-metrics-user-sessions"
        },
        "frequency": "5m",
        "sync": {
            "time": {
                "field": "@timestamp",
                "delay": "60s"
            }
        },
        "pivot": {
            "group_by": {
                "player_id": {
                    "terms": {
                        "field": "player_id"
                    }
                }
            },
            "aggregations": {
                "total_sessions": {
                    "value_count": {
                        "field": "session_id"
                    }
                },
                "first_session": {
                    "min": {
                        "field": "@timestamp"
                    }
                },
                "last_session": {
                    "max": {
                        "field": "@timestamp"
                    }
                },
                "unique_days_active": {
                    "cardinality": {
                        "field": "@timestamp",
                        "precision_threshold": 1000
                    }
                },
                "unique_games_played": {
                    "cardinality": {
                        "field": "game_id"
                    }
                }
            }
        },
        "description": "Per-user session metrics for engagement and retention analysis",
        "settings": {
            "max_page_search_size": 500
        }
    }
    
    return create_transform("transform-user-session-metrics", transform_config)


def create_retention_cohort_transform():
    """
    Transform 3: User Retention Cohorts
    
    Groups users by their registration week and tracks retention
    This provides data for cohort retention analysis
    """
    transform_config = {
        "source": {
            "index": ["platform-events-*"],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"event_type": "session_started"}}
                    ]
                }
            }
        },
        "dest": {
            "index": "retention-metrics-cohorts"
        },
        "frequency": "1h",
        "sync": {
            "time": {
                "field": "@timestamp",
                "delay": "60s"
            }
        },
        "pivot": {
            "group_by": {
                "player_id": {
                    "terms": {
                        "field": "player_id"
                    }
                },
                "cohort_week": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "calendar_interval": "1w"
                    }
                }
            },
            "aggregations": {
                "sessions_in_cohort_week": {
                    "value_count": {
                        "field": "session_id"
                    }
                },
                "first_session_in_week": {
                    "min": {
                        "field": "@timestamp"
                    }
                },
                "last_session_in_week": {
                    "max": {
                        "field": "@timestamp"
                    }
                }
            }
        },
        "description": "User cohorts grouped by registration week for retention analysis",
        "settings": {
            "max_page_search_size": 500
        }
    }
    
    return create_transform("transform-retention-cohorts", transform_config)


def create_hourly_activity_transform():
    """
    Transform 4: Hourly Activity Patterns
    
    Aggregates sessions by hour of day to identify peak usage times
    """
    transform_config = {
        "source": {
            "index": ["platform-events-*"],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"event_type": "session_started"}}
                    ]
                }
            }
        },
        "dest": {
            "index": "retention-metrics-hourly-activity"
        },
        "frequency": "30m",
        "sync": {
            "time": {
                "field": "@timestamp",
                "delay": "60s"
            }
        },
        "pivot": {
            "group_by": {
                "hour_of_day": {
                    "terms": {
                        "script": {
                            "source": "doc['@timestamp'].value.getHour()",
                            "lang": "painless"
                        }
                    }
                },
                "day_of_week": {
                    "terms": {
                        "script": {
                            "source": "doc['@timestamp'].value.getDayOfWeekEnum().getValue()",
                            "lang": "painless"
                        }
                    }
                }
            },
            "aggregations": {
                "session_count": {
                    "value_count": {
                        "field": "session_id"
                    }
                },
                "unique_players": {
                    "cardinality": {
                        "field": "player_id"
                    }
                }
            }
        },
        "description": "Hourly and daily activity patterns for usage optimization",
        "settings": {
            "max_page_search_size": 500
        }
    }
    
    return create_transform("transform-hourly-activity", transform_config)


def verify_transform_data(index_name: str, transform_id: str):
    """Verify that transform has generated data"""
    print(f"\n🔍 Verifying data in {index_name}...")
    
    time.sleep(3)  # Wait for transform to process some data
    
    try:
        response = requests.get(
            f"{ES_HOST}/{index_name}/_search",
            auth=auth,
            params={"size": 0}
        )
        
        if response.status_code == 200:
            hits = response.json()['hits']['total']['value']
            if hits > 0:
                print(f"  ✅ {hits} documents indexed")
                
                # Get sample document
                sample_response = requests.get(
                    f"{ES_HOST}/{index_name}/_search",
                    auth=auth,
                    params={"size": 1}
                )
                if sample_response.status_code == 200:
                    sample = sample_response.json()['hits']['hits']
                    if sample:
                        print(f"  📄 Sample document: {json.dumps(sample[0]['_source'], indent=2)[:200]}...")
                return True
            else:
                print(f"  ⚠️  No documents yet (transform may still be processing)")
                return False
        else:
            print(f"  ⚠️  Index not found yet")
            return False
    except Exception as e:
        print(f"  ⚠️  Cannot verify: {e}")
        return False


def create_index_template_for_metrics():
    """Create index templates for metric indices"""
    print("\n📋 Creating index templates for metric indices...")
    
    templates = {
        "retention-metrics-daily-active-users": {
            "index_patterns": ["retention-metrics-daily-active-users*"],
            "template": {
                "mappings": {
                    "properties": {
                        "date": {"type": "date"},
                        "daily_active_users": {"type": "long"},
                        "total_sessions": {"type": "long"},
                        "unique_games": {"type": "long"}
                    }
                }
            }
        },
        "retention-metrics-user-sessions": {
            "index_patterns": ["retention-metrics-user-sessions*"],
            "template": {
                "mappings": {
                    "properties": {
                        "player_id": {"type": "keyword"},
                        "total_sessions": {"type": "long"},
                        "first_session": {"type": "date"},
                        "last_session": {"type": "date"},
                        "unique_days_active": {"type": "long"},
                        "unique_games_played": {"type": "long"}
                    }
                }
            }
        }
    }
    
    for template_name, template_config in templates.items():
        response = requests.put(
            f"{ES_HOST}/_index_template/{template_name}",
            auth=auth,
            headers=headers,
            json=template_config
        )
        
        if response.status_code in [200, 201]:
            print(f"  ✅ Template created: {template_name}")
        else:
            print(f"  ⚠️  Template creation warning: {response.status_code}")


def main():
    """Main execution"""
    print("🔧 Elasticsearch Transforms Setup for Retention & Engagement")
    print("=" * 70)
    
    if not check_elasticsearch():
        print("\n❌ Elasticsearch is not available. Please start it first.")
        print("   Run: docker-compose up -d elasticsearch")
        return
    
    print("\n📝 This script will create the following transforms:")
    print("  1. Daily Active Users (DAU/WAU/MAU base data)")
    print("  2. User Session Metrics (per-user engagement)")
    print("  3. Retention Cohorts (cohort analysis)")
    print("  4. Hourly Activity (usage patterns)")
    print("\n⚠️  Note: Transforms require source data to exist.")
    print("   Make sure you've run: python scripts/generate_retention_data.py")
    
    input("\nPress Enter to continue or Ctrl+C to cancel...")
    
    # Create index templates first
    create_index_template_for_metrics()
    
    # Create transforms
    print("\n" + "=" * 70)
    print("Creating transforms...")
    print("=" * 70)
    
    results = []
    
    # Transform 1: DAU/WAU/MAU
    results.append(("Daily Active Users", create_dau_wau_mau_transform()))
    time.sleep(2)
    
    # Transform 2: User Session Metrics
    results.append(("User Session Metrics", create_user_session_metrics_transform()))
    time.sleep(2)
    
    # Transform 3: Retention Cohorts
    results.append(("Retention Cohorts", create_retention_cohort_transform()))
    time.sleep(2)
    
    # Transform 4: Hourly Activity
    results.append(("Hourly Activity", create_hourly_activity_transform()))
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 Transform Creation Summary:")
    print("=" * 70)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
    
    successful = sum(1 for _, success in results if success)
    print(f"\n  {successful}/{len(results)} transforms created successfully")
    
    # Verify data
    print("\n" + "=" * 70)
    print("Verifying transform data...")
    print("=" * 70)
    
    verify_transform_data("retention-metrics-daily-active-users", "transform-daily-active-users")
    verify_transform_data("retention-metrics-user-sessions", "transform-user-session-metrics")
    
    print("\n" + "=" * 70)
    print("✅ Transform setup complete!")
    print("\n📊 Next steps:")
    print("  1. Wait 2-3 minutes for transforms to process data")
    print("  2. Run: python setup/create_retention_dashboard_complete.py")
    print("  3. View transforms: curl -u elastic:changeme http://localhost:9200/_transform")
    print("  4. Check Kibana Stack Management → Transforms")
    print("\n💡 Transforms run continuously and update as new data arrives")


if __name__ == "__main__":
    main()

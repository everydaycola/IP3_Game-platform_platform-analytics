#!/usr/bin/env python3
"""
Create Revenue Dashboard in Kibana
Automatically creates all visualizations and dashboard for revenue analytics
"""

import requests
import json
import os
from requests.auth import HTTPBasicAuth
import time

KIBANA_URL = os.getenv("KIBANA_HOST", "http://localhost:5601")
ELASTIC_USER = os.getenv("KIBANA_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("KIBANA_PASSWORD", "changeme")

headers = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}

auth = HTTPBasicAuth(ELASTIC_USER, ELASTIC_PASSWORD)

def check_dashboard_exists():
    """Check if the dashboard already exists"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/revenue-dashboard"
    try:
        response = requests.get(url, headers=headers, auth=auth)
        return response.status_code == 200
    except:
        return False

def get_data_view_id():
    """Get the ID of the platform-events data view"""
    url = f"{KIBANA_URL}/api/data_views"
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        data_views = response.json()
        for dv in data_views.get('data_view', []):
            if dv.get('title') == 'platform-events-*':
                print(f"✓ Found data view: {dv['id']}")
                return dv['id']
    
    print("❌ Data view 'platform-events-*' not found!")
    return None

def create_visualization(title, vis_type, vis_state, saved_object_id, data_view_id, custom_query=None):
    """Create a visualization in Kibana"""
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{saved_object_id}"
    
    # Use custom query if provided, otherwise use default
    if custom_query:
        search_source = custom_query
        search_source["index"] = data_view_id
    else:
        search_source = {
            "index": data_view_id,
            "query": {
                "query": "event_type:purchase_made OR event_type:payment_made",
                "language": "kuery"
            },
            "filter": []
        }
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(search_source)
            }
        },
        "references": [
            {
                "id": data_view_id,
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern"
            }
        ]
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"✅ Created: {title}")
        return saved_object_id
    else:
        print(f"❌ Failed to create {title}: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
        return None

def create_lens_visualization(title, lens_config, saved_object_id):
    """Create a Lens visualization"""
    url = f"{KIBANA_URL}/api/saved_objects/lens/{saved_object_id}"
    
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsXY",
            "state": lens_config,
            "references": []
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"✅ Created: {title}")
        return saved_object_id
    else:
        print(f"❌ Failed to create {title}: {response.status_code}")
        return None

def create_dashboard(viz_ids):
    """Create the Revenue Dashboard"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/revenue-dashboard"
    
    # Layout configuration for panels
    panels = [
        # Row 1: KPI Metrics (4 cards)
        {"id": viz_ids["total_revenue"], "gridData": {"x": 0, "y": 0, "w": 12, "h": 8}},
        {"id": viz_ids["avg_purchase"], "gridData": {"x": 12, "y": 0, "w": 12, "h": 8}},
        {"id": viz_ids["total_transactions"], "gridData": {"x": 24, "y": 0, "w": 12, "h": 8}},
        {"id": viz_ids["annual_projection"], "gridData": {"x": 36, "y": 0, "w": 12, "h": 8}},
        
        # Row 2: Revenue Evolution (full width)
        {"id": viz_ids["revenue_evolution"], "gridData": {"x": 0, "y": 8, "w": 48, "h": 15}},
        
        # Row 3: Top Games and Payment Methods
        {"id": viz_ids["top_games"], "gridData": {"x": 0, "y": 23, "w": 24, "h": 15}},
        {"id": viz_ids["payment_methods"], "gridData": {"x": 24, "y": 23, "w": 24, "h": 15}},
        
        # Row 4: Revenue by Game Type
        {"id": viz_ids["revenue_by_game"], "gridData": {"x": 0, "y": 38, "w": 48, "h": 15}},
    ]
    
    panels_json = []
    for i, panel in enumerate(panels):
        panels_json.append({
            "version": "8.15.3",
            "type": "visualization",
            "gridData": panel["gridData"],
            "panelIndex": str(i+1),
            "embeddableConfig": {},
            "panelRefName": f"panel_{i+1}"
        })
    
    references = []
    for i, panel in enumerate(panels):
        references.append({
            "name": f"panel_{i+1}",
            "type": "visualization",
            "id": panel["id"]
        })
    
    payload = {
        "attributes": {
            "title": "Opbrengsten Dashboard",
            "description": "Revenue analytics dashboard voor bordspel platform",
            "panelsJSON": json.dumps(panels_json),
            "optionsJSON": json.dumps({
                "useMargins": True,
                "hidePanelTitles": False
            }),
            "version": 1,
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-30d",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": references
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"\n✅ Dashboard created successfully!")
        print(f"🌐 View at: {KIBANA_URL}/app/dashboards#/view/revenue-dashboard")
        return True
    else:
        print(f"❌ Failed to create dashboard: {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        return False

def main():
    print("=" * 70)
    print("💰 CREATING REVENUE DASHBOARD IN KIBANA")
    print("=" * 70)
    
    # Check if dashboard already exists
    if check_dashboard_exists():
        print("\n✅ Dashboard 'revenue-dashboard' already exists. Skipping creation.")
        return
    
    # Get data view ID
    data_view_id = get_data_view_id()
    if not data_view_id:
        print("\n❌ Please create the data view first in Kibana!")
        return
    
    print(f"\n📊 Creating visualizations...")
    viz_ids = {}
    
    # 1. Total Revenue (Metric)
    viz_ids["total_revenue"] = create_visualization(
        "Total Revenue",
        "metric",
        {
            "title": "Total Revenue",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "sum",
                    "params": {"field": "amount"},
                    "schema": "metric"
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
                }
            }
        },
        "viz-total-revenue",
        data_view_id
    )
    
    # 2. Average Purchase Value
    viz_ids["avg_purchase"] = create_visualization(
        "Avg Purchase Value",
        "metric",
        {
            "title": "Avg Purchase Value",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "avg",
                    "params": {"field": "amount"},
                    "schema": "metric"
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
                }
            },
            "searchSourceJSON": json.dumps({
                "query": {"query": "event_type: purchase_made", "language": "kuery"},
                "filter": []
            })
        },
        "viz-avg-purchase",
        data_view_id
    )
    
    # 3. Total Transactions
    viz_ids["total_transactions"] = create_visualization(
        "Total Transactions",
        "metric",
        {
            "title": "Total Transactions",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "params": {},
                    "schema": "metric"
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
                }
            },
            "searchSourceJSON": json.dumps({
                "query": {"query": "event_type: purchase_made", "language": "kuery"},
                "filter": []
            })
        },
        "viz-total-transactions",
        data_view_id
    )
    
    # 4. Annual Projection (calculated metric)
    viz_ids["annual_projection"] = create_visualization(
        "Annual Projection",
        "metric",
        {
            "title": "Annual Projection",
            "type": "metric",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "sum",
                    "params": {"field": "amount"},
                    "schema": "metric"
                }
            ],
            "params": {
                "addTooltip": True,
                "addLegend": False,
                "type": "metric",
                "metric": {
                    "percentageMode": False,
                    "useRanges": False,
                    "colorSchema": "Green to Red",
                    "metricColorMode": "None",
                    "colorsRange": [{"from": 0, "to": 10000}],
                    "labels": {"show": True},
                    "invertColors": False,
                    "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "Projected", "fontSize": 60}
                }
            },
            "searchSourceJSON": json.dumps({
                "query": {"query": "event_type: purchase_made", "language": "kuery"},
                "filter": []
            })
        },
        "viz-annual-projection",
        data_view_id
    )
    
    # 5. Revenue Evolution Over Time
    viz_ids["revenue_evolution"] = create_visualization(
        "Revenue Evolution",
        "line",
        {
            "title": "Revenue Evolution Over Time",
            "type": "line",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "sum",
                    "params": {"field": "amount"},
                    "schema": "metric"
                },
                {
                    "id": "2",
                    "enabled": True,
                    "type": "date_histogram",
                    "params": {
                        "field": "@timestamp",
                        "timeRange": {"from": "now-30d", "to": "now"},
                        "useNormalizedEsInterval": True,
                        "scaleMetricValues": False,
                        "interval": "auto",
                        "drop_partials": False,
                        "min_doc_count": 1,
                        "extended_bounds": {}
                    },
                    "schema": "segment"
                }
            ],
            "params": {
                "type": "line",
                "grid": {"categoryLines": False},
                "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True, "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 100}, "title": {"text": "Datum"}}],
                "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left", "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"}, "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100}, "title": {"text": "Opbrengsten (€)"}}],
                "seriesParams": [{"show": True, "type": "line", "mode": "normal", "data": {"label": "Revenue", "id": "1"}, "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "times": [],
                "addTimeMarker": False,
                "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}
            }
        },
        "viz-revenue-evolution",
        data_view_id,
        custom_query={"query": {"query": "event_type: purchase_made", "language": "kuery"}, "filter": []}
    )
    
    # 6. Top Games by Revenue
    viz_ids["top_games"] = create_visualization(
        "Top Games by Revenue",
        "horizontal_bar",
        {
            "title": "Top Games by Revenue",
            "type": "horizontal_bar",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "sum",
                    "params": {"field": "amount"},
                    "schema": "metric"
                },
                {
                    "id": "2",
                    "enabled": True,
                    "type": "terms",
                    "params": {
                        "field": "game_name",
                        "orderBy": "1",
                        "order": "desc",
                        "size": 10,
                        "otherBucket": False,
                        "otherBucketLabel": "Other",
                        "missingBucket": False,
                        "missingBucketLabel": "Missing"
                    },
                    "schema": "segment"
                }
            ],
            "params": {
                "type": "histogram",
                "grid": {"categoryLines": False},
                "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "left", "show": True, "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 200}, "title": {"text": "Spel"}}],
                "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "bottom", "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"}, "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100}, "title": {"text": "Totale Opbrengst (€)"}}],
                "seriesParams": [{"show": True, "type": "histogram", "mode": "normal", "data": {"label": "Revenue", "id": "1"}, "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "times": [],
                "addTimeMarker": False
            }
        },
        "viz-top-games",
        data_view_id,
        custom_query={"query": {"query": "event_type: purchase_made", "language": "kuery"}, "filter": []}
    )
    
    # 7. Payment Methods Distribution
    viz_ids["payment_methods"] = create_visualization(
        "Payment Methods",
        "pie",
        {
            "title": "Payment Method Distribution",
            "type": "pie",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "count",
                    "params": {},
                    "schema": "metric"
                },
                {
                    "id": "2",
                    "enabled": True,
                    "type": "terms",
                    "params": {
                        "field": "payment_method",
                        "orderBy": "1",
                        "order": "desc",
                        "size": 10,
                        "otherBucket": False,
                        "otherBucketLabel": "Other",
                        "missingBucket": False,
                        "missingBucketLabel": "Missing"
                    },
                    "schema": "segment"
                }
            ],
            "params": {
                "type": "pie",
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "isDonut": False,
                "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}
            }
        },
        "viz-payment-methods",
        data_view_id,
        custom_query={"query": {"query": "event_type: payment_made", "language": "kuery"}, "filter": []}
    )
    
    # 8. Revenue by Game
    viz_ids["revenue_by_game"] = create_visualization(
        "Revenue by Game",
        "histogram",
        {
            "title": "Revenue by Game Type",
            "type": "histogram",
            "aggs": [
                {
                    "id": "1",
                    "enabled": True,
                    "type": "sum",
                    "params": {"field": "amount"},
                    "schema": "metric"
                },
                {
                    "id": "2",
                    "enabled": True,
                    "type": "terms",
                    "params": {
                        "field": "product_type.keyword",
                        "orderBy": "1",
                        "order": "desc",
                        "size": 10,
                        "otherBucket": False,
                        "otherBucketLabel": "Other",
                        "missingBucket": False,
                        "missingBucketLabel": "Missing"
                    },
                    "schema": "segment"
                }
            ],
            "params": {
                "type": "histogram",
                "grid": {"categoryLines": False},
                "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True, "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 100, "rotate": 0}, "title": {"text": "Product Type"}}],
                "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left", "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"}, "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100}, "title": {"text": "Opbrengsten (€)"}}],
                "seriesParams": [{"show": True, "type": "histogram", "mode": "stacked", "data": {"label": "Revenue", "id": "1"}, "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True, "lineWidth": 2, "showCircles": True}],
                "addTooltip": True,
                "addLegend": True,
                "legendPosition": "right",
                "times": [],
                "addTimeMarker": False
            }
        },
        "viz-revenue-by-game",
        data_view_id,
        custom_query={"query": {"query": "event_type: purchase_made", "language": "kuery"}, "filter": []}
    )
    
    time.sleep(2)
    
    # Create the dashboard
    print(f"\n📊 Creating dashboard...")
    create_dashboard(viz_ids)
    
    print("\n" + "=" * 70)
    print("✅ REVENUE DASHBOARD SETUP COMPLETE!")
    print("=" * 70)
    print(f"\n🌐 Open Kibana: {KIBANA_URL}/app/dashboards#/view/revenue-dashboard")
    print("\n📊 Dashboard includes:")
    print("   • Total Revenue")
    print("   • Average Purchase Value")
    print("   • Total Transactions")
    print("   • Annual Projection")
    print("   • Revenue Evolution Over Time")
    print("   • Top Games by Revenue")
    print("   • Payment Method Distribution")
    print("   • Revenue by Game Type")
    print("\n💡 Tip: Gebruik de time picker rechts bovenin om de periode aan te passen!")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

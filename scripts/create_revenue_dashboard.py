#!/usr/bin/env python3
"""
Create Revenue Dashboard in Kibana using ALL Lens visualizations
Uses panel-level time range overrides for Weekly/Monthly/Yearly KPIs
"""

import requests
import json
import os
import uuid
from requests.auth import HTTPBasicAuth

KIBANA_URL = os.getenv("KIBANA_HOST", "http://localhost:5601")
ELASTIC_USER = os.getenv("KIBANA_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("KIBANA_PASSWORD", "changeme")

headers = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}

auth = HTTPBasicAuth(ELASTIC_USER, ELASTIC_PASSWORD)


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


def create_lens_metric(title, data_view_id, field, operation_type="sum", kql_query=""):
    """Create a Lens metric visualization"""
    lens_id = f"lens-revenue-{title.lower().replace(' ', '-').replace('(', '').replace(')', '')}"
    layer_id = str(uuid.uuid4())
    col_id = str(uuid.uuid4())
    
    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"
    
    if operation_type == "count":
        metric_column = {
            "label": title,
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio"
        }
    else:
        metric_column = {
            "label": title,
            "dataType": "number",
            "operationType": operation_type,
            "sourceField": field,
            "isBucketed": False,
            "scale": "ratio",
            "params": {}
        }
    
    layer_state = {
        "indexPatternId": data_view_id,
        "columns": {
            col_id: metric_column
        },
        "columnOrder": [col_id]
    }
    
    state = {
        "query": {"language": "kuery", "query": kql_query},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer_id: layer_state
                }
            }
        },
        "visualization": {
            "layerId": layer_id,
            "metricAccessor": col_id,
            "layerType": "data"
        }
    }
    
    references = [
        {
            "type": "index-pattern",
            "id": data_view_id,
            "name": f"indexpattern-datasource-layer-{layer_id}"
        }
    ]
    
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsMetric",
            "state": state
        },
        "references": references
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens Metric) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens Metric) {title}: {response.text[:200]}")
        return None


def create_lens_xy(title, data_view_id, x_field, y_field, agg_type="sum", series_type="line", kql_query="", x_interval="auto", x_label=None, y_label=None):
    """Create a Lens XY visualization (line/bar)"""
    lens_id = f"lens-revenue-{title.lower().replace(' ', '-').replace('(', '').replace(')', '')}"
    layer_id = str(uuid.uuid4())
    x_col_id = str(uuid.uuid4())
    y_col_id = str(uuid.uuid4())
    
    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"
    
    # X-axis column (date histogram)
    x_column = {
        "label": x_label or "Date",
        "dataType": "date",
        "operationType": "date_histogram",
        "sourceField": x_field,
        "isBucketed": True,
        "scale": "interval",
        "params": {"interval": x_interval},
        "customLabel": True
    }
    
    # Y-axis column
    if agg_type == "count":
        y_column = {
            "label": y_label or "Count",
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio",
            "customLabel": True
        }
    else:
        y_column = {
            "label": y_label or f"Sum of {y_field}",
            "dataType": "number",
            "operationType": agg_type,
            "sourceField": y_field,
            "isBucketed": False,
            "scale": "ratio",
            "customLabel": True
        }
    
    state = {
        "query": {"language": "kuery", "query": kql_query},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer_id: {
                        "indexPatternId": data_view_id,
                        "columns": {
                            x_col_id: x_column,
                            y_col_id: y_column
                        },
                        "columnOrder": [x_col_id, y_col_id]
                    }
                }
            }
        },
        "visualization": {
            "title": title,
            "legend": {"isVisible": True, "position": "right"},
            "preferredSeriesType": series_type,
            "layers": [
                {
                    "layerId": layer_id,
                    "accessors": [y_col_id],
                    "position": "top",
                    "seriesType": series_type,
                    "showLines": series_type != "bar",
                    "xAccessor": x_col_id,
                    "layerType": "data"
                }
            ]
        }
    }
    
    references = [
        {
            "type": "index-pattern",
            "id": data_view_id,
            "name": f"indexpattern-datasource-layer-{layer_id}"
        }
    ]
    
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsXY",
            "state": state
        },
        "references": references
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens XY) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens XY) {title}: {response.text[:200]}")
        return None


def create_lens_bar_terms(title, data_view_id, terms_field, metric_field, agg_type="sum", kql_query="", horizontal=False, x_label=None, y_label=None):
    """Create a Lens bar chart with terms aggregation"""
    lens_id = f"lens-revenue-{title.lower().replace(' ', '-').replace('(', '').replace(')', '')}"
    layer_id = str(uuid.uuid4())
    x_col_id = str(uuid.uuid4())
    y_col_id = str(uuid.uuid4())
    
    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"
    
    # X-axis column (terms)
    x_column = {
        "label": x_label or terms_field,
        "dataType": "string",
        "operationType": "terms",
        "sourceField": terms_field,
        "isBucketed": True,
        "scale": "ordinal",
        "params": {
            "size": 10,
            "orderBy": {"type": "column", "columnId": y_col_id},
            "orderDirection": "desc"
        },
        "customLabel": True
    }
    
    # Y-axis column
    if agg_type == "count":
        y_column = {
            "label": y_label or "Count",
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio",
            "customLabel": True
        }
    else:
        y_column = {
            "label": y_label or f"Revenue (€)",
            "dataType": "number",
            "operationType": agg_type,
            "sourceField": metric_field,
            "isBucketed": False,
            "scale": "ratio",
            "customLabel": True
        }
    
    series_type = "bar_horizontal" if horizontal else "bar"
    
    state = {
        "query": {"language": "kuery", "query": kql_query},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer_id: {
                        "indexPatternId": data_view_id,
                        "columns": {
                            x_col_id: x_column,
                            y_col_id: y_column
                        },
                        "columnOrder": [x_col_id, y_col_id]
                    }
                }
            }
        },
        "visualization": {
            "title": title,
            "legend": {"isVisible": True, "position": "right"},
            "preferredSeriesType": series_type,
            "layers": [
                {
                    "layerId": layer_id,
                    "accessors": [y_col_id],
                    "position": "top",
                    "seriesType": series_type,
                    "xAccessor": x_col_id,
                    "layerType": "data"
                }
            ]
        }
    }
    
    references = [
        {
            "type": "index-pattern",
            "id": data_view_id,
            "name": f"indexpattern-datasource-layer-{layer_id}"
        }
    ]
    
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsXY",
            "state": state
        },
        "references": references
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens Bar) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens Bar) {title}: {response.text[:200]}")
        return None


def create_lens_pie(title, data_view_id, terms_field, kql_query="", slice_label=None):
    """Create a Lens pie chart"""
    lens_id = f"lens-revenue-{title.lower().replace(' ', '-').replace('(', '').replace(')', '')}"
    layer_id = str(uuid.uuid4())
    slice_col_id = str(uuid.uuid4())
    metric_col_id = str(uuid.uuid4())
    
    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"
    
    state = {
        "query": {"language": "kuery", "query": kql_query},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer_id: {
                        "indexPatternId": data_view_id,
                        "columns": {
                            slice_col_id: {
                                "label": slice_label or "Category",
                                "dataType": "string",
                                "operationType": "terms",
                                "sourceField": terms_field,
                                "isBucketed": True,
                                "scale": "ordinal",
                                "params": {
                                    "size": 10,
                                    "orderBy": {"type": "column", "columnId": metric_col_id},
                                    "orderDirection": "desc"
                                },
                                "customLabel": True
                            },
                            metric_col_id: {
                                "label": "Number of Transactions",
                                "dataType": "number",
                                "operationType": "count",
                                "sourceField": "___records___",
                                "isBucketed": False,
                                "scale": "ratio",
                                "customLabel": True
                            }
                        },
                        "columnOrder": [slice_col_id, metric_col_id]
                    }
                }
            }
        },
        "visualization": {
            "shape": "pie",
            "layers": [
                {
                    "layerId": layer_id,
                    "primaryGroups": [slice_col_id],
                    "metrics": [metric_col_id],
                    "numberDisplay": "percent",
                    "categoryDisplay": "default",
                    "legendDisplay": "default",
                    "nestedLegend": False,
                    "layerType": "data"
                }
            ]
        }
    }
    
    references = [
        {
            "type": "index-pattern",
            "id": data_view_id,
            "name": f"indexpattern-datasource-layer-{layer_id}"
        }
    ]
    
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "visualizationType": "lnsPie",
            "state": state
        },
        "references": references
    }
    
    response = requests.post(url, headers=headers, json=payload, auth=auth, params={"overwrite": "true"})
    
    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens Pie) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens Pie) {title}: {response.text[:200]}")
        return None


def create_dashboard(viz_ids):
    """Create the Revenue Dashboard with panel-level time overrides"""
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/revenue-dashboard"
    
    # Layout with time range overrides for revenue KPIs
    layout = [
        # Row 1: Revenue KPIs with fixed time ranges
        {"id": viz_ids["weekly_revenue"], "type": "lens", "gridData": {"x": 0, "y": 0, "w": 16, "h": 10, "i": "1"}, 
         "timeRange": {"from": "now-7d", "to": "now"}},
        {"id": viz_ids["monthly_revenue"], "type": "lens", "gridData": {"x": 16, "y": 0, "w": 16, "h": 10, "i": "2"}, 
         "timeRange": {"from": "now-30d", "to": "now"}},
        {"id": viz_ids["yearly_revenue"], "type": "lens", "gridData": {"x": 32, "y": 0, "w": 16, "h": 10, "i": "3"}, 
         "timeRange": {"from": "now-1y", "to": "now"}},
        
        # Row 2: Other KPIs (follow dashboard time)
        {"id": viz_ids["avg_purchase"], "type": "lens", "gridData": {"x": 0, "y": 10, "w": 24, "h": 10, "i": "4"}},
        {"id": viz_ids["total_transactions"], "type": "lens", "gridData": {"x": 24, "y": 10, "w": 24, "h": 10, "i": "5"}},
        
        # Row 3: Revenue Evolution (Lens line)
        {"id": viz_ids["revenue_evolution"], "type": "lens", "gridData": {"x": 0, "y": 20, "w": 48, "h": 15, "i": "6"}},
        
        # Row 4: Top Games and Payment Methods (Lens)
        {"id": viz_ids["top_games"], "type": "lens", "gridData": {"x": 0, "y": 35, "w": 24, "h": 15, "i": "7"}},
        {"id": viz_ids["payment_methods"], "type": "lens", "gridData": {"x": 24, "y": 35, "w": 24, "h": 15, "i": "8"}},
        
        # Row 5: Revenue by Product Type (Lens bar)
        {"id": viz_ids["revenue_by_product"], "type": "lens", "gridData": {"x": 0, "y": 50, "w": 48, "h": 15, "i": "9"}},
    ]
    
    panels_json = []
    references = []
    
    for idx, item in enumerate(layout):
        if not item["id"]:
            continue
            
        panel_index = str(idx + 1)
        
        # Build embeddableConfig with timeRange if specified
        embeddable_config = {}
        if item.get("timeRange"):
            embeddable_config["timeRange"] = item["timeRange"]
        
        panels_json.append({
            "version": "8.15.3",
            "type": item["type"],
            "gridData": item["gridData"],
            "panelIndex": panel_index,
            "embeddableConfig": embeddable_config,
            "panelRefName": f"panel_{panel_index}"
        })
        
        references.append({
            "name": f"panel_{panel_index}",
            "type": item["type"],
            "id": item["id"]
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
    print("💰 CREATING REVENUE DASHBOARD IN KIBANA (ALL LENS)")
    print("=" * 70)
    
    # Get data view ID
    data_view_id = get_data_view_id()
    if not data_view_id:
        print("\n❌ Please create the data view first in Kibana!")
        return
    
    print(f"\n📊 Creating Lens visualizations...")
    viz_ids = {}
    
    # 1. Weekly Revenue (Lens metric - time range set at panel level)
    viz_ids["weekly_revenue"] = create_lens_metric(
        "Weekly Revenue",
        data_view_id,
        "amount",
        "sum",
        "event_type:purchase_made"
    )
    
    # 2. Monthly Revenue (Lens metric - time range set at panel level)
    viz_ids["monthly_revenue"] = create_lens_metric(
        "Monthly Revenue",
        data_view_id,
        "amount",
        "sum",
        "event_type:purchase_made"
    )
    
    # 3. Yearly Revenue (Lens metric - time range set at panel level)
    viz_ids["yearly_revenue"] = create_lens_metric(
        "Yearly Revenue",
        data_view_id,
        "amount",
        "sum",
        "event_type:purchase_made"
    )
    
    # 4. Average Purchase Value (Lens metric)
    viz_ids["avg_purchase"] = create_lens_metric(
        "Avg Purchase Value",
        data_view_id,
        "amount",
        "average",
        "event_type:purchase_made"
    )
    
    # 5. Total Transactions (Lens metric with count)
    viz_ids["total_transactions"] = create_lens_metric(
        "Total Transactions",
        data_view_id,
        None,
        "count",
        "event_type:purchase_made"
    )
    
    # 6. Revenue Evolution (Lens line chart)
    viz_ids["revenue_evolution"] = create_lens_xy(
        "Revenue Evolution",
        data_view_id,
        "@timestamp",
        "amount",
        "sum",
        "line",
        "event_type:purchase_made",
        "1d",
        x_label="Date",
        y_label="Revenue (€)"
    )
    
    # 7. Top Games by Revenue (Lens horizontal bar)
    viz_ids["top_games"] = create_lens_bar_terms(
        "Top Games by Revenue",
        data_view_id,
        "game_name",
        "amount",
        "sum",
        "event_type:purchase_made",
        horizontal=True,
        x_label="Game",
        y_label="Revenue (€)"
    )
    
    # 8. Payment Methods Distribution (Lens pie)
    viz_ids["payment_methods"] = create_lens_pie(
        "Payment Methods",
        data_view_id,
        "payment_method",
        "event_type:payment_made",
        slice_label="Payment Method"
    )
    
    # 9. Revenue by Product Type (Lens bar)
    viz_ids["revenue_by_product"] = create_lens_bar_terms(
        "Revenue by Product Type",
        data_view_id,
        "product_type.keyword",
        "amount",
        "sum",
        "event_type:purchase_made",
        horizontal=False,
        x_label="Product Type",
        y_label="Revenue (€)"
    )
    
    # Create dashboard
    print("\n📊 Creating dashboard with panel-level time ranges...")
    create_dashboard(viz_ids)
    
    print("\n" + "=" * 70)
    print("✅ REVENUE DASHBOARD SETUP COMPLETE!")
    print("=" * 70)
    print(f"\n🌐 Open Kibana: {KIBANA_URL}/app/dashboards#/view/revenue-dashboard")
    print("\n📊 KPI Time Ranges:")
    print("   • Weekly Revenue: Last 7 days")
    print("   • Monthly Revenue: Last 30 days")
    print("   • Yearly Revenue: Last 1 year")
    print("\n💡 These KPIs have fixed time ranges independent of the dashboard time picker!")
    print("=" * 70)


if __name__ == "__main__":
    main()

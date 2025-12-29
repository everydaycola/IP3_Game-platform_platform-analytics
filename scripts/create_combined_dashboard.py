#!/usr/bin/env python3
"""
ISM User Engagement & Retention Dashboard Creator
Creates ONE combined dashboard with proper visualization references

IMPORTANT: Metrics Implementation following Industry Standards
=================================================================

DEFINITIONS (Source: https://mixpanel.com/blog/mau/):
- DAU (Daily Active Users): Number of UNIQUE users who performed a meaningful action in a given DAY
- WAU (Weekly Active Users): Number of UNIQUE users who performed a meaningful action in a given WEEK  
- MAU (Monthly Active Users): Number of UNIQUE users who performed a meaningful action in a given MONTH

KEY POINT: These are UNIQUE USER COUNTS, not cumulative sums!

CORRECT ELASTICSEARCH AGGREGATION (Source: https://www.elastic.co/guide/en/elasticsearch/reference/current/):
- For UNIQUE user counts: Use CARDINALITY aggregation (counts distinct values)
- NEVER use SUM (adds up values - wrong for user counts)
- NEVER use AVG on already-aggregated data (mathematically incorrect)

CURRENT IMPLEMENTATION:
Our data pipeline (Elasticsearch Transforms) already pre-calculates:
- daily_active_users field = unique user count per day (already a cardinality result)
- weekly_active_users field = unique user count per week (already a cardinality result)
- monthly_active_users field = unique user count per month (already a cardinality result)

DASHBOARD AGGREGATION CHOICE (Per Analytics Standard - Elastic/Mixpanel/GA):
Since our data is pre-aggregated at correct granularity (1 doc per day/week/month):
- For KPI TILES: Use MAX to show the most recent/highest value in selected range
  This is equivalent to last_value and represents point-in-time active users
  (Shows: "What is the latest/peak DAU/WAU/MAU in this period?")
- For TREND LINES: Data is already at correct granularity
  (Each point = actual unique user count for that day/week/month)

WHY MAX (equivalent to last_value)?
- Analytics standard: DAU/WAU/MAU are point-in-time metrics, not averages
- MAX on time-sorted data gives us the most recent complete period
- Example: For WAU with multiple weeks, MAX gives the latest week's unique count
- This is how Google Analytics, Mixpanel, and Amplitude display these metrics

WHY NOT AVG?
- avg would give "average daily unique users" which is NOT the DAU definition
- DAU = unique users in the last complete day, not average across days
- avg(daily_active_users) is a trend statistic, not an active user KPI

WHY NOT SUM?
- Would count users multiple times across periods (meaningless)
- Creates impossible scenarios like DAU > MAU
"""

import requests
import json
import uuid
import time

KIBANA_URL = "http://localhost:5601"
KIBANA_USER = "elastic"
KIBANA_PASSWORD = "changeme"
KIBANA_HEADERS = {
    "kbn-xsrf": "true",
    "Content-Type": "application/json"
}


def check_kibana():
    """Check if Kibana is ready"""
    print("⏳ Checking Kibana connection...")
    for i in range(30):
        try:
            response = requests.get(
                f"{KIBANA_URL}/api/status",
                auth=(KIBANA_USER, KIBANA_PASSWORD),
                timeout=5
            )
            if response.status_code == 200:
                print("✅ Kibana is ready!\n")
                return True
        except:
            pass
        time.sleep(2)
    
    print("❌ Cannot connect to Kibana")
    return False


def get_or_create_data_view(name, pattern, time_field=None):
    """Get existing or create new data view"""
    search_url = f"{KIBANA_URL}/api/data_views"
    try:
        response = requests.get(
            search_url,
            auth=(KIBANA_USER, KIBANA_PASSWORD),
            headers=KIBANA_HEADERS
        )
        
        if response.status_code == 200:
            data_views = response.json().get('data_view', [])
            for dv in data_views:
                if dv.get('title') == pattern:
                    dv_id = dv['id']
                    print(f"  📋 Found existing: {name}")

                    # If a time field is provided and the existing data view
                    # doesn't have it set (or uses a different one), update it
                    # so time-based visualizations (line charts, etc.) work
                    # correctly with the dashboard time filter.
                    if time_field and dv.get('timeFieldName') != time_field:
                        try:
                            update_url = f"{KIBANA_URL}/api/data_views/data_view/{dv_id}"
                            update_payload = {
                                "data_view": {
                                    "title": dv.get('title', pattern),
                                    "name": dv.get('name', name),
                                    "timeFieldName": time_field
                                }
                            }
                            update_resp = requests.put(
                                update_url,
                                auth=(KIBANA_USER, KIBANA_PASSWORD),
                                headers=KIBANA_HEADERS,
                                json=update_payload
                            )
                            if update_resp.status_code in [200, 201]:
                                print(f"    🔄 Updated time field for {name} → {time_field}")
                            else:
                                print(f"    ⚠️  Could not update time field for {name}: {update_resp.status_code}")
                        except Exception as ue:
                            print(f"    ⚠️  Error updating data view {name}: {ue}")

                    return dv_id
    except Exception as e:
        print(f"  ⚠️  Error searching: {e}")
    
    # Create new data view
    create_url = f"{KIBANA_URL}/api/data_views/data_view"
    payload = {
        "data_view": {
            "title": pattern,
            "name": name
        }
    }
    
    if time_field:
        payload["data_view"]["timeFieldName"] = time_field
    
    try:
        response = requests.post(
            create_url,
            auth=(KIBANA_USER, KIBANA_PASSWORD),
            headers=KIBANA_HEADERS,
            json=payload
        )
        
        if response.status_code in [200, 201]:
            data_view_id = response.json()['data_view']['id']
            print(f"  ✅ Created: {name}")
            return data_view_id
        else:
            print(f"  ❌ Failed: {name}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def create_visualization(title, vis_type, data_view_id, vis_state, description=""):
    """Generic legacy visualization creator (kept for markdown)."""
    vis_id = str(uuid.uuid4())
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{vis_id}"

    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "description": description,
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "index": data_view_id if data_view_id else None,
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": ([
            {
                "name": "kibanaSavedObjectMeta.searchSourceJSON.index",
                "type": "index-pattern",
                "id": data_view_id
            }
        ] if data_view_id else [])
    }

    response = requests.post(
        url,
        auth=(KIBANA_USER, KIBANA_PASSWORD),
        headers=KIBANA_HEADERS,
        json=payload
    )

    if response.status_code in [200, 201]:
        print(f"  ✅ {title}")
        return vis_id
    else:
        print(f"  ❌ {title}: {response.text}")
        return None


def create_lens_metric(title, data_view_id, field, operation_type="max", ignore_global_time=False, formula_expression=None, value_format=None, decimals=1, sort_field=None):
    """Create a Lens metric visualization (lnsMetric).

    When formula_expression is provided, a Lens formula metric is created
    instead of a simple field aggregation.
    For last_value operation, sort_field should be provided to determine which value is "last".
    """
    lens_id = str(uuid.uuid4())
    layer_id = str(uuid.uuid4())
    col_id = str(uuid.uuid4())

    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"

    # --- formatter (Lens) ---
    fmt = None
    if value_format == "percent":
        fmt = {"id": "percent", "params": {"decimals": decimals}}

    # Build metric column definition
    if formula_expression:
        metric_column = {
            "label": title,
            "dataType": "number",
            "operationType": "formula",
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                "formula": formula_expression,
                "isFormulaBroken": False,
                **({"format": fmt} if fmt else {})
            }
        }
    else:
        metric_column = {
            "label": title,
            "dataType": "number",
            "operationType": operation_type,
            "sourceField": field,
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                **({"format": fmt} if fmt else {}),
                **({"sortField": sort_field} if sort_field and operation_type == "last_value" else {})
            }
        }

    layer_state = {
        "indexPatternId": data_view_id,
        "columns": {
            col_id: metric_column
        },
        "columnOrder": [col_id]
    }

    # Use formBased datasource for Kibana 8.x+ and set ignoreGlobalFilters
    datasource_key = "formBased"
    if ignore_global_time:
        layer_state["ignoreGlobalTimeRange"] = True
        layer_state["ignoreGlobalFilters"] = True

    state = {
        "query": {"language": "kuery", "query": ""},
        "filters": [],
        "datasourceStates": {
            datasource_key: {
                "layers": {
                    layer_id: layer_state
                }
            }
        },
        "visualization": {
            "layerId": layer_id,
            "metricAccessor": col_id,
            "title": title,
            "subtitle": "",
            "description": ""
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

    response = requests.post(
        url,
        auth=(KIBANA_USER, KIBANA_PASSWORD),
        headers=KIBANA_HEADERS,
        json=payload
    )

    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens) {title}: {response.text}")
        return None


def create_lens_xy(
    title,
    data_view_id,
    x_field,
    y_field,
    agg_type="sum",
    is_date_x=True,
    series_type="line",
    kql_query="",
    x_label=None,
    y_label=None,
    x_interval=None,
    value_format=None,
    decimals=1
):
    """Create a Lens XY visualization (line/bar) with one metric and one bucket.

    x_label / y_label let us control the axis/tooltip names without
    changing the underlying fields or aggregations.
    """
    lens_id = str(uuid.uuid4())
    layer_id = str(uuid.uuid4())
    x_col_id = str(uuid.uuid4())
    y_col_id = str(uuid.uuid4())

    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"

    fmt = None
    if value_format == "percent":
        fmt = {"id": "percent", "params": {"decimals": decimals}}

    if is_date_x:
        x_column = {
            "label": x_label or x_field,
            "dataType": "date",
            "operationType": "date_histogram",
            "sourceField": x_field,
            "isBucketed": True,
            "scale": "interval",
            "params": {"interval": x_interval or "auto"}
        }
    else:
        # Use a numeric histogram for hour_of_day to avoid the
        # "invalid for use with the Terms aggregation" error.
        if x_field == "hour_of_day":
            x_column = {
                "label": x_label or x_field,
                "dataType": "number",
                "operationType": "histogram",
                "sourceField": x_field,
                "isBucketed": True,
                "scale": "interval",
                "params": {"interval": 1}
            }
        else:
            x_column = {
                "label": x_label or x_field,
                "dataType": "string",
                "operationType": "terms",
                "sourceField": x_field,
                "isBucketed": True,
                "scale": "ordinal",
                "params": {"size": 50, "orderBy": {"type": "alphabetical"}}
            }

    # Ensure Lens uses our custom X-axis label when provided
    if x_label:
        x_column["customLabel"] = True

    if agg_type == "count":
        y_column = {
            "label": y_label or "Count of records",
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio"
        }
    else:
        y_column = {
            "label": y_label or y_field,
            "dataType": "number",
            "operationType": agg_type,
            "sourceField": y_field,
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                **({"format": fmt} if fmt else {})
            }
        }

    # Ensure Lens actually uses our custom metric label in the UI
    if y_label:
        y_column["customLabel"] = True

    state = {
        "query": {"language": "kuery", "query": kql_query or ""},
        "filters": [],
        "datasourceStates": {
            "indexpattern": {
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
                    "showPoints": False,
                    "xAccessor": x_col_id
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

    response = requests.post(
        url,
        auth=(KIBANA_USER, KIBANA_PASSWORD),
        headers=KIBANA_HEADERS,
        json=payload
    )

    if response.status_code in [200, 201]:
        print(f"  ✅ (Lens) {title}")
        return lens_id
    else:
        print(f"  ❌ (Lens) {title}: {response.text}")
        return None


def create_metric(title, field, data_view_id, agg_type="avg"):
    """Create a simple metric visualization"""
    vis_state = {
        "title": title,
        "type": "metric",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": agg_type,
                "params": {"field": field},
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
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 60
                }
            }
        }
    }
    return create_visualization(title, "metric", data_view_id, vis_state)


def create_active_users_metric(title, data_view_id, user_field="player_id.keyword"):
    """Create active users metric using cardinality (unique user count)
    
    This creates a TRUE active user metric by counting unique users in the selected time range.
    Following industry standard (Mixpanel, Google Analytics, Amplitude):
    - Uses cardinality aggregation to count UNIQUE users
    - Respects dashboard time filter
    - Point-in-time metric, not an average
    """
    vis_state = {
        "title": title,
        "type": "metric",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "cardinality",
                "params": {"field": user_field},
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
                "style": {
                    "bgFill": "#000",
                    "bgColor": False,
                    "labelColor": False,
                    "subText": "",
                    "fontSize": 60
                }
            }
        }
    }
    return create_visualization(title, "metric", data_view_id, vis_state)


def create_active_users_with_fixed_window(title, data_view_id, user_field, time_window):
    """Create an active users metric (cardinality on user_field).

    The actual fixed time windows for DAU/WAU/MAU (1/7/30 days)
    are enforced at the dashboard level via panel-level timeRange
    overrides. The time_window parameter is kept only to avoid
    changing the call sites.
    """
    # We use a regular metric visualization (cardinality on user_field).
    return create_active_users_metric(title, data_view_id, user_field)


def create_line_chart_vis(title, data_view_id, date_field, metric_field, agg_type="avg"):
    """Create a line chart"""
    vis_state = {
        "title": title,
        "type": "line",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": agg_type,
                "params": {"field": metric_field},
                "schema": "metric"
            },
            {
                "id": "2",
                "enabled": True,
                "type": "date_histogram",
                "params": {
                    "field": date_field,
                    "calendar_interval": "1d",
                    "min_doc_count": 1
                },
                "schema": "segment"
            }
        ],
        "params": {
            "type": "line",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right"
        }
    }
    return create_visualization(title, "line", data_view_id, vis_state)


def create_bar_chart_vis(title, data_view_id, x_field, y_field):
    """Create a bar chart"""
    # Use a numeric histogram for hour_of_day to avoid the
    # "invalid for use with the Terms aggregation" error.
    if x_field == "hour_of_day":
        bucket_agg = {
            "id": "2",
            "enabled": True,
            "type": "histogram",
            "params": {
                "field": x_field,
                "interval": 1,
                "min_doc_count": 1
            },
            "schema": "segment"
        }
    else:
        bucket_agg = {
            "id": "2",
            "enabled": True,
            "type": "terms",
            "params": {
                "field": x_field,
                "orderBy": "_key",
                "order": "asc",
                "size": 24
            },
            "schema": "segment"
        }

    vis_state = {
        "title": title,
        "type": "histogram",
        "aggs": [
            {
                "id": "1",
                "enabled": True,
                "type": "sum",
                "params": {"field": y_field},
                "schema": "metric"
            },
            bucket_agg
        ],
        "params": {
            "type": "histogram",
            "addTooltip": True,
            "addLegend": False
        }
    }
    return create_visualization(title, "histogram", data_view_id, vis_state)


def create_markdown(text, title=""):
    """Create a markdown panel"""
    vis_id = str(uuid.uuid4())
    url = f"{KIBANA_URL}/api/saved_objects/visualization/{vis_id}"
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "markdown",
                "aggs": [],
                "params": {
                    "fontSize": 12,
                    "openLinksInNewTab": False,
                    "markdown": text
                }
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": "", "filter": []})
            }
        }
    }
    
    response = requests.post(
        url,
        auth=(KIBANA_USER, KIBANA_PASSWORD),
        headers=KIBANA_HEADERS,
        json=payload
    )
    
    if response.status_code in [200, 201]:
        return vis_id
    return None


def create_dashboard(title, visualization_ids):
    """Create dashboard with visualization IDs"""
    dashboard_id = str(uuid.uuid4())
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}"
    
    # Build panels with proper references
    panels = []
    references = []
    
    # Define layout; KPIs follow the dashboard time filter unless overridden
    layout = [
        # Engagement Header (legacy markdown visualization)
        {"vis_id": visualization_ids.get("eng_header"), "x": 0, "y": 0, "w": 48, "h": 5, "name": "eng_header", "so_type": "visualization"},
        # Row 1: DAU/WAU/MAU KPIs
        {"vis_id": visualization_ids.get("dau"), "x": 0,  "y": 5,  "w": 16, "h": 8, "name": "dau", "so_type": "lens", "timeRange": {"from": "now/d", "to": "now"}},
        {"vis_id": visualization_ids.get("wau"), "x": 16, "y": 5,  "w": 16, "h": 8, "name": "wau", "so_type": "lens", "timeRange": {"from": "now-7d", "to": "now"}},
        {"vis_id": visualization_ids.get("mau"), "x": 32, "y": 5,  "w": 16, "h": 8, "name": "mau", "so_type": "lens", "timeRange": {"from": "now-30d", "to": "now"}},
        # Row 2: Additional engagement KPIs
        {"vis_id": visualization_ids.get("avg_session"), "x": 0,  "y": 13, "w": 24, "h": 8, "name": "avg_session", "so_type": "lens"},
        {"vis_id": visualization_ids.get("tracked_users"), "x": 24, "y": 13, "w": 24, "h": 8, "name": "tracked_users", "so_type": "lens"},
        # DAU Trend (Lens line)
        {"vis_id": visualization_ids.get("dau_trend"), "x": 0, "y": 21, "w": 24, "h": 12, "name": "dau_trend", "so_type": "lens"},
        # Sessions (Lens line)
        {"vis_id": visualization_ids.get("sessions"), "x": 24, "y": 21, "w": 24, "h": 12, "name": "sessions", "so_type": "lens"},
        # Hourly (Lens bar chart, last 24 hours)
        {"vis_id": visualization_ids.get("hourly"), "x": 0, "y": 33, "w": 48, "h": 12, "name": "hourly", "so_type": "lens", "timeRange": {"from": "now-24h", "to": "now"}},
        # Retention Header (legacy markdown visualization)
        {"vis_id": visualization_ids.get("ret_header"), "x": 0, "y": 45, "w": 48, "h": 11, "name": "ret_header", "so_type": "visualization"},
        # D1/D7/D30 (Lens metrics)
        {"vis_id": visualization_ids.get("d1"), "x": 0, "y": 53, "w": 16, "h": 8, "name": "d1", "so_type": "lens",
         "timeRange": {"from": "now-2d/d", "to": "now-1d/d"}},
        {"vis_id": visualization_ids.get("d7"), "x": 16, "y": 53, "w": 16, "h": 8, "name": "d7", "so_type": "lens",
         "timeRange": {"from": "now-8d/d", "to": "now-7d/d"}},
        {"vis_id": visualization_ids.get("d30"), "x": 32, "y": 53, "w": 16, "h": 8, "name": "d30", "so_type": "lens",
         "timeRange": {"from": "now-31d/d", "to": "now-30d/d"}},
        # Retention Trend (Lens line)
        {"vis_id": visualization_ids.get("ret_trend"), "x": 0, "y": 61, "w": 48, "h": 12, "name": "ret_trend", "so_type": "lens"},
    ]

    # Remove panel-level timeRange for tracked_users panel and set all-time override
    for item in layout:
        if item.get("name") == "tracked_users":
            if "timeRange" in item:
                del item["timeRange"]
            # Set all-time timeRange override for tracked_users
            item["timeRange"] = {
                "from": "2000-01-01T00:00:00.000Z",
                "to": "now"
            }
    
    for idx, item in enumerate(layout):
        if item["vis_id"]:
            panel_id = f"panel_{idx}"
            ref_name = f"panel_{item['name']}"
            
            panel_config = {
                "version": "8.11.0",
                "gridData": {
                    "x": item["x"],
                    "y": item["y"],
                    "w": item["w"],
                    "h": item["h"],
                    "i": panel_id
                },
                "panelIndex": panel_id,
                "embeddableConfig": {},
                "panelRefName": ref_name
            }

            # Apply panel-level time range override when specified
            if "timeRange" in item:
                panel_config["embeddableConfig"]["timeRange"] = item["timeRange"]

            # No ignoreDashboardFilters for Lens panels

            panels.append(panel_config)

            references.append({
                "name": ref_name,
                "type": item.get("so_type", "lens"),
                "id": item["vis_id"]
            })
    
    payload = {
        "attributes": {
            "title": title,
            "hits": 0,
            "description": "Combined User Engagement & Retention Dashboard",
            "panelsJSON": json.dumps(panels),
            "optionsJSON": json.dumps({
                "hidePanelTitles": False,
                "useMargins": True
            }),
            "version": 1,
            "timeRestore": True,
            "timeFrom": "now-30d",
            "timeTo": "now",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        },
        "references": references
    }
    
    response = requests.post(
        url,
        auth=(KIBANA_USER, KIBANA_PASSWORD),
        headers=KIBANA_HEADERS,
        json=payload
    )
    
    if response.status_code in [200, 201]:
        print(f"\n✅ Dashboard created: {title}")
        return dashboard_id
    else:
        print(f"\n❌ Failed to create dashboard: {response.text}")
        return None


def main():
    """Main execution"""
    print("=" * 80)
    print("🎯 ISM USER ENGAGEMENT & RETENTION DASHBOARD")
    print("=" * 80)
    
    if not check_kibana():
        return
    
    # Create data views
    print("\n📋 Setting up data views...")
    # Raw events for true unique user counts (DAU/WAU/MAU)
    events_view = get_or_create_data_view("Platform Events", "platform-events-*", "@timestamp")
    # Sessionized index for industry-correct Average Session Duration
    sessions_view = get_or_create_data_view("Player Sessions", "player-sessions-*", "session_start")
    # Pre-aggregated metrics for trends
    dau_view = get_or_create_data_view("DAU Metrics", "retention-metrics-daily-active-users", "date")
    wau_view = get_or_create_data_view("WAU Metrics", "retention-metrics-weekly-active-users", "week")
    mau_view = get_or_create_data_view("MAU Metrics", "retention-metrics-monthly-active-users", "month")
    hourly_view = get_or_create_data_view("Hourly Activity", "retention-metrics-hourly-activity", None)
    retention_cohort_view = get_or_create_data_view("Retention Cohort", "retention_cohort", "cohort_date")
    
    if not all([events_view, sessions_view, dau_view, wau_view, mau_view, hourly_view, retention_cohort_view]):
        print("\n❌ Failed to create all data views")
        return
    
    visualization_ids = {}
    
    # ==================== SECTION 1: USER ENGAGEMENT ====================
    print("\n" + "=" * 80)
    print("📊 SECTION 1: USER ENGAGEMENT")
    print("=" * 80)
    
    visualization_ids["eng_header"] = create_markdown(
        "# 📊 USER ENGAGEMENT: **How intensively is the platform being used?**",
        "Engagement Header"
    )
    
    print("\n1. Activity KPIs (follow dashboard time filter)")
    # TRUE DAU/WAU/MAU as UNIQUE USER COUNTS (cardinality)
    # - Based on raw platform-events-* data
    # - Uses unique_count on player_id.keyword (keyword subfield)
    visualization_ids["dau"] = create_lens_metric("Daily Active Users (DAU)", events_view, "player_id.keyword", "unique_count")
    visualization_ids["wau"] = create_lens_metric("Weekly Active Users (WAU)", events_view, "player_id.keyword", "unique_count")
    visualization_ids["mau"] = create_lens_metric("Monthly Active Users (MAU)", events_view, "player_id.keyword", "unique_count")
    # Additional engagement KPIs
    # Avg session duration in MINUTES over all sessions in the selected period,
    # based on the sessionized index (player-sessions-*) with one document per
    # session. This follows the 30-minute inactivity timeout definition.
    visualization_ids["avg_session"] = create_lens_metric(
        "Avg Session Duration (min)",
        sessions_view,
        "session_duration_minutes",
        "average",
    )
    # Total tracked players (all-time), independent of dashboard time filter
    visualization_ids["tracked_users"] = create_lens_metric(
        "Total Tracked Players (All-time)",
        events_view,
        "player_id.keyword",
        "unique_count",
        ignore_global_time=True,
    )
    
    print("\n2. Activity Trends")
    # DAU trend: unique users per day from raw events (always includes latest days)
    visualization_ids["dau_trend"] = create_lens_xy(
        "DAU Trend",
        events_view,
        "@timestamp",
        "player_id.keyword",
        "unique_count",
        is_date_x=True,
        series_type="line",
        x_label="date",
        y_label="Unique count of players",
        x_interval="1d",
    )
    # Sessions per day: count of all events (session_started) per day from raw events
    visualization_ids["sessions"] = create_lens_xy(
        "Sessions per Day",
        events_view,
        "@timestamp",
        "sessions",
        "count",
        is_date_x=True,
        series_type="line",
        kql_query='event_type : "session_started"',
        x_label="date",
        y_label="Count of sessions",
        x_interval="1d",
    )
    
    print("\n3. Activity Patterns")
    # Active users per hour over the last 24h using raw events
    visualization_ids["hourly"] = create_lens_xy(
        "Active Users by Hour",
        events_view,
        "@timestamp",
        "player_id.keyword",
        "unique_count",
        is_date_x=True,
        series_type="bar",
        x_label="date",
        y_label="Unique count of players",
        x_interval="1h",
    )
    
    # ==================== SECTION 2: USER RETENTION ====================
    print("\n" + "=" * 80)
    print("📊 SECTION 2: USER RETENTION")
    print("=" * 80)
    
    visualization_ids["ret_header"] = create_markdown(
        "# 📈 USER RETENTION\n"
        "**Are users coming back?**\n\n"
        "- **D1**: % active 1 day after first session\n"
        "- **D7**: % active 7 days after\n"
        "- **D30**: % active 30 days after",
        "Retention Header"
    )
    
    print("\n4. Retention KPIs")
    # D1/D7/D30 KPIs: Use last_value to show the most recent cohort's retention rate
    # D1: now-2d/d to now-1d/d, D7: now-8d/d to now-7d/d, D30: now-31d/d to now-30d/d
    # Sort by cohort_date to get the most recent cohort
    visualization_ids["d1"] = create_lens_metric("D1 Retention (Latest Complete Cohort)", retention_cohort_view,
                                                 "d1_retention", "last_value", value_format="percent", decimals=1, sort_field="cohort_date")
    visualization_ids["d7"] = create_lens_metric("D7 Retention (Latest Complete Cohort)", retention_cohort_view,
                                                 "d7_retention", "last_value", value_format="percent", decimals=1, sort_field="cohort_date")
    visualization_ids["d30"] = create_lens_metric("D30 Retention (Latest Complete Cohort)", retention_cohort_view,
                                                  "d30_retention", "last_value", value_format="percent", decimals=1, sort_field="cohort_date")

    print("\n5. Retention Trends")
    visualization_ids["ret_trend"] = create_lens_xy(
        "D7 Retention Trend",
        retention_cohort_view,
        "cohort_date",
        "d7_retention",
        "average",
        True,
        "line",
        "cohort_date < now-6d/d",
        "Cohort Date",
        "D7 Retention",
        "1d",
        value_format="percent",
        decimals=1
    )
    # Cohort Size Trend
    visualization_ids["cohort_size_trend"] = create_lens_xy(
        "Cohort Size Trend",
        retention_cohort_view,
        "cohort_date",
        "cohort_size.players",
        "average",
        True,
        "line",
        "",
        "Cohort Date",
        "Cohort Size",
        "1d"
    )
    # Cohort Heatmap/Table (D1, D7, D30)
    # This is a placeholder; actual implementation may require a custom Lens table or heatmap
    # For now, just create a D1 retention table as an example
    visualization_ids["cohort_heatmap"] = create_lens_xy(
        "Cohort D1 Retention Table",
        retention_cohort_view,
        "cohort_date",
        "d1_retention",
        "average",
        True,
        "bar",
        "",
        "Cohort Date",
        "D1 Retention",
        "1d"
    )
    
    # Create dashboard
    print("\n🎨 Creating dashboard...")
    dashboard_id = create_dashboard("User Engagement & Retention", visualization_ids)
    
    if dashboard_id:
        dashboard_url = f"{KIBANA_URL}/app/dashboards#/view/{dashboard_id}"
        print("\n" + "=" * 80)
        print("✅ DASHBOARD READY!")
        print("=" * 80)
        print(f"\n🌐 URL: {dashboard_url}")
        print(f"\n🔐 Login: elastic / changeme")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

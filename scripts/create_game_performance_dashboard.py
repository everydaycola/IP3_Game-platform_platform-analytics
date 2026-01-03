#!/usr/bin/env python3
"""
Game Performance Dashboard Creator (Lens-based) - FIXED VERSION
Uses the same Lens structure as create_retention_engagement_dashboard.py which is proven to work.
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

ES_URL = "http://localhost:9200"
ES_USER = "elastic"
ES_PASSWORD = "changeme"


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


def resolve_field(base_field):
    """Resolve the correct field name for aggregations."""
    try:
        response = requests.get(
            f"{ES_URL}/platform-events-*/_mapping",
            auth=(ES_USER, ES_PASSWORD),
            timeout=10,
        )
        if response.status_code != 200:
            print(f"⚠️  Could not load mappings ({response.status_code}), using '{base_field}'")
            return base_field

        mappings = response.json() or {}
        if not mappings:
            return base_field

        index_name = list(mappings.keys())[0]
        props = mappings.get(index_name, {}).get("mappings", {}).get("properties", {})
        field_def = props.get(base_field, {})

        keyword_sub = field_def.get("fields", {}).get("keyword") if isinstance(field_def, dict) else None
        if keyword_sub is not None:
            resolved = f"{base_field}.keyword"
            print(f"   ✅ Using '{resolved}' for aggregations")
            return resolved

        print(f"   ℹ️  Using '{base_field}' for aggregations (no .keyword subfield)")
        return base_field
    except Exception as e:
        print(f"⚠️  Error resolving field '{base_field}': {e}. Using base field.")
        return base_field


def get_or_create_data_view(name, pattern, time_field="@timestamp"):
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
                    print(f"  ✓ Found data view: {name} (ID: {dv_id})")
                    return dv_id
    except Exception as e:
        print(f"  ⚠️  Error searching: {e}")

    # Create new data view
    create_url = f"{KIBANA_URL}/api/data_views/data_view"
    payload = {
        "data_view": {
            "id": pattern,  # Use pattern as ID for consistency
            "title": pattern,
            "name": name,
            "timeFieldName": time_field
        }
    }

    try:
        response = requests.post(
            create_url,
            auth=(KIBANA_USER, KIBANA_PASSWORD),
            headers=KIBANA_HEADERS,
            json=payload
        )

        if response.status_code in [200, 201]:
            data_view_id = response.json()['data_view']['id']
            print(f"  ✅ Created data view: {name} (ID: {data_view_id})")
            return data_view_id
        else:
            print(f"  ❌ Failed to create: {name} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def create_lens_metric(title, data_view_id, field, operation_type="count", kql_filter="", value_format=None, decimals=1):
    """
    Create a Lens metric visualization using the SAME structure as create_retention_engagement_dashboard.py
    
    operation_type can be: count, unique_count, sum, average, max, min
    """
    lens_id = str(uuid.uuid4())
    layer_id = str(uuid.uuid4())
    col_id = str(uuid.uuid4())

    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"

    # Formatter
    fmt = None
    if value_format == "percent":
        fmt = {"id": "percent", "params": {"decimals": decimals}}
    elif value_format == "number":
        fmt = {"id": "number", "params": {"decimals": decimals}}

    # Build metric column - matching the working create_retention_engagement_dashboard.py structure
    if operation_type == "count":
        metric_column = {
            "label": title,
            "customLabel": True,
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                **({"format": fmt} if fmt else {})
            }
        }
    else:
        metric_column = {
            "label": title,
            "customLabel": True,
            "dataType": "number",
            "operationType": operation_type,
            "sourceField": field,
            "isBucketed": False,
            "scale": "ratio",
            "params": {
                **({"format": fmt} if fmt else {})
            }
        }

    layer_state = {
        "indexPatternId": data_view_id,
        "columns": {
            col_id: metric_column
        },
        "columnOrder": [col_id]
    }

    # Use formBased datasource for Kibana 8.x+ (same as working script)
    state = {
        "query": {"language": "kuery", "query": kql_filter},
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
            "metricAccessor": col_id,  # This is the key - must be metricAccessor, not accessor
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
        print(f"  ✅ {title}")
        return lens_id
    else:
        print(f"  ❌ {title}: {response.text[:300]}")
        return None


def create_lens_xy_chart(title, data_view_id, x_field, y_field, y_operation="count",
                         chart_type="bar_horizontal", kql_filter="", x_label=None, y_label=None,
                         split_field=None):
    """Create a Lens XY chart using the SAME structure as create_retention_engagement_dashboard.py"""
    lens_id = str(uuid.uuid4())
    layer_id = str(uuid.uuid4())
    x_col_id = str(uuid.uuid4())
    y_col_id = str(uuid.uuid4())
    split_col_id = str(uuid.uuid4()) if split_field else None

    url = f"{KIBANA_URL}/api/saved_objects/lens/{lens_id}"

    # X-axis column (bucket)
    if x_field == "@timestamp":
        x_column = {
            "label": x_label or "Datum",
            "customLabel": True,
            "dataType": "date",
            "operationType": "date_histogram",
            "sourceField": x_field,
            "isBucketed": True,
            "scale": "interval",
            "params": {"interval": "auto", "includeEmptyRows": True}
        }
    else:
        x_column = {
            "label": x_label or x_field,
            "customLabel": True,
            "dataType": "string",
            "operationType": "terms",
            "sourceField": x_field,
            "isBucketed": True,
            "scale": "ordinal",
            "params": {
                "size": 10,
                "orderBy": {"type": "column", "columnId": y_col_id},
                "orderDirection": "desc"
            }
        }

    # Y-axis column (metric)
    if y_operation == "count":
        y_column = {
            "label": y_label or "Aantal",
            "customLabel": True,
            "dataType": "number",
            "operationType": "count",
            "sourceField": "___records___",
            "isBucketed": False,
            "scale": "ratio"
        }
    elif y_operation == "unique_count":
        y_column = {
            "label": y_label or "Unieke spelers",
            "customLabel": True,
            "dataType": "number",
            "operationType": "unique_count",
            "sourceField": y_field,
            "isBucketed": False,
            "scale": "ratio"
        }
    else:
        y_column = {
            "label": y_label or y_field,
            "customLabel": True,
            "dataType": "number",
            "operationType": y_operation,
            "sourceField": y_field,
            "isBucketed": False,
            "scale": "ratio"
        }

    columns = {
        x_col_id: x_column,
        y_col_id: y_column
    }
    column_order = [x_col_id, y_col_id]

    # Split series column
    if split_field:
        split_column = {
            "label": "Spel",
            "customLabel": True,
            "dataType": "string",
            "operationType": "terms",
            "sourceField": split_field,
            "isBucketed": True,
            "scale": "ordinal",
            "params": {
                "size": 6,
                "orderBy": {"type": "column", "columnId": y_col_id},
                "orderDirection": "desc"
            }
        }
        columns[split_col_id] = split_column
        column_order.insert(1, split_col_id)

    layer_state = {
        "indexPatternId": data_view_id,
        "columns": columns,
        "columnOrder": column_order
    }

    # Use formBased datasource (same as working script)
    state = {
        "query": {"language": "kuery", "query": kql_filter},
        "filters": [],
        "datasourceStates": {
            "formBased": {
                "layers": {
                    layer_id: layer_state
                }
            }
        },
        "visualization": {
            "title": title,
            "legend": {"isVisible": True, "position": "right"},
            "preferredSeriesType": "line" if chart_type == "line" else "bar_horizontal" if chart_type == "bar_horizontal" else "bar",
            "layers": [
                {
                    "layerId": layer_id,
                    "accessors": [y_col_id],
                    "position": "top",
                    "seriesType": "line" if chart_type == "line" else "bar_horizontal" if chart_type == "bar_horizontal" else "bar",
                    "showGridlines": False,
                    "xAccessor": x_col_id,
                    **({"splitAccessor": split_col_id} if split_field else {})
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
        print(f"  ✅ {title}")
        return lens_id
    else:
        print(f"  ❌ {title}: {response.text[:300]}")
        return None


def create_dashboard(title, visualization_ids):
    """Create the Game Performance Dashboard"""
    dashboard_id = str(uuid.uuid4())
    url = f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}"

    panels = []
    references = []

    layout = [
        # Row 1: KPI Metrics (5 cards)
        {"vis_id": visualization_ids.get("total_sessions"), "x": 0, "y": 0, "w": 10, "h": 8, "name": "total_sessions"},
        {"vis_id": visualization_ids.get("unique_players"), "x": 10, "y": 0, "w": 10, "h": 8, "name": "unique_players"},
        {"vis_id": visualization_ids.get("avg_duration"), "x": 20, "y": 0, "w": 10, "h": 8, "name": "avg_duration"},
        {"vis_id": visualization_ids.get("completion_rate"), "x": 30, "y": 0, "w": 9, "h": 8, "name": "completion_rate"},
        {"vis_id": visualization_ids.get("abandon_rate"), "x": 39, "y": 0, "w": 9, "h": 8, "name": "abandon_rate"},

        # Row 2: Sessions per game & Unique players (side by side)
        {"vis_id": visualization_ids.get("sessions_per_game"), "x": 0, "y": 8, "w": 24, "h": 14, "name": "sessions_per_game"},
        {"vis_id": visualization_ids.get("players_per_game"), "x": 24, "y": 8, "w": 24, "h": 14, "name": "players_per_game"},

        # Row 3: Evolutie sessies per spel (FULL WIDTH)
        {"vis_id": visualization_ids.get("game_evolution"), "x": 0, "y": 22, "w": 48, "h": 14, "name": "game_evolution"},

        # Row 4: Duration and activity
        {"vis_id": visualization_ids.get("duration_per_game"), "x": 0, "y": 36, "w": 24, "h": 14, "name": "duration_per_game"},
        {"vis_id": visualization_ids.get("daily_activity"), "x": 24, "y": 36, "w": 24, "h": 14, "name": "daily_activity"},
    ]

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

            panels.append(panel_config)

            references.append({
                "name": ref_name,
                "type": "lens",
                "id": item["vis_id"]
            })

    payload = {
        "attributes": {
            "title": title,
            "hits": 0,
            "description": "Game Performance Dashboard - Inzicht in spelprestaties en populariteit",
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
        print(f"\n❌ Failed to create dashboard: {response.text[:500]}")
        return None


def main():
    """Main execution"""
    print("=" * 80)
    print("🎮 GAME PERFORMANCE DASHBOARD (FIXED)")
    print("=" * 80)

    if not check_kibana():
        return

    # Resolve field names
    print("\n🔍 Resolving field mappings...")
    player_field = resolve_field("player_id")
    game_field = resolve_field("game_name")

    # Get or create data view
    print("\n📋 Setting up data view...")
    events_view = get_or_create_data_view("Platform Events", "platform-events-*", "@timestamp")

    if not events_view:
        print("\n❌ Failed to get data view")
        return

    visualization_ids = {}

    # ==================== KPI METRICS ====================
    print("\n" + "=" * 80)
    print("📊 Creating KPI Metrics")
    print("=" * 80)

    # 1. Total Sessions - COUNT of game_started events
    visualization_ids["total_sessions"] = create_lens_metric(
        "Totale sessies",
        events_view,
        "___records___",
        "count",
        kql_filter='event_type: "game_started"'
    )

    # 2. Unique Players - UNIQUE_COUNT of player_id
    visualization_ids["unique_players"] = create_lens_metric(
        "Unieke spelers",
        events_view,
        player_field,
        "unique_count",
        kql_filter='event_type: "game_started"'
    )

    # 3. Average Session Duration - AVERAGE of session_duration_seconds (in minutes)
    visualization_ids["avg_duration"] = create_lens_metric(
        "Gem. sessieduur (sec)",
        events_view,
        "session_duration_seconds",
        "average",
        kql_filter='event_type: ("game_ended" OR "game_abandoned")'
    )

    # 4. Completion Rate - COUNT of game_ended (displayed as number, user can calculate %)
    visualization_ids["completion_rate"] = create_lens_metric(
        "Voltooide games",
        events_view,
        "___records___",
        "count",
        kql_filter='event_type: "game_ended"'
    )

    # 5. Abandon Rate - COUNT of game_abandoned
    visualization_ids["abandon_rate"] = create_lens_metric(
        "Verlaten games",
        events_view,
        "___records___",
        "count",
        kql_filter='event_type: "game_abandoned"'
    )

    # ==================== CHARTS ====================
    print("\n" + "=" * 80)
    print("📊 Creating Charts")
    print("=" * 80)

    # 6. Sessions per Game
    visualization_ids["sessions_per_game"] = create_lens_xy_chart(
        "Sessies per spel",
        events_view,
        game_field,
        "___records___",
        "count",
        "bar_horizontal",
        kql_filter='event_type: "game_started"',
        x_label="Spel",
        y_label="Aantal sessies"
    )

    # 7. Unique Players per Game
    visualization_ids["players_per_game"] = create_lens_xy_chart(
        "Unieke spelers per spel",
        events_view,
        game_field,
        player_field,
        "unique_count",
        "bar_horizontal",
        kql_filter='event_type: "game_started"',
        x_label="Spel",
        y_label="Unieke spelers"
    )

    # 8. Game Evolution Over Time
    visualization_ids["game_evolution"] = create_lens_xy_chart(
        "Evolutie sessies per spel",
        events_view,
        "@timestamp",
        "___records___",
        "count",
        "line",
        kql_filter='event_type: "game_started"',
        x_label="Datum",
        y_label="Aantal sessies",
        split_field=game_field
    )

    # 9. Duration per Game
    visualization_ids["duration_per_game"] = create_lens_xy_chart(
        "Gem. sessieduur per spel",
        events_view,
        game_field,
        "session_duration_seconds",
        "average",
        "bar_horizontal",
        kql_filter='event_type: ("game_ended" OR "game_abandoned")',
        x_label="Spel",
        y_label="Gem. duur (sec)"
    )

    # 10. Daily Activity
    visualization_ids["daily_activity"] = create_lens_xy_chart(
        "Activiteit per dag",
        events_view,
        "@timestamp",
        "___records___",
        "count",
        "bar",
        kql_filter='event_type: "game_started"',
        x_label="Datum",
        y_label="Aantal sessies"
    )

    # ==================== CREATE DASHBOARD ====================
    print("\n" + "=" * 80)
    print("🎨 Creating Dashboard")
    print("=" * 80)

    dashboard_id = create_dashboard("Game Performance Dashboard", visualization_ids)

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

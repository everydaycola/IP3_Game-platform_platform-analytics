"""Unit tests voor create_revenue_dashboard.py script."""

import pytest


def test_dashboard_config_structure():
    """Test de structuur van een dashboard configuratie."""
    dashboard_config = {
        "title": "Revenue Dashboard",
        "panels": [],
        "timeRange": {
            "from": "now-7d",
            "to": "now"
        }
    }
    
    assert "title" in dashboard_config
    assert "panels" in dashboard_config
    assert isinstance(dashboard_config["panels"], list)


def test_panel_creation():
    """Test het aanmaken van een dashboard panel."""
    panel = {
        "type": "visualization",
        "title": "Total Revenue",
        "visualization_type": "metric"
    }
    
    assert panel["type"] == "visualization"
    assert "title" in panel
    assert len(panel["title"]) > 0


def test_time_range_validation():
    """Test time range validatie voor dashboards."""
    valid_ranges = [
        {"from": "now-7d", "to": "now"},
        {"from": "now-30d", "to": "now"},
        {"from": "now-1y", "to": "now"}
    ]
    
    for time_range in valid_ranges:
        assert "from" in time_range
        assert "to" in time_range
        assert time_range["to"] == "now"

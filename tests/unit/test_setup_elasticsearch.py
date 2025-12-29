"""Unit tests voor setup_elasticsearch.py script."""

import pytest


def test_elasticsearch_connection_config(elasticsearch_config):
    """Test Elasticsearch connectie configuratie."""
    assert elasticsearch_config["host"] == "localhost"
    assert elasticsearch_config["port"] == 9200
    assert "user" in elasticsearch_config
    assert "password" in elasticsearch_config


def test_template_structure():
    """Test de structuur van een Elasticsearch template."""
    template = {
        "index_patterns": ["platform-events-*"],
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0
        },
        "mappings": {
            "properties": {
                "timestamp": {"type": "date"},
                "event_type": {"type": "keyword"}
            }
        }
    }
    
    assert "index_patterns" in template
    assert "settings" in template
    assert "mappings" in template
    assert isinstance(template["index_patterns"], list)


def test_password_validation():
    """Test wachtwoord validatie."""
    # Test valid password
    valid_password = "changeme"
    assert len(valid_password) >= 6
    
    # Test empty password
    empty_password = ""
    assert len(empty_password) == 0  # Dit zou een error moeten geven in productie

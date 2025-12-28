"""Pytest configuration en shared fixtures."""

import pytest


@pytest.fixture
def elasticsearch_config():
    """Elasticsearch configuratie voor tests."""
    return {
        "host": "localhost",
        "port": 9200,
        "user": "elastic",
        "password": "changeme"
    }


@pytest.fixture
def rabbitmq_config():
    """RabbitMQ configuratie voor tests."""
    return {
        "host": "localhost",
        "port": 5672,
        "user": "admin",
        "password": "admin"
    }

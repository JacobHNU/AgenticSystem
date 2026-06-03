import pytest
from app.monitoring.metrics import MetricsCollector

def test_metrics_collector_init():
    collector = MetricsCollector()
    assert collector is not None

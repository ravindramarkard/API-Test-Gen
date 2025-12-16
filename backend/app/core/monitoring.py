"""
Monitoring and metrics setup.
"""
import logging
from prometheus_client import Counter, Histogram, generate_latest
from fastapi import Response

logger = logging.getLogger(__name__)

# Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

test_generation_total = Counter(
    'test_generation_total',
    'Total test generations',
    ['project_id', 'format']
)

test_execution_total = Counter(
    'test_execution_total',
    'Total test executions',
    ['test_suite_id', 'status']
)


def get_metrics():
    """Get Prometheus metrics."""
    return generate_latest()


def record_http_request(method: str, endpoint: str, status: int, duration: float):
    """Record HTTP request metrics."""
    http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
    http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)





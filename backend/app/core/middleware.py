"""
Custom middleware for monitoring and error handling.
"""
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.monitoring import record_http_request

logger = logging.getLogger(__name__)


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware for request monitoring."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        endpoint = request.url.path
        method = request.method
        status = response.status_code
        
        record_http_request(method, endpoint, status, duration)
        
        # Log slow requests
        if duration > 1.0:
            logger.warning(
                f"Slow request: {method} {endpoint} took {duration:.2f}s"
            )
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for error handling."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(
                f"Unhandled error: {str(e)}",
                exc_info=True
            )
            # Re-raise to let FastAPI handle it
            raise



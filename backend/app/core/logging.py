"""
Logging configuration.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging():
    """Configure application logging."""
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            RotatingFileHandler(
                log_dir / "app.log",
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            ),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)





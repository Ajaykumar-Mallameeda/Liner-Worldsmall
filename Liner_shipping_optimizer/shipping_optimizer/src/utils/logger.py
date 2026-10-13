import structlog
import logging
from pathlib import Path
from datetime import datetime

def setup_logging(log_dir:Path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"app_{timestamp}.log"
    
    structlog.configure(
        processors = [
            structlog.processors.TimeStamper(fmt = "iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=open(log_file, 'a')),    
    )
    
    return structlog.get_logger()

from src.utils.config import Config
logger = setup_logging(Config.LOGS_DIR)

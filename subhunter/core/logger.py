import os
import logging
from datetime import datetime
from .config import CONFIG_DIR

LOG_DIR = os.path.join(CONFIG_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "subhunter.log")


def setup_logger():
    """Configure logging to file and return the logger."""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger("subhunter")
    logger.setLevel(logging.DEBUG)

    # Don't add handlers twice
    if logger.handlers:
        return logger

    # File handler — detailed logs with rotation (keep last 5MB)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))

    # Truncate if too large (>5MB)
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 5_000_000:
            with open(LOG_FILE, 'w') as f:
                f.write(f"--- Log truncated at {datetime.now().isoformat()} ---\n")
    except OSError:
        pass

    logger.addHandler(fh)
    return logger


log = setup_logger()

import yaml
import logging
from typing import Dict, Any

def load_config(file_path: str) -> Dict[str, Any]:
    logger = logging.getLogger(__name__)
    try:
        with open(file_path, "r") as f:
            config = yaml.safe_load(f)
        logger.info("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise
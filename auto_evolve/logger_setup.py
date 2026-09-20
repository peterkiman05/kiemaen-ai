import logging
import yaml
from pathlib import Path

def load_config(config_path="auto_evolve/config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def setup_logger(name="auto_evolve", config=None):
    config = config or load_config()
    log_file = config.get("log_file", "auto_evolve/auto_evolve.log")
    log_level = config.get("log_level", "INFO").upper()

    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    if not logger.handlers:
        fh = logging.FileHandler(log_file)
        fh.setLevel(getattr(logging, log_level, logging.INFO))
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, log_level, logging.INFO))
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    logger.propagate = False
    return logger

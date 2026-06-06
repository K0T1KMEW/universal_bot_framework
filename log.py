import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

def setup_logger(name: str = None, level: str = None, log_dir: str = None) -> logging.Logger:
    if name is None:
        logger = logging.getLogger()
    else:
        logger = logging.getLogger(name)
    
    logger.handlers = []
    if level is None:
        logger.addHandler(logging.NullHandler())
        return logger

    logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - [%(name)s] %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_dir:
        if name is None:
            safe_name = "root"
        else:
            safe_name = name.replace('.', os.sep)
        log_path = os.path.join(log_dir, safe_name)
        os.makedirs(log_path, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        file_path = os.path.join(log_path, f"{today}.log")
        file_handler = TimedRotatingFileHandler(
            file_path, when="midnight", interval=1, backupCount=30, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
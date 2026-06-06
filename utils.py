import asyncio
import logging
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Optional[str] = None):
    """Setup logging configuration"""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=handlers
    )


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    if path.suffix in [".yaml", ".yml"]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    elif path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported config format: {path.suffix}")


def run_bot(bot, *args, **kwargs):
    import asyncio
    
    async def runner():
        await bot.startup()
        await bot.start(*args, **kwargs)
    
    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    finally:
        asyncio.run(bot.shutdown())


class Singleton(type):
    _instances = {}
    
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def escape_markdown(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    for char in escape_chars:
        text = text.replace(char, f"\\{char}")
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


async def async_sleep(seconds: float):
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        pass
import warnings

warnings.warn(
    "base.py is deprecated. Import Bot, Command, Handler from universal_bot_framework import Bot",
    DeprecationWarning,
    stacklevel=2
)

from .bot import Bot as BaseBot, Command, Handler

__all__ = ["BaseBot", "Command", "Handler"]
import warnings

from .bot import Bot
from .context import Platform, EventType, Context, User, Chat, Message, CallbackQuery, Attachment
from .filters import (
    text, chat_type, callback_data, user, command,
    and_, or_, not_,
    is_private, is_group, is_channel,
    user_id, chat_id, has_args, is_command,
    platform, state
)
from .exceptions import (
    BotError, HandlerError, PlatformError, ConfigurationError,
    MiddlewareError, FilterError, ValidationError
)
from .middlewares import (
    BaseMiddleware, LoggingMiddleware, RateLimitMiddleware,
    DatabaseMiddleware, StatsMiddleware
)
from .utils import (
    setup_logging, load_config, run_bot, Singleton,
    escape_markdown, truncate_text, async_sleep
)

from .keyboards import (
    InlineButton, ReplyButton, InlineKeyboard, ReplyKeyboard,
    ButtonStyle, send_with_keyboard
)

from .states import State, StatesGroup
from .storage import BaseStorage, MemoryStorage, JSONStorage

try:
    from .platforms.telegram import TelegramBot
    TELEGRAM_AVAILABLE = True
except ImportError as e:
    warnings.warn(f"Telegram platform not available: {e}")
    TelegramBot = None
    TELEGRAM_AVAILABLE = False

try:
    from .platforms.vk import VKBot
    VK_AVAILABLE = True
except ImportError as e:
    warnings.warn(f"VK platform not available: {e}")
    VKBot = None

__version__ = "0.2.0"

__all__ = [
    # Core
    "Bot",
    "Command",
    "Handler",

    # Context
    "Platform",
    "EventType",
    "Context",
    "User",
    "Chat",
    "Message",
    "CallbackQuery",

    # Filters
    "text",
    "chat_type",
    "callback_data",
    "user",
    "command",
    "and_",
    "or_",
    "not_",
    "is_private",
    "is_group",
    "is_channel",
    "user_id",
    "chat_id",
    "has_args",
    "is_command",
    "platform",

    # Exceptions
    "BotError",
    "HandlerError",
    "PlatformError",
    "ConfigurationError",
    "MiddlewareError",
    "FilterError",
    "ValidationError",

    # Middlewares
    "BaseMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "DatabaseMiddleware",
    "StatsMiddleware",

    # Utils
    "setup_logging",
    "load_config",
    "run_bot",
    "Singleton",
    "escape_markdown",
    "truncate_text",
    "async_sleep",

    # Keyboards
    "InlineButton", "ReplyButton", "InlineKeyboard", "ReplyKeyboard",
    "ButtonStyle", "send_with_keyboard",

    # States
    "State", "StatesGroup",

    # Storages
    "BaseStorage", "MemoryStorage", "JSONStorage",

    # Version
    "__version__",
]

if TELEGRAM_AVAILABLE:
    __all__.append("TelegramBot")
if VK_AVAILABLE:
    __all__.append("VKBot")
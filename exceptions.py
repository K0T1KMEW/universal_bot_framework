class BotError(Exception):
    pass


class HandlerError(BotError):
    pass


class PlatformError(BotError):
    pass


class ConfigurationError(BotError):
    pass


class MiddlewareError(BotError):
    pass


class FilterError(BotError):
    pass


class ValidationError(BotError):
    pass
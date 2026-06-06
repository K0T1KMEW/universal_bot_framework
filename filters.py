from typing import Callable, List, Union
from .context import Context, Platform
from .states import State


class Text:
    @staticmethod
    def equals(text: str) -> Callable:
        return lambda ctx: ctx.message and ctx.message.text == text

    @staticmethod
    def contains(text: str) -> Callable:
        return lambda ctx: ctx.message and text in ctx.message.text

    @staticmethod
    def startswith(prefix: str) -> Callable:
        return lambda ctx: ctx.message and ctx.message.text.startswith(prefix)

    @staticmethod
    def endswith(suffix: str) -> Callable:
        return lambda ctx: ctx.message and ctx.message.text.endswith(suffix)

    @staticmethod
    def regex(pattern: str) -> Callable:
        import re
        regex = re.compile(pattern)
        return lambda ctx: ctx.message and bool(regex.search(ctx.message.text or ""))


class ChatType:
    @staticmethod
    def private() -> Callable:
        return lambda ctx: ctx.chat and ctx.chat.type == "private"

    @staticmethod
    def group() -> Callable:
        return lambda ctx: ctx.chat and ctx.chat.type in ["group", "supergroup"]

    @staticmethod
    def channel() -> Callable:
        return lambda ctx: ctx.chat and ctx.chat.type == "channel"


class CallbackData:
    @staticmethod
    def equals(data: str) -> Callable:
        return lambda ctx: ctx.callback_query and ctx.callback_query.data == data

    @staticmethod
    def startswith(prefix: str) -> Callable:
        return lambda ctx: ctx.callback_query and ctx.callback_query.data.startswith(prefix)

    @staticmethod
    def contains(text: str) -> Callable:
        return lambda ctx: ctx.callback_query and text in ctx.callback_query.data


class UserFilter:
    @staticmethod
    def is_bot() -> Callable:
        return lambda ctx: ctx.user and ctx.user.is_bot

    @staticmethod
    def is_admin() -> Callable:
        return lambda ctx: False

    @staticmethod
    def id(user_id: int) -> Callable:
        return lambda ctx: ctx.user and ctx.user.id == user_id

    @staticmethod
    def username(username: str) -> Callable:
        return lambda ctx: ctx.user and ctx.user.username == username


class CommandFilter:
    @staticmethod
    def has_args() -> Callable:
        return lambda ctx: len(ctx.args) > 0

    @staticmethod
    def min_args(min_count: int) -> Callable:
        return lambda ctx: len(ctx.args) >= min_count

    @staticmethod
    def max_args(max_count: int) -> Callable:
        return lambda ctx: len(ctx.args) <= max_count


def platform(plat: Platform) -> Callable:
    return lambda ctx: ctx.platform == plat


def and_(*filters: Callable) -> Callable:
    async def combined(ctx):
        for f in filters:
            result = f(ctx)
            if hasattr(result, '__await__'):
                result = await result
            if not result:
                return False
        return True
    return combined


def or_(*filters: Callable) -> Callable:
    async def combined(ctx):
        for f in filters:
            result = f(ctx)
            if hasattr(result, '__await__'):
                result = await result
            if not result:
                continue
            return True
        return False
    return combined


def not_(filter_func: Callable) -> Callable:
    async def negated(ctx):
        result = filter_func(ctx)
        if hasattr(result, '__await__'):
            result = await result
        return not result
    return negated


def is_private() -> Callable:
    return ChatType.private()


def is_group() -> Callable:
    return ChatType.group()


def is_channel() -> Callable:
    return ChatType.channel()


def user_id(user_id: int) -> Callable:
    return UserFilter.id(user_id)


def chat_id(chat_id: int) -> Callable:
    return lambda ctx: ctx.chat and ctx.chat.id == chat_id


def has_args() -> Callable:
    return CommandFilter.has_args()


def is_command(command: str) -> Callable:
    return lambda ctx: ctx.command == command

def state(state_value: Union[str, State]) -> Callable:
    target = state_value.name if isinstance(state_value, State) else state_value

    async def check(ctx: Context) -> bool:
        current = await ctx.get_state()
        return current == target
    return check


text = Text()
chat_type = ChatType()
callback_data = CallbackData()
user = UserFilter()
command = CommandFilter()
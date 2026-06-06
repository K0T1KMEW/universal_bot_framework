from dataclasses import dataclass
from typing import Optional, Any, Dict, List, Union
from enum import Enum
from .storage import BaseStorage
from .states import State


class Platform(Enum):
    TELEGRAM = "telegram"
    VK = "vk"
    DISCORD = "discord"

class EventType(Enum):
    MESSAGE = "message"
    CALLBACK_QUERY = "callback_query"
    COMMAND = "command"
    REACTION_ADD = "reaction_add"
    REACTION_REMOVE = "reaction_remove"
    NEW_CHAT_MEMBER = "new_chat_member"
    LEFT_CHAT_MEMBER = "left_chat_member"
    CHAT_JOIN_REQUEST = "chat_join_request"
    POLL = "poll"
    POLL_ANSWER = "poll_answer"


@dataclass
class User:
    id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_bot: bool = False
    language_code: Optional[str] = None
    is_premium: bool = False

    @property
    def full_name(self) -> str:
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else str(self.id)


@dataclass
class Chat:
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None

    @property
    def is_private(self) -> bool:
        return self.type == "private"

    @property
    def is_group(self) -> bool:
        return self.type in ["group", "supergroup"]

    @property
    def is_channel(self) -> bool:
        return self.type == "channel"


@dataclass
class Attachment:
    type: str
    id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    raw: Any = None


@dataclass
class Message:
    id: int
    text: Optional[str] = None
    date: Optional[int] = None
    chat: Optional[Chat] = None
    user: Optional[User] = None
    reply_to_message: Optional['Message'] = None
    attachments: Optional[List[Attachment]] = None

    def has_text(self) -> bool:
        return bool(self.text)


@dataclass
class CallbackQuery:
    id: str
    data: str
    user: User
    message: Optional[Message] = None

@dataclass
class InlineQuery:
    id: str
    query: str
    user: User
    offset: str = ""
    chat_type: Optional[str] = None

@dataclass
class ChosenInlineResult:
    result_id: str
    user: User
    query: str
    inline_message_id: Optional[str] = None


class Context:
    def __init__(self, platform: Platform, event_type: EventType, raw_event: Any, bot: Any, adapter: Any):
        self.platform = platform
        self.event_type = event_type
        self.raw_event = raw_event
        self.bot = bot
        self.adapter = adapter

        self.message: Optional[Message] = None
        self.callback_query: Optional[CallbackQuery] = None
        self.user: Optional[User] = None
        self.chat: Optional[Chat] = None
        self.command: Optional[str] = None
        self.args: List[str] = []
        self.kwargs: Dict[str, Any] = {}

        self._reply_mode: bool = True

        self.state: Dict[str, Any] = {}
        self.middleware_data: Dict[str, Any] = {}

        self.inline_query: Optional[InlineQuery] = None
        self.chosen_inline_result: Optional[ChosenInlineResult] = None

        self._storage: Optional[BaseStorage] = None
        self._storage_key: str = ""
        self._user_data: Dict[str, Any] = {}
        self._state: Optional[str] = None

    async def load_user_data(self) -> None:
        if not self._storage or not self._storage_key:
            return
        self._user_data = await self._storage.get_data(self._storage_key)
        self._state = await self._storage.get_state(self._storage_key)

    async def save_user_data(self) -> None:
        if not self._storage or not self._storage_key:
            return
        await self._storage.set_data(self._storage_key, self._user_data)
        await self._storage.set_state(self._storage_key, self._state)

    async def get_user_data(self, key: str, default: Any = None) -> Any:
        return self._user_data.get(key, default)

    async def set_user_data(self, key: str, value: Any) -> None:
        self._user_data[key] = value
        await self.save_user_data()

    async def update_user_data(self, data: Dict[str, Any]) -> None:
        self._user_data.update(data)
        await self.save_user_data()

    async def delete_user_data(self, key: str) -> None:
        if key in self._user_data:
            del self._user_data[key]
            await self.save_user_data()

    async def get_state(self) -> Optional[str]:
        return self._state

    async def set_state(self, state: Optional[Union[str, State]]) -> None:
        if isinstance(state, State):
            state = state.name
        self._state = state
        await self.save_user_data()

    async def reply(self, text: str, **kwargs):
        return await self.adapter.send_message(
            chat_id=self.chat.id if self.chat else None,
            text=text,
            reply_to_message_id=self.message.id if self.message and self._reply_mode else None,
            **kwargs
        )

    async def send_message(self, text: str, **kwargs):
        self._reply_mode = False
        return await self.reply(text, **kwargs)

    async def edit_message(self, text: str, **kwargs):
        return await self.adapter.edit_message(
            chat_id=self.chat.id if self.chat else None,
            message_id=self.message.id if self.message else None,
            text=text,
            **kwargs
        )

    async def delete_message(self, message_id: Optional[int] = None, **kwargs):
        msg_id = message_id or (self.message.id if self.message else None)
        return await self.adapter.delete_message(
            chat_id=self.chat.id if self.chat else None,
            message_id=msg_id,
            **kwargs
        )

    async def answer_callback_query(self, text: Optional[str] = None, **kwargs):
        return await self.adapter.answer_callback_query(
            callback_query_id=self.callback_query.id if self.callback_query else None,
            text=text,
            **kwargs
        )
    
    async def answer_inline_query(self, results: List[Any], **kwargs):
        return await self.adapter.answer_inline_query(
            inline_query_id=self.inline_query.id,
            results=results,
            **kwargs
        )

    def get_arg(self, index: int, default: Any = None) -> Any:
        return self.args[index] if index < len(self.args) else default

    def get_args(self) -> List[str]:
        return self.args.copy()

    def has_args(self) -> bool:
        return len(self.args) > 0
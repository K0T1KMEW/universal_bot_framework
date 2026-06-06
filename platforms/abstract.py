from abc import ABC, abstractmethod
from typing import Any, Optional, List

from ..context import Platform, EventType, Context


class PlatformAdapter(ABC):

    def __init__(self, platform: Platform, token: str, bot):
        self.platform = platform
        self.token = token
        self.bot = bot
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        pass

    @abstractmethod
    async def answer_inline_query(self, inline_query_id: str, results: List[Any], **kwargs) -> Any:
        pass

    @abstractmethod
    async def cleanup(self):
        pass

    @abstractmethod
    async def run(self):
        pass

    @abstractmethod
    async def stop(self):
        pass


    @abstractmethod
    async def send_message(self, chat_id: Any, text: str, **kwargs) -> Any:
        pass

    @abstractmethod
    async def edit_message(self, chat_id: Any, message_id: Any, text: str, **kwargs) -> Any:
        pass

    @abstractmethod
    async def answer_callback_query(self, callback_query_id: str, **kwargs) -> Any:
        pass

    @abstractmethod
    async def delete_message(self, chat_id: Any, message_id: Any, **kwargs) -> Any:
        pass

    @abstractmethod
    async def get_me(self) -> Any:
        pass

    @abstractmethod
    async def get_chat(self, chat_id: Any) -> Any:
        pass

    @abstractmethod
    async def get_user(self, user_id: Any) -> Any:
        pass

    @property
    @abstractmethod
    def raw_client(self):
        pass

    def _get_storage_key(self, ctx: Context) -> str:
        raise NotImplementedError
    
    async def _dispatch_event(self, raw_event: Any, event_type: EventType):
        ctx = self._create_context(raw_event, event_type)
        ctx._storage = self.bot.storage
        ctx._storage_key = self._get_storage_key(ctx)
        await ctx.load_user_data()
        await self.bot._dispatch(ctx)
        await ctx.save_user_data()

    @abstractmethod
    def _create_context(self, raw_event: Any, event_type: EventType) -> Context:
        pass

    
import asyncio
from typing import Any, Optional, List

from aiogram import Bot as AiogramBot, Dispatcher
from aiogram.types import Message as AiogramMessage, CallbackQuery as AiogramCallbackQuery
from aiogram.types import InlineQuery, ChosenInlineResult

from ..context import Platform, EventType, Context, Message, Chat, User, CallbackQuery, Attachment
from .abstract import PlatformAdapter
from ..log import setup_logger


class TelegramAdapter(PlatformAdapter):
    def __init__(self, token: str, bot, log_level: str = None, log_dir: str = None):
        super().__init__(Platform.TELEGRAM, token, bot)
        self.logger = setup_logger('TelegramAdapter', log_level, log_dir)
        self.aiogram_bot = AiogramBot(token=token)
        self.dp = Dispatcher()
        self._setup_handlers()

    def _get_storage_key(self, ctx: Context) -> str:
        platform = self.platform.value
        if ctx.user and ctx.chat and ctx.chat.type != 'private':
            return f"{platform}:group:{ctx.chat.id}:user:{ctx.user.id}"
        if ctx.user:
            return f"{platform}:user:{ctx.user.id}"
        if ctx.chat:
            return f"{platform}:chat:{ctx.chat.id}"
        return f"{platform}:unknown"

    def _setup_handlers(self):

        @self.dp.message()
        async def handle_message(aiogram_message: AiogramMessage):
            self.logger.debug(f"Received message: {aiogram_message.text}")
            await self._dispatch_event(aiogram_message, EventType.MESSAGE)
                
        @self.dp.callback_query()
        async def handle_callback(aiogram_callback: AiogramCallbackQuery):
            await self._dispatch_event(aiogram_callback, EventType.CALLBACK_QUERY)

        @self.dp.inline_query()
        async def handle_inline_query(inline_query: InlineQuery):
            await self._dispatch_event(inline_query, EventType.INLINE_QUERY)

        @self.dp.chosen_inline_result()
        async def handle_chosen_inline_result(chosen_result: ChosenInlineResult):
            await self._dispatch_event(chosen_result, EventType.CHOSEN_INLINE_RESULT)

    async def initialize(self):
        await self.aiogram_bot.get_me()
        self.logger.info(f"Telegram adapter initialized for bot: {self.aiogram_bot.id}")

    async def cleanup(self):
        await self.aiogram_bot.session.close()

    async def run(self):
        await self.dp.start_polling(self.aiogram_bot)

    async def stop(self):
        pass

    @property
    def raw_client(self):
        return self.aiogram_bot

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Any:
        reply_to = kwargs.pop('reply_to_message_id', None)
        return await self.aiogram_bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to,
            **kwargs
        )

    async def edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> Any:
        return await self.aiogram_bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            **kwargs
        )

    async def answer_callback_query(self, callback_query_id: str, **kwargs) -> Any:
        return await self.aiogram_bot.answer_callback_query(
            callback_query_id=callback_query_id,
            **kwargs
        )

    async def delete_message(self, chat_id: int, message_id: int, **kwargs) -> Any:
        return await self.aiogram_bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
            **kwargs
        )
    
    async def answer_inline_query(self, inline_query_id: str, results: List[Any], **kwargs) -> Any:
        return await self.aiogram_bot.answer_inline_query(
            inline_query_id=inline_query_id,
            results=results,
            **kwargs
        )

    async def get_me(self) -> Any:
        return await self.aiogram_bot.get_me()

    async def get_chat(self, chat_id: int) -> Any:
        return await self.aiogram_bot.get_chat(chat_id)

    async def get_user(self, user_id: int) -> Any:
        return None

    def _create_context(self, raw_event: Any, event_type: EventType) -> Context:
        ctx = Context(self.platform, event_type, raw_event, self.bot, adapter=self)

        if isinstance(raw_event, AiogramMessage):
            user = None
            if raw_event.from_user:
                user = User(
                    id=raw_event.from_user.id,
                    username=raw_event.from_user.username,
                    first_name=raw_event.from_user.first_name,
                    last_name=raw_event.from_user.last_name,
                    is_bot=raw_event.from_user.is_bot,
                    language_code=raw_event.from_user.language_code,
                    is_premium=getattr(raw_event.from_user, 'is_premium', False)
                )

            chat = None
            if raw_event.chat:
                chat = Chat(
                    id=raw_event.chat.id,
                    type=raw_event.chat.type,
                    title=raw_event.chat.title,
                    username=raw_event.chat.username
                )

            attachments = []
            if raw_event.photo:
                for photo in raw_event.photo:
                    attachments.append(Attachment(type='photo', raw=photo))
            if raw_event.video:
                attachments.append(Attachment(type='video', raw=raw_event.video))
            if raw_event.document:
                attachments.append(Attachment(type='document', raw=raw_event.document))
            if raw_event.audio:
                attachments.append(Attachment(type='audio', raw=raw_event.audio))
            if raw_event.animation:
                attachments.append(Attachment(type='animation', raw=raw_event.animation))
            if raw_event.sticker:
                attachments.append(Attachment(type='sticker', raw=raw_event.sticker))
            if raw_event.poll:
                attachments.append(Attachment(type='poll', raw=raw_event.poll))

            ctx.message = Message(
                id=raw_event.message_id,
                text=raw_event.text or raw_event.caption,
                date=raw_event.date.timestamp() if raw_event.date else None,
                chat=chat,
                user=user,
                attachments=attachments
            )
            ctx.chat = chat
            ctx.user = user

            if raw_event.text and raw_event.text.startswith('/'):
                parts = raw_event.text[1:].split()
                if parts:
                    ctx.command = parts[0].split('@')[0]
                    ctx.args = parts[1:] if len(parts) > 1 else []

        elif isinstance(raw_event, AiogramCallbackQuery):
            user = None
            if raw_event.from_user:
                user = User(
                    id=raw_event.from_user.id,
                    username=raw_event.from_user.username,
                    first_name=raw_event.from_user.first_name,
                    last_name=raw_event.from_user.last_name,
                    is_bot=raw_event.from_user.is_bot,
                    language_code=raw_event.from_user.language_code,
                    is_premium=getattr(raw_event.from_user, 'is_premium', False)
                )

            message = None
            if raw_event.message:
                chat = None
                if raw_event.message.chat:
                    chat = Chat(
                        id=raw_event.message.chat.id,
                        type=raw_event.message.chat.type,
                        title=raw_event.message.chat.title,
                        username=raw_event.message.chat.username
                    )
                message = Message(
                    id=raw_event.message.message_id,
                    chat=chat
                )

            ctx.callback_query = CallbackQuery(
                id=raw_event.id,
                data=raw_event.data,
                user=user,
                message=message
            )
            ctx.user = user
            ctx.chat = message.chat if message else None

        return ctx

TelegramBot = TelegramAdapter
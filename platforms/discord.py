import asyncio
from typing import Any, Optional, List, Dict, Union

import discord
from discord.ext import commands

from ..context import Platform, EventType, Context, Message, Chat, User, CallbackQuery, Attachment
from .abstract import PlatformAdapter
from ..log import setup_logger


class DiscordAdapter(PlatformAdapter):
    def __init__(self, token: str, bot, log_level: str = None, log_dir: str = None, command_prefix: str = "!"):
        super().__init__(Platform.DISCORD, token, bot)
        self.logger = setup_logger('DiscordAdapter', log_level, log_dir)
        self.token = token
        self.command_prefix = command_prefix

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        self.client = commands.Bot(command_prefix=command_prefix, intents=intents)

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
        @self.client.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.client.user} (ID: {self.client.user.id})")

        @self.client.event
        async def on_message(message: discord.Message):
            if message.author.id == self.client.user.id:
                return
            await self._dispatch_event(message, EventType.MESSAGE)

        @self.client.event
        async def on_interaction(interaction: discord.Interaction):
            if interaction.type == discord.InteractionType.component:
                await self._dispatch_event(interaction, EventType.CALLBACK_QUERY)

    async def initialize(self):
        self.logger.info("Discord adapter initialized")

    async def cleanup(self):
        await self.client.close()

    async def run(self):
        await self.client.start(self.token)

    async def stop(self):
        await self.client.close()

    @property
    def raw_client(self):
        return self.client

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Any:
        channel = self.client.get_channel(chat_id)
        if not channel:
            raise ValueError(f"Channel {chat_id} not found")

        reply_to = kwargs.pop('reply_to_message_id', None)
        if reply_to is not None:
            try:
                reference = await channel.fetch_message(reply_to)
                kwargs['reference'] = reference
            except Exception as e:
                self.logger.warning(f"Could not fetch message {reply_to} for reply: {e}")

        return await channel.send(text, **kwargs)

    async def edit_message(self, chat_id: int, message_id: int, text: str, **kwargs) -> Any:
        channel = self.client.get_channel(chat_id)
        if not channel:
            raise ValueError(f"Channel {chat_id} not found")
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            raise ValueError(f"Message {message_id} not found in channel {chat_id}")
        return await message.edit(content=text, **kwargs)

    async def answer_callback_query(self, callback_query_id: str, **kwargs) -> Any:
        raise NotImplementedError("Use interaction.response directly (available as ctx.raw_event)")

    async def delete_message(self, chat_id: int, message_id: int, **kwargs) -> Any:
        channel = self.client.get_channel(chat_id)
        if not channel:
            raise ValueError(f"Channel {chat_id} not found")
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            raise ValueError(f"Message {message_id} not found in channel {chat_id}")
        return await message.delete()

    async def get_me(self) -> Any:
        return self.client.user

    async def get_chat(self, chat_id: int) -> Any:
        return self.client.get_channel(chat_id)

    async def get_user(self, user_id: int) -> Any:
        user = self.client.get_user(user_id)
        if not user:
            try:
                user = await self.client.fetch_user(user_id)
            except Exception:
                pass
        return user

    async def answer_inline_query(self, inline_query_id: str, results: List[Any], **kwargs) -> Any:
        raise NotImplementedError("Inline queries are not supported in Discord")

    def _create_context(self, raw_event: Any, event_type: EventType) -> Context:
        ctx = Context(self.platform, event_type, raw_event, self.bot, adapter=self)

        if event_type == EventType.MESSAGE:
            message: discord.Message = raw_event
            user = User(
                id=message.author.id,
                username=message.author.name,
                first_name=message.author.display_name,
                last_name=None,
                is_bot=message.author.bot,
                language_code=None,
                is_premium=message.author.premium_since is not None
            )
            chat = Chat(
                id=message.channel.id,
                type=message.channel.type.name,
                title=getattr(message.channel, 'name', None),
                username=None
            )
            attachments = []
            if message.attachments:
                for att in message.attachments:
                    attachments.append(Attachment(
                        type='file',
                        id=att.id,
                        url=att.url,
                        title=att.filename,
                        raw=att
                    ))

            ctx.message = Message(
                id=message.id,
                text=message.content,
                date=message.created_at.timestamp(),
                chat=chat,
                user=user,
                attachments=attachments
            )
            ctx.chat = chat
            ctx.user = user

            if message.content.startswith(self.command_prefix):
                parts = message.content[len(self.command_prefix):].split()
                if parts:
                    ctx.command = parts[0]
                    ctx.args = parts[1:] if len(parts) > 1 else []

        elif event_type == EventType.CALLBACK_QUERY:
            interaction: discord.Interaction = raw_event
            user = User(
                id=interaction.user.id,
                username=interaction.user.name,
                first_name=interaction.user.display_name,
                last_name=None,
                is_bot=interaction.user.bot,
                language_code=None,
                is_premium=False
            )
            message = None
            if interaction.message:
                message = Message(
                    id=interaction.message.id,
                    text=interaction.message.content,
                    chat=Chat(
                        id=interaction.channel.id,
                        type=interaction.channel.type.name,
                        title=getattr(interaction.channel, 'name', None)
                    )
                )

            ctx.callback_query = CallbackQuery(
                id=str(interaction.id),
                data=interaction.data.get('custom_id', ''),
                user=user,
                message=message
            )
            ctx.user = user
            ctx.chat = Chat(
                id=interaction.channel.id,
                type=interaction.channel.type.name,
                title=getattr(interaction.channel, 'name', None)
            )
            ctx.raw_event = interaction

        return ctx
    
DiscordBot = DiscordAdapter
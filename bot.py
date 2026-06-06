import os
import asyncio
import inspect
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Any

from .context import Context, EventType
from .log import setup_logger
from .storage import BaseStorage, MemoryStorage


@dataclass
class Command:
    name: str
    handler: Callable
    description: str = ""
    aliases: List[str] = None
    filters: List[Callable] = None

    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.filters is None:
            self.filters = []


class Handler:
    def __init__(self, func: Callable, filters: List[Callable] = None):
        self.func = func
        self.filters = filters or []

    async def check_filters(self, ctx) -> bool:
        for filter_func in self.filters:
            if inspect.iscoroutinefunction(filter_func):
                result = await filter_func(ctx)
            else:
                result = filter_func(ctx)
            if not result:
                return False
        return True


class Bot:
    def __init__(self, log_level: str = None, logging_enabled: bool = True,
                 log_dir: str = None, storage: Optional[BaseStorage] = None, **kwargs):
        self.logging_enabled = logging_enabled
        if not logging_enabled:
            log_level = None
            log_dir = None
        self.log_level = log_level
        self.log_dir = log_dir
        self.storage = storage or MemoryStorage()

        if log_level is not None:
            setup_logger(None, log_level, log_dir)
        self.logger = setup_logger('Bot', log_level, log_dir) if log_level else None

        self.adapters = []

        if "telegram_token" in kwargs:
            from .platforms.telegram import TelegramAdapter
            self.adapters.append(TelegramAdapter(
                kwargs["telegram_token"], self,
                log_level=self.log_level, log_dir=self.log_dir
            ))

        if "vk_token" in kwargs and "vk_group_id" in kwargs:
            from .platforms.vk import VKAdapter
            user_token = kwargs.get("vk_user_token")
            admin_ids = kwargs.get("vk_admin_ids")
            self.adapters.append(VKAdapter(
                kwargs["vk_token"],
                kwargs["vk_group_id"],
                self,
                user_token=user_token,
                admin_ids=admin_ids,
                log_level=self.log_level,
                log_dir=self.log_dir
            ))

        if "discord_token" in kwargs:
            from .platforms.discord import DiscordAdapter
            self.adapters.append(DiscordAdapter(
                kwargs["discord_token"], self,
                log_level=self.log_level, log_dir=self.log_dir
            ))

        self.commands: Dict[str, Command] = {}
        self.message_handlers: List[Handler] = []
        self.callback_handlers: List[Handler] = []
        self.event_handlers: Dict[EventType, List[Handler]] = defaultdict(list)
        self.inline_handlers: List[Handler] = []
        self.chosen_inline_result_handlers: List[Handler] = []

        self.pre_middleware: List[Callable] = []
        self.post_middleware: List[Callable] = []

        self._startup_callbacks: List[Callable] = []
        self._shutdown_callbacks: List[Callable] = []

    def command(self, name: str, description: str = "", aliases: List[str] = None, filters: List[Callable] = None):
        def decorator(func):
            cmd = Command(name, func, description, aliases or [], filters)
            self.commands[name] = cmd
            for alias in cmd.aliases:
                self.commands[alias] = cmd
            return func
        return decorator

    def message_handler(self, *filters):
        def decorator(func):
            self.message_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    def callback_handler(self, *filters):
        def decorator(func):
            self.callback_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    def event_handler(self, event_type: EventType, *filters):
        def decorator(func):
            handler = Handler(func, list(filters))
            self.event_handlers[event_type].append(handler)
            return func
        return decorator

    def middleware(self, position: str = "pre"):
        def decorator(func):
            if position == "pre":
                self.pre_middleware.append(func)
            else:
                self.post_middleware.append(func)
            return func
        return decorator

    def on_startup(self, func: Callable):
        self._startup_callbacks.append(func)
        return func

    def on_shutdown(self, func: Callable):
        self._shutdown_callbacks.append(func)
        return func

    def inline_handler(self, *filters):
        def decorator(func):
            self.inline_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    def chosen_inline_result_handler(self, *filters):
        def decorator(func):
            self.chosen_inline_result_handlers.append(Handler(func, list(filters)))
            return func
        return decorator

    async def _dispatch(self, ctx: Context):
        if self.logger:
            self.logger.debug(f"Dispatching: event_type={ctx.event_type}, command={ctx.command}")

        for mw in self.pre_middleware:
            await self._run_middleware(mw, ctx)

        try:
            if ctx.command and ctx.command in self.commands:
                cmd = self.commands[ctx.command]
                if cmd.filters:
                    handler_wrapper = Handler(cmd.handler, cmd.filters)
                    if not await handler_wrapper.check_filters(ctx):
                        return
                await cmd.handler(ctx)
                return

            handlers = []
            if ctx.event_type == EventType.MESSAGE:
                handlers = self.message_handlers
            elif ctx.event_type == EventType.CALLBACK_QUERY:
                handlers = self.callback_handlers
            elif ctx.event_type == EventType.INLINE_QUERY:
                handlers = self.inline_handlers
            elif ctx.event_type == EventType.CHOSEN_INLINE_RESULT:
                handlers = self.chosen_inline_result_handlers

            for h in handlers:
                if await h.check_filters(ctx):
                    await h.func(ctx)
                    return

            if ctx.event_type in self.event_handlers:
                for h in self.event_handlers[ctx.event_type]:
                    if await h.check_filters(ctx):
                        await h.func(ctx)
                        return

        except Exception as e:
            if self.logger:
                self.logger.error(f"Handler error: {e}", exc_info=True)
            if ctx.chat:
                await ctx.reply(f"Ошибка: {e}")
        finally:
            for mw in self.post_middleware:
                await self._run_middleware(mw, ctx)

    @staticmethod
    async def _run_middleware(mw, ctx):
        if inspect.iscoroutinefunction(mw):
            await mw(ctx, ctx.bot)
        else:
            mw(ctx, ctx.bot)


    async def startup(self):
        for cb in self._startup_callbacks:
            if inspect.iscoroutinefunction(cb):
                await cb(self)
            else:
                cb(self)
        for adapter in self.adapters:
            await adapter.initialize()

    async def shutdown(self):
        for cb in self._shutdown_callbacks:
            if inspect.iscoroutinefunction(cb):
                await cb(self)
            else:
                cb(self)
        for adapter in self.adapters:
            await adapter.cleanup()

    def run(self):
        async def runner():
            await self.startup()
            await asyncio.gather(*(adapter.run() for adapter in self.adapters))

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            if self.logger:
                self.logger.info("Bot stopped by user")
            else:
                self.logger.info("\nBot stopped by user")
        finally:
            asyncio.run(self.shutdown())
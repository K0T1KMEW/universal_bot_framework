"""
Built-in middlewares (functions or classes with __call__).
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from .context import EventType


class BaseMiddleware:
    pass


class LoggingMiddleware:
    def __init__(self, logger=None):
        self.logger = logger

    async def __call__(self, ctx, bot):
        if self.logger:
            self.logger.info(
                f"[{ctx.platform.value}] {ctx.event_type.value}: "
                f"User {ctx.user.id if ctx.user else 'unknown'} - "
                f"Chat {ctx.chat.id if ctx.chat else 'unknown'}"
            )


class TimingMiddleware:

    async def __call__(self, ctx, bot):
        ctx._start_time = time.time()


class TimingPostMiddleware:
    def __init__(self, logger=None):
        self.logger = logger

    async def __call__(self, ctx, bot):
        if hasattr(ctx, '_start_time'):
            elapsed = time.time() - ctx._start_time
            if self.logger:
                self.logger.debug(f"Handler executed in {elapsed:.3f}s")


class RateLimitMiddleware:
    def __init__(self, rate: int = 5, per: int = 60):
        self.rate = rate
        self.per = per
        self.user_requests: Dict[int, list] = defaultdict(list)

    async def __call__(self, ctx, bot):
        if not ctx.user:
            return

        user_id = ctx.user.id
        now = datetime.now()

        self.user_requests[user_id] = [
            req_time for req_time in self.user_requests[user_id]
            if now - req_time < timedelta(seconds=self.per)
        ]

        if len(self.user_requests[user_id]) >= self.rate:
            await ctx.reply("Rate limit exceeded. Please try again later.")
            return

        self.user_requests[user_id].append(now)


class DatabaseMiddleware:

    def __init__(self, db_connection):
        self.db = db_connection

    async def __call__(self, ctx, bot):
        ctx.db = self.db


class StatsMiddleware:
    def __init__(self):
        self.stats = {
            "messages": 0,
            "commands": 0,
            "callbacks": 0,
            "errors": 0,
        }

    async def __call__(self, ctx, bot):
        if ctx.event_type == EventType.MESSAGE:
            self.stats["messages"] += 1
            if ctx.command:
                self.stats["commands"] += 1
        elif ctx.event_type == EventType.CALLBACK_QUERY:
            self.stats["callbacks"] += 1
        ctx.stats = self.stats.copy()
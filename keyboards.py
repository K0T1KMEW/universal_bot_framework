from enum import Enum
from typing import List, Optional, Any, Dict
from .context import Platform


class ButtonStyle(Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    SUCCESS = "success"


class InlineButton:
    def __init__(self, text: str, callback_data: Optional[str] = None, 
                 url: Optional[str] = None, style: ButtonStyle = ButtonStyle.SECONDARY):
        self.text = text
        self.callback_data = callback_data
        self.url = url
        self.style = style

    def is_url(self) -> bool:
        return self.url is not None


class ReplyButton:
    def __init__(self, text: str, request_contact: bool = False, request_location: bool = False):
        self.text = text
        self.request_contact = request_contact
        self.request_location = request_location


class InlineKeyboard:
    def __init__(self):
        self.rows: List[List[InlineButton]] = []

    def row(self, *buttons: InlineButton) -> 'InlineKeyboard':
        self.rows.append(list(buttons))
        return self

    def is_empty(self) -> bool:
        return not self.rows


class ReplyKeyboard:
    def __init__(self, resize_keyboard: bool = True, one_time_keyboard: bool = False):
        self.resize_keyboard = resize_keyboard
        self.one_time_keyboard = one_time_keyboard
        self.rows: List[List[ReplyButton]] = []

    def row(self, *buttons: ReplyButton) -> 'ReplyKeyboard':
        self.rows.append(list(buttons))
        return self

    def is_empty(self) -> bool:
        return not self.rows


def _convert_reply_to_telegram(kb: ReplyKeyboard):
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    buttons = []
    for row in kb.rows:
        buttons.append([
            KeyboardButton(
                text=btn.text,
                request_contact=btn.request_contact,
                request_location=btn.request_location
            ) for btn in row
        ])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=kb.resize_keyboard,
        one_time_keyboard=kb.one_time_keyboard
    )


def _convert_inline_to_telegram(kb: InlineKeyboard):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    rows = []
    for row in kb.rows:
        btns = []
        for btn in row:
            if btn.is_url():
                btns.append(InlineKeyboardButton(text=btn.text, url=btn.url))
            else:
                btns.append(InlineKeyboardButton(text=btn.text, callback_data=btn.callback_data))
        rows.append(btns)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _convert_inline_to_vk(kb: InlineKeyboard) -> str:
    from vk_api.keyboard import VkKeyboard, VkKeyboardColor
    vk_kb = VkKeyboard(inline=True)
    for row in kb.rows:
        for btn in row:
            color = VkKeyboardColor.SECONDARY
            if btn.style == ButtonStyle.PRIMARY:
                color = VkKeyboardColor.PRIMARY
            elif btn.style == ButtonStyle.DANGER:
                color = VkKeyboardColor.NEGATIVE
            elif btn.style == ButtonStyle.SUCCESS:
                color = VkKeyboardColor.POSITIVE
            vk_kb.add_button(btn.text, color=color, payload={"callback": btn.callback_data})
        vk_kb.add_line()
    return vk_kb.get_keyboard()


def _convert_inline_to_discord(kb: InlineKeyboard):
    import discord
    view = discord.ui.View(timeout=None)
    for row in kb.rows:
        for btn in row:
            style = discord.ButtonStyle.secondary
            if btn.style == ButtonStyle.PRIMARY:
                style = discord.ButtonStyle.primary
            elif btn.style == ButtonStyle.SUCCESS:
                style = discord.ButtonStyle.success
            elif btn.style == ButtonStyle.DANGER:
                style = discord.ButtonStyle.danger
            button = discord.ui.Button(
                label=btn.text,
                style=style,
                custom_id=btn.callback_data,
                url=btn.url
            )
            view.add_item(button)
    return view



async def send_with_keyboard(ctx, text: str, 
                             inline_keyboard: Optional[InlineKeyboard] = None,
                             reply_keyboard: Optional[ReplyKeyboard] = None,
                             **kwargs):
    platform = ctx.platform
    adapter = ctx.adapter

    if platform == Platform.TELEGRAM:
        markup = None
        if reply_keyboard and not reply_keyboard.is_empty():
            markup = _convert_reply_to_telegram(reply_keyboard)
        elif inline_keyboard and not inline_keyboard.is_empty():
            markup = _convert_inline_to_telegram(inline_keyboard)
        return await adapter.send_message(ctx.chat.id, text, reply_markup=markup, **kwargs)

    elif platform == Platform.VK:
        keyboard = None
        if inline_keyboard and not inline_keyboard.is_empty():
            keyboard = _convert_inline_to_vk(inline_keyboard)
        return await adapter.send_message(ctx.chat.id, text, keyboard=keyboard, **kwargs)

    elif platform == Platform.DISCORD:
        view = None
        if inline_keyboard and not inline_keyboard.is_empty():
            view = _convert_inline_to_discord(inline_keyboard)
        return await adapter.send_message(ctx.chat.id, text, view=view, **kwargs)

    else:
        return await adapter.send_message(ctx.chat.id, text, **kwargs)
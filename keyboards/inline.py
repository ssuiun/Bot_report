from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import FINANCE_CATEGORIES


def finance_categories_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in FINANCE_CATEGORIES:
        builder.button(text=cat, callback_data=f"fin_cat:{cat}")
    builder.adjust(2)
    return builder.as_markup()


def employees_kb(employees: list[dict], prefix: str) -> InlineKeyboardMarkup:
    """employees: список dict с ключами id, full_name. prefix — префикс callback_data."""
    builder = InlineKeyboardBuilder()
    for emp in employees:
        builder.button(text=emp["full_name"], callback_data=f"{prefix}:{emp['id']}")
    builder.button(text="Указать вручную (ФИО)", callback_data=f"{prefix}:manual")
    builder.adjust(1)
    return builder.as_markup()


def open_acts_kb(acts: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for act in acts:
        label = f"{act['item']} → {act['to_user']}"
        builder.button(text=label[:60], callback_data=f"act_return:{act['id']}")
    builder.adjust(1)
    return builder.as_markup()


def confirm_return_kb(act_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отметить возвращённым", callback_data=f"act_confirm_return:{act_id}")
    return builder.as_markup()


def remove_user_kb(employees: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for emp in employees:
        builder.button(text=f"{emp['full_name']} ({emp['position']})", callback_data=f"del_user:{emp['telegram_id']}")
    builder.adjust(1)
    return builder.as_markup()


def skip_photo_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Без фото", callback_data="fin_skip_photo")
    return builder.as_markup()

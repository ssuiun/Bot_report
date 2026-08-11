from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import SUPER_ADMIN_IDS
from db import database as db
from keyboards.reply import main_menu, BTN_BACK, BTN_CANCEL

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_tg_id = message.from_user.id
    user = await db.get_user(user_tg_id)

    # Если пользователь из SUPER_ADMIN_IDS — автоматически создаём/восстанавливаем его
    if user_tg_id in SUPER_ADMIN_IDS:
        if user is None:
            # Первый вход супер-админа — создаём запись
            full_name = message.from_user.full_name or "Администратор"
            await db.add_user(user_tg_id, full_name, "Руководство", "", role="admin")
            user = await db.get_user(user_tg_id)
        elif user["role"] != "admin" or not user["active"]:
            # Роль слетела (например, после сброса БД на Railway) — восстанавливаем
            await db.restore_super_admin(user_tg_id)
            user = await db.get_user(user_tg_id)

    if user is None or not user["active"]:
        await message.answer(
            "👋 Вы пока не зарегистрированы в системе.\n\n"
            f"Ваш Telegram ID: <code>{user_tg_id}</code>\n\n"
            "Передайте этот ID администратору, чтобы он добавил вас через команду "
            "/add_user — после этого бот станет доступен.",
        )
        return

    await message.answer(
        f"👋 Здравствуйте, {user['full_name']}!\nВыберите раздел в меню ниже:",
        reply_markup=main_menu(user["role"]),
    )


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    role = user["role"] if user else "employee"
    await message.answer("Действие отменено.", reply_markup=main_menu(role))


@router.message(F.text == BTN_BACK)
async def back_to_main(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user or not user["active"]:
        await message.answer("Вы не зарегистрированы. Наберите /start.")
        return
    await message.answer("Главное меню:", reply_markup=main_menu(user["role"]))


async def require_registered_user(message: Message) -> dict | None:
    """Утилита: возвращает пользователя из БД или отправляет предупреждение и None."""
    user = await db.get_user(message.from_user.id)
    if not user or not user["active"]:
        await message.answer("⛔ Доступ закрыт. Наберите /start и передайте ваш ID администратору.")
        return None
    return user

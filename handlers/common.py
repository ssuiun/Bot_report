from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db import database as db
from keyboards.reply import main_menu, BTN_BACK, BTN_CANCEL

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if user is None or not user["active"]:
        await message.answer(
            "👋 Вы пока не зарегистрированы в системе.\n\n"
            f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n\n"
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

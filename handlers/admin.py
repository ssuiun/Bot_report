from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db import database as db
from services import sheets
from states.forms import AddUserForm
from keyboards.reply import admin_menu, cancel_menu, main_menu, BTN_ADMIN, BTN_ADD_USER, BTN_DEL_USER, BTN_SUMMARY
from keyboards.inline import remove_user_kb

router = Router()


async def _require_admin(message: Message) -> dict | None:
    user = await db.get_user(message.from_user.id)
    if not user or not user["active"] or user["role"] != "admin":
        await message.answer("⛔ Эта функция доступна только администраторам.")
        return None
    return user


@router.message(F.text == BTN_ADMIN)
async def open_admin_menu(message: Message, state: FSMContext) -> None:
    if not await _require_admin(message):
        return
    await state.clear()
    await message.answer("Админ-панель:", reply_markup=admin_menu())


# ---------- Добавление сотрудника ----------

@router.message(Command("add_user"))
@router.message(F.text == BTN_ADD_USER)
async def start_add_user(message: Message, state: FSMContext) -> None:
    if not await _require_admin(message):
        return
    await state.set_state(AddUserForm.full_name)
    await message.answer("Введите ФИО нового сотрудника:", reply_markup=cancel_menu())


@router.message(AddUserForm.full_name)
async def add_user_name(message: Message, state: FSMContext) -> None:
    await state.update_data(full_name=message.text)
    await state.set_state(AddUserForm.position)
    await message.answer("Введите должность:", reply_markup=cancel_menu())


@router.message(AddUserForm.position)
async def add_user_position(message: Message, state: FSMContext) -> None:
    await state.update_data(position=message.text)
    await state.set_state(AddUserForm.phone)
    await message.answer("Введите телефон (или «-», если нет):", reply_markup=cancel_menu())


@router.message(AddUserForm.phone)
async def add_user_phone(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text)
    await state.set_state(AddUserForm.telegram_id)
    await message.answer(
        "Введите Telegram ID сотрудника.\n\n"
        "ℹ️ Узнать ID можно так: попросите сотрудника написать боту /start — "
        "бот покажет его ID, если он ещё не зарегистрирован.",
        reply_markup=cancel_menu(),
    )


@router.message(AddUserForm.telegram_id)
async def add_user_finish(message: Message, state: FSMContext, bot) -> None:
    if not message.text.strip().lstrip("-").isdigit():
        await message.answer("Telegram ID должен быть числом. Попробуйте ещё раз:")
        return
    telegram_id = int(message.text.strip())
    data = await state.get_data()
    await state.clear()

    await db.add_user(telegram_id, data["full_name"], data["position"], data["phone"], role="employee")

    admin = await db.get_user(message.from_user.id)
    await message.answer(
        f"✅ Сотрудник {data['full_name']} добавлен.",
        reply_markup=admin_menu(),
    )

    try:
        await bot.send_message(
            telegram_id,
            f"👋 Здравствуйте, {data['full_name']}! Вас добавили в корпоративного бота "
            f"«{admin['full_name']}». Наберите /start, чтобы открыть меню.",
        )
    except Exception:
        await message.answer(
            "⚠️ Не удалось отправить приглашение автоматически — сотрудник ещё ни разу "
            "не писал боту. Попросите его самостоятельно нажать /start."
        )


# ---------- Удаление сотрудника ----------

@router.message(F.text == BTN_DEL_USER)
async def start_remove_user(message: Message) -> None:
    if not await _require_admin(message):
        return
    employees = [e for e in await db.list_active_users() if e["telegram_id"] != message.from_user.id]
    if not employees:
        await message.answer("Нет сотрудников для удаления.", reply_markup=admin_menu())
        return
    await message.answer("Выберите сотрудника для удаления доступа:", reply_markup=remove_user_kb(employees))


@router.callback_query(F.data.startswith("del_user:"))
async def confirm_remove_user(callback: CallbackQuery) -> None:
    telegram_id = int(callback.data.split(":", 1)[1])
    admin = await db.get_user(callback.from_user.id)
    if not admin or admin["role"] != "admin":
        await callback.answer("Недостаточно прав.", show_alert=True)
        return
    user = await db.get_user(telegram_id)
    await db.deactivate_user(telegram_id)
    await callback.message.edit_text(f"🗑 Доступ сотрудника «{user['full_name']}» заблокирован.")
    await callback.answer()


# ---------- Общая сводка ----------

@router.message(F.text == BTN_SUMMARY)
async def summary(message: Message) -> None:
    if not await _require_admin(message):
        return
    url = sheets.get_spreadsheet_url()
    await message.answer(
        f"📊 Общая сводка (все данные в реальном времени):\n{url}",
        reply_markup=admin_menu(),
    )

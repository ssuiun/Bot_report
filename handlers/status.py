from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from db import database as db
from services import sheets
from states.forms import AwayForm
from keyboards.reply import (
    status_menu, cancel_menu, main_menu,
    BTN_STATUS, BTN_LEAVE, BTN_RETURN, BTN_WHO_IN_OFFICE, BTN_MY_PROFILE,
)
from utils.formatting import now_date, now_time, away_card, return_card, who_is_in_office, profile_card
from utils.notify import notify
from handlers.common import require_registered_user

router = Router()


@router.message(F.text == BTN_STATUS)
async def open_status_menu(message: Message, state: FSMContext) -> None:
    if not await require_registered_user(message):
        return
    await state.clear()
    await message.answer("Раздел «Статус». Выберите действие:", reply_markup=status_menu())


# ---------- Ухожу (цепочка вопросов) ----------

@router.message(F.text == BTN_LEAVE)
async def start_leave(message: Message, state: FSMContext) -> None:
    user = await require_registered_user(message)
    if not user:
        return
    if user["status"] == "away":
        await message.answer(
            "Вы уже отмечены как отсутствующий. Нажмите «🟢 Я вернулся», если хотите сменить статус.",
            reply_markup=status_menu(),
        )
        return
    await state.set_state(AwayForm.destination)
    await message.answer("Куда уходите?", reply_markup=cancel_menu())


@router.message(AwayForm.destination)
async def leave_destination(message: Message, state: FSMContext) -> None:
    await state.update_data(destination=message.text)
    await state.set_state(AwayForm.reason)
    await message.answer("Цель / зачем?", reply_markup=cancel_menu())


@router.message(AwayForm.reason)
async def leave_reason(message: Message, state: FSMContext) -> None:
    await state.update_data(reason=message.text)
    await state.set_state(AwayForm.return_time)
    await message.answer("Примерное время возвращения? (например: 14:30 или «через 2 часа»)",
                          reply_markup=cancel_menu())


@router.message(AwayForm.return_time)
async def leave_return_time(message: Message, state: FSMContext, bot) -> None:
    try:
        data = await state.get_data()
        destination = data.get("destination", "Не указано")
        reason = data.get("reason", "Не указано")
        return_time = message.text
        await state.clear()

        user = await require_registered_user(message)
        if not user:
            return
        since = now_time()

        # 1. Сначала локальная БД — быстро и надёжно
        await db.set_status_away(message.from_user.id, destination, reason, return_time, since)
        movement_id = await db.add_movement(user["id"], 0, since, destination, reason, return_time)

        # 2. Сразу отвечаем пользователю (не ждём Google Sheets)
        card = away_card(user["full_name"], destination, reason, return_time)
        await message.answer(card, reply_markup=status_menu())

        # 3. Google Sheets — в фоне
        try:
            row_number = await sheets.add_status_row(
                date=now_date(), time_left=since, employee=user["full_name"],
                destination=destination, reason=reason, expected_return=return_time,
            )
            await db.set_movement_sheet_row(movement_id, row_number)
        except Exception as e:
            import logging; logging.warning("Sheets недоступен (ухожу): %s", e)

        await notify(bot, card, actor_telegram_id=message.from_user.id)
    except Exception as e:
        import logging
        logging.error("Ошибка в leave_return_time: %s", e, exc_info=True)
        await message.answer("Произошла ошибка при сохранении статуса. Попробуйте ещё раз.", reply_markup=status_menu())


# ---------- Я вернулся ----------

@router.message(F.text == BTN_RETURN)
async def mark_return(message: Message, bot) -> None:
    user = await require_registered_user(message)
    if not user:
        return
    if user["status"] != "away":
        await message.answer("Вы и так отмечены как «в офисе».", reply_markup=status_menu())
        return

    movement = await db.get_open_movement(user["id"])
    actual_time = now_time()

    if movement:
        await db.close_movement(movement["id"], actual_time)

    plan_time = user["away_expected_return"]
    await db.set_status_in_office(message.from_user.id)

    card = return_card(user["full_name"], actual_time, plan_time)
    await message.answer(card, reply_markup=status_menu())

    if movement and movement["sheet_row"]:
        try:
            await sheets.update_status_return(movement["sheet_row"], actual_time)
        except Exception as e:
            import logging; logging.warning("Sheets недоступен (вернулся): %s", e)

    await notify(bot, card, actor_telegram_id=message.from_user.id)


# ---------- Кто в офисе ----------

@router.message(F.text == BTN_WHO_IN_OFFICE)
async def who_in_office(message: Message) -> None:
    if not await require_registered_user(message):
        return
    users = await db.list_active_users()
    await message.answer(who_is_in_office(users), reply_markup=status_menu())


# ---------- Мой профиль ----------

@router.message(F.text == BTN_MY_PROFILE)
async def my_profile(message: Message) -> None:
    user = await require_registered_user(message)
    if not user:
        return
    movements = await db.list_movements(user["id"], limit=5)
    await message.answer(profile_card(user, movements), reply_markup=status_menu())

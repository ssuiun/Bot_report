from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db import database as db
from services import sheets
from states.forms import ActForm
from keyboards.reply import acts_menu, cancel_menu, skip_or_cancel_menu, BTN_ACTS, BTN_NEW_ACT, BTN_MY_ACTS
from keyboards.inline import employees_kb, open_acts_kb
from utils.formatting import now_date, now_time, act_card
from utils.notify import notify
from handlers.common import require_registered_user

router = Router()


@router.message(F.text == BTN_ACTS)
async def open_acts_menu(message: Message, state: FSMContext) -> None:
    if not await require_registered_user(message):
        return
    await state.clear()
    await message.answer("Раздел «Акты». Выберите действие:", reply_markup=acts_menu())


# ---------- Передать документ ----------

@router.message(F.text == BTN_NEW_ACT)
async def start_act(message: Message, state: FSMContext) -> None:
    if not await require_registered_user(message):
        return
    await state.set_state(ActForm.item)
    await message.answer("Что передаётся? (название документа/товара)", reply_markup=cancel_menu())


@router.message(ActForm.item)
async def act_item(message: Message, state: FSMContext) -> None:
    await state.update_data(item=message.text)
    await state.set_state(ActForm.whom)
    employees = [e for e in await db.list_active_users() if e["telegram_id"] != message.from_user.id]
    await message.answer(
        "Кому передаётся? Выберите из списка или укажите вручную:",
        reply_markup=cancel_menu(),
    )
    await message.answer("Список сотрудников:", reply_markup=employees_kb(employees, "act_to"))


@router.callback_query(ActForm.whom, F.data.startswith("act_to:"))
async def act_whom_selected(callback: CallbackQuery, state: FSMContext) -> None:
    value = callback.data.split(":", 1)[1]
    if value == "manual":
        await callback.message.answer("Введите ФИО получателя текстом:")
        await callback.answer()
        return
    emp = await db.get_user_by_id(int(value))
    await state.update_data(whom=emp["full_name"] if emp else "Неизвестно")
    await state.set_state(ActForm.due_date)
    await callback.message.answer("Срок возврата? (например: 10.08.2026)", reply_markup=cancel_menu())
    await callback.answer()


@router.message(ActForm.whom)
async def act_whom_manual(message: Message, state: FSMContext) -> None:
    await state.update_data(whom=message.text)
    await state.set_state(ActForm.due_date)
    await message.answer("Срок возврата? (например: 10.08.2026)", reply_markup=cancel_menu())


@router.message(ActForm.due_date)
async def act_due_date(message: Message, state: FSMContext) -> None:
    await state.update_data(due_date=message.text)
    await state.set_state(ActForm.comment)
    await message.answer("Комментарий (необязательно):", reply_markup=skip_or_cancel_menu())


@router.message(ActForm.comment)
async def act_comment(message: Message, state: FSMContext, bot) -> None:
    comment = "" if message.text == "⏭ Пропустить" else message.text
    data = await state.get_data()
    await state.clear()

    user = await db.get_user(message.from_user.id)

    # Порядковый номер для колонки "№ п/п" — количество открытых+закрытых актов + 1
    open_acts = await db.list_open_acts(user["id"])
    number = len(open_acts) + 1

    act_id = await db.add_act(0, user["id"], data["whom"], data["item"], data["due_date"], comment)

    card = act_card(data["item"], user["full_name"], data["whom"], data["due_date"], comment)
    await message.answer(card, reply_markup=acts_menu())

    # Google Sheets — в фоне; запоминаем номер строки в БД, иначе "Мои акты →
    # отметить возвращённым" не найдёт, какую строку обновлять в таблице.
    try:
        row_number = await sheets.add_act_row(
            number=number, date=now_date(), time_=now_time(), item=data["item"],
            from_user=user["full_name"], to_user=data["whom"], due_date=data["due_date"],
        )
        await db.set_act_sheet_row(act_id, row_number)
    except Exception as e:
        import logging; logging.warning("Sheets недоступен (акт): %s", e)

    await notify(bot, card, actor_telegram_id=message.from_user.id)


# ---------- Мои акты (не возвращены) ----------

@router.message(F.text == BTN_MY_ACTS)
async def my_open_acts(message: Message) -> None:
    user = await require_registered_user(message)
    if not user:
        return
    acts = await db.list_open_acts(user["id"])
    if not acts:
        await message.answer("У вас нет открытых актов (всё возвращено).", reply_markup=acts_menu())
        return
    await message.answer(
        "Открытые акты — нажмите, чтобы отметить возврат:",
        reply_markup=open_acts_kb(acts),
    )


@router.callback_query(F.data.startswith("act_return:"))
async def act_return_prompt(callback: CallbackQuery) -> None:
    act_id = int(callback.data.split(":", 1)[1])
    act = await db.get_act(act_id)
    if not act or act["status"] == "returned":
        await callback.answer("Уже возвращено или не найдено.", show_alert=True)
        return
    await db.mark_act_returned(act_id)
    try:
        await callback.message.edit_text(f"✅ «{act['item']}» отмечено как возвращённое.")
    except Exception:
        await callback.message.answer(f"✅ «{act['item']}» отмечено как возвращённое.")
    await callback.answer()
    if act["sheet_row"]:
        try:
            await sheets.update_act_return(act["sheet_row"])
        except Exception as e:
            import logging; logging.warning("Sheets недоступен (возврат акта): %s", e)

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from db import database as db
from services import sheets, drive
from states.forms import FinanceForm
from keyboards.reply import finance_menu, cancel_menu, BTN_FINANCE, BTN_NEW_EXPENSE, BTN_CANCEL
from keyboards.inline import finance_categories_kb, skip_photo_kb
from utils.formatting import now_date, now_time, finance_card
from utils.notify import notify, notify_photo
from handlers.common import require_registered_user
from config import LOG_CHAT_ID

router = Router()


@router.message(F.text == BTN_FINANCE)
async def open_finance_menu(message: Message, state: FSMContext) -> None:
    if not await require_registered_user(message):
        return
    await state.clear()
    await message.answer("Раздел «Финансы». Выберите действие:", reply_markup=finance_menu())


@router.message(F.text == BTN_NEW_EXPENSE)
async def start_expense(message: Message, state: FSMContext) -> None:
    if not await require_registered_user(message):
        return
    await state.set_state(FinanceForm.category)
    await message.answer("На что потрачено? Выберите категорию:", reply_markup=finance_categories_kb())


@router.callback_query(FinanceForm.category, F.data.startswith("fin_cat:"))
async def expense_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":", 1)[1]
    await state.update_data(category=category)
    await state.set_state(FinanceForm.amount)
    await callback.message.answer(f"Категория: {category}\n\nВведите сумму расхода (число, ₽):",
                                   reply_markup=cancel_menu())
    await callback.answer()


@router.message(FinanceForm.amount)
async def expense_amount(message: Message, state: FSMContext) -> None:
    text = message.text.replace(",", ".").replace(" ", "")
    try:
        amount = float(text)
    except ValueError:
        await message.answer("Пожалуйста, введите сумму числом, например: 350")
        return
    await state.update_data(amount=amount)
    await state.set_state(FinanceForm.description)
    await message.answer(
        "Подробное описание (куда ездил, что купил, номер заказа и т.д.):",
        reply_markup=cancel_menu(),
    )


@router.message(FinanceForm.description)
async def expense_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text)
    await state.set_state(FinanceForm.photo)
    await message.answer(
        "Приложите фото чека (или нажмите «Без фото»):",
        reply_markup=skip_photo_kb(),
    )


@router.message(FinanceForm.photo, F.photo)
async def expense_photo(message: Message, state: FSMContext, bot) -> None:
    receipt_cell_value = ""
    photo = message.photo[-1]

    # 1. Основной путь — грузим фото в Google Drive и вставляем сам файл
    # изображения в ячейку таблицы через формулу =IMAGE(...), а не просто ссылку.
    try:
        tg_file = await bot.get_file(photo.file_id)
        file_bytes_io = await bot.download_file(tg_file.file_path)
        filename = f"receipt_{message.from_user.id}_{message.date.strftime('%Y%m%d_%H%M%S')}.jpg"
        direct_url = await drive.upload_photo(file_bytes_io.read(), filename)
        receipt_cell_value = f'=IMAGE("{direct_url}")'
    except Exception as e:
        import logging
        logging.warning("Google Drive недоступен (чек): %s", e)

        if LOG_CHAT_ID:
            try:
                forwarded = await bot.forward_message(LOG_CHAT_ID, message.chat.id, message.message_id)
                receipt_cell_value = f"https://t.me/c/{str(LOG_CHAT_ID).replace('-100', '')}/{forwarded.message_id}"
            except Exception:
                receipt_cell_value = f"file_id:{photo.file_id}"
        else:
            receipt_cell_value = f"file_id:{photo.file_id}"

    await _save_expense(message, state, receipt_cell_value, photo_file_id=photo.file_id, bot=bot)


@router.callback_query(FinanceForm.photo, F.data == "fin_skip_photo")
async def expense_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _save_expense(callback.message, state, "", user_override=callback.from_user.id, bot=callback.bot)


@router.message(FinanceForm.photo)
async def expense_photo_reminder(message: Message) -> None:
    await message.answer(
        "Пришлите фото чека или нажмите «⏭ Без фото» под предыдущим сообщением.",
        reply_markup=skip_photo_kb(),
    )


async def _save_expense(
    message: Message,
    state: FSMContext,
    receipt_link: str,
    user_override: int | None = None,
    photo_file_id: str | None = None,
    bot=None
) -> None:
    data = await state.get_data()
    telegram_id = user_override or message.from_user.id
    user = await db.get_user(telegram_id)
    await state.clear()

    card = finance_card(user["full_name"], data["category"], str(data["amount"]), data["description"])
    
    if photo_file_id:
        await message.answer_photo(photo_file_id, caption=card, reply_markup=finance_menu())
        if bot:
            await notify_photo(bot, photo_file_id, card, actor_telegram_id=telegram_id)
    else:
        await message.answer(card, reply_markup=finance_menu())
        if bot:
            await notify(bot, card, actor_telegram_id=telegram_id)

    try:
        await sheets.add_finance_row(
            date=now_date(), time_=now_time(), employee=user["full_name"],
            category=data["category"], amount=str(data["amount"]),
            description=data["description"], receipt_link=receipt_link,
        )
    except Exception as e:
        import logging; logging.warning("Sheets недоступен (финансы): %s", e)

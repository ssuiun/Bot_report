import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from db.database import init_db
from services.sheets import ensure_sheets

from handlers import common, status, acts, finance, admin


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    await init_db()
    try:
        await ensure_sheets()
        logging.info("Google Sheets подключён успешно")
    except Exception as e:
        logging.warning(
            "Google Sheets недоступен — бот работает без него. "
            "Проверьте credentials.json, GOOGLE_SHEET_ID и права доступа "
            "(сервисный аккаунт должен быть Редактором таблицы). Ошибка: %s", e
        )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: более специфичные роутеры (с FSM-состояниями) — раньше общих.
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(status.router)
    dp.include_router(acts.router)
    dp.include_router(finance.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

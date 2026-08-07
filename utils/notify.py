"""
Единая функция дублирования уведомлений (смена статуса, новые акты) в лог-чат
и/или админам, БЕЗ дублирования одного и того же сообщения одному и тому же chat_id.

Почему это отдельный модуль: раньше похожая логика была продублирована в
handlers/status.py и handlers/acts.py по отдельности, с разными условиями —
из-за этого сообщения уходили по 2-3 раза одному и тому же человеку, если он
одновременно автор действия, админ и владелец LOG_CHAT_ID.

Правило: если LOG_CHAT_ID задан — уведомление уходит ТОЛЬКО туда (один раз).
Если LOG_CHAT_ID не задан — уведомление уходит каждому админу (каждому — не более одного раза).
Автору действия (actor_telegram_id) уведомление никогда не дублируется, так как
он уже получил карточку как прямой ответ на своё сообщение.
"""
from db import database as db
from config import LOG_CHAT_ID


async def notify(bot, text: str, actor_telegram_id: int | None = None) -> None:
    targets: set[int] = set()

    if LOG_CHAT_ID:
        targets.add(LOG_CHAT_ID)
    else:
        for admin in await db.list_all_admins():
            targets.add(admin["telegram_id"])

    if actor_telegram_id is not None:
        if not (LOG_CHAT_ID and actor_telegram_id == LOG_CHAT_ID):
            targets.discard(actor_telegram_id)

    for chat_id in targets:
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            pass


async def notify_photo(bot, photo_file_id: str, caption: str, actor_telegram_id: int | None = None) -> None:
    targets: set[int] = set()

    if LOG_CHAT_ID:
        targets.add(LOG_CHAT_ID)
    else:
        for admin in await db.list_all_admins():
            targets.add(admin["telegram_id"])

    if actor_telegram_id is not None:
        if not (LOG_CHAT_ID and actor_telegram_id == LOG_CHAT_ID):
            targets.discard(actor_telegram_id)

    for chat_id in targets:
        try:
            await bot.send_photo(chat_id, photo=photo_file_id, caption=caption)
        except Exception:
            try:
                await bot.send_message(chat_id, caption)
            except Exception:
                pass

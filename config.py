"""
Конфигурация бота. Все значения берутся из переменных окружения (.env).
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_id_list(raw: str) -> set[int]:
    ids = set()
    for chunk in (raw or "").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            ids.add(int(chunk))
    return ids


BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# ID администраторов, которых нужно создать автоматически при первом запуске,
# если их ещё нет в базе (чтобы всегда был хотя бы один админ).
SUPER_ADMIN_IDS: set[int] = _parse_id_list(os.getenv("SUPER_ADMIN_IDS", "6530698325,491929316,1207389040"))

# Чат/канал для дублирования уведомлений (смена статуса, новые акты, чеки).
LOG_CHAT_ID: int | None = int(os.getenv("LOG_CHAT_ID", "6530698325")) if os.getenv("LOG_CHAT_ID", "6530698325") else None

GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE: str = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# ID папки в Google Drive, куда будут заливаться фото чеков (необязательно —
# если не задано, файлы будут загружаться в корень диска сервисного аккаунта).
# Взять из URL папки: https://drive.google.com/drive/folders/ЭТА_ЧАСТЬ
GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

DB_PATH: str = os.getenv("DB_PATH", "hr_bot.db")

# Названия листов в таблице Google Sheets
SHEET_STATUS = "Лист1"
SHEET_ACTS = "Лист2"
SHEET_FINANCE = "Лист3"

FINANCE_CATEGORIES = ["Такси", "Курьер", "Канцелярия", "Хознужды", "Прочее"]

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните значения."
    )

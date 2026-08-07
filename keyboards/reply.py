from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- Тексты кнопок (используются и как триггеры в handlers через F.text==) ---
BTN_STATUS = "📍 Статус"
BTN_ACTS = "📄 Акты"
BTN_FINANCE = "💰 Финансы"
BTN_ADMIN = "⚙️ Админ-панель"

BTN_LEAVE = "🔴 Ухожу"
BTN_RETURN = "🟢 Я вернулся"
BTN_WHO_IN_OFFICE = "👥 Кто в офисе"
BTN_MY_PROFILE = "🙋 Мой профиль"
BTN_BACK = "⬅️ Главное меню"

BTN_NEW_ACT = "➕ Передать документ"
BTN_MY_ACTS = "📋 Мои акты (не возвращены)"

BTN_NEW_EXPENSE = "➕ Добавить расход"

BTN_ADD_USER = "➕ Добавить сотрудника"
BTN_DEL_USER = "🗑 Удалить сотрудника"
BTN_SUMMARY = "📊 Общая сводка"

BTN_CANCEL = "❌ Отмена"


def main_menu(role: str) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=BTN_STATUS)],
        [KeyboardButton(text=BTN_ACTS), KeyboardButton(text=BTN_FINANCE)],
    ]
    if role == "admin":
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def status_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_LEAVE), KeyboardButton(text=BTN_RETURN)],
            [KeyboardButton(text=BTN_WHO_IN_OFFICE), KeyboardButton(text=BTN_MY_PROFILE)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def acts_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW_ACT)],
            [KeyboardButton(text=BTN_MY_ACTS)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def finance_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW_EXPENSE)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADD_USER), KeyboardButton(text=BTN_DEL_USER)],
            [KeyboardButton(text=BTN_SUMMARY)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def skip_or_cancel_menu(skip_text: str = "⏭ Пропустить") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=skip_text)], [KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )

"""
Обёртка над gspread для записи данных в Google Sheets в реальном времени.

Все обращения к gspread — синхронные (блокирующие), поэтому каждый вызов
выполняется в отдельном потоке через asyncio.to_thread, чтобы не блокировать
event loop бота.
"""
import asyncio
import re
import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE, GOOGLE_CREDENTIALS_JSON, SHEET_STATUS, SHEET_ACTS, SHEET_FINANCE
import json

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_HEADERS = {
    SHEET_STATUS: ["Дата", "Время ухода", "Сотрудник", "Куда ушел", "Зачем",
                   "Время возврата (план)", "Время возврата (факт)", "Статус"],
    SHEET_ACTS: ["№ п/п", "Дата передачи", "Время", "Что передано", "От кого",
                 "Кому", "Срок возврата", "Статус"],
    SHEET_FINANCE: ["Дата", "Время", "Сотрудник", "Категория", "Сумма (₽)",
                    "Описание/Комментарий", "Ссылка на чек/фото"],
}

# Колонка "Статус" (1-indexed) и правила раскраски по значению для каждого листа.
# Цвета — RGB от 0 до 1, как того требует Sheets API.
_RED = {"red": 0.96, "green": 0.80, "blue": 0.80}
_GREEN = {"red": 0.80, "green": 0.94, "blue": 0.80}

_STATUS_COLOR_RULES = {
    SHEET_STATUS: (8, [("Отсутствует", _RED), ("Вернулся", _GREEN)]),
    SHEET_ACTS: (8, [("Не возвращен", _RED), ("Возвращен", _GREEN)]),
}

_client = None
_spreadsheet = None


def _get_spreadsheet():
    global _client, _spreadsheet
    if _spreadsheet is None:
        if GOOGLE_CREDENTIALS_JSON:
            creds_info = json.loads(GOOGLE_CREDENTIALS_JSON)
            creds = Credentials.from_service_account_info(creds_info, scopes=_SCOPES)
        else:
            creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=_SCOPES)
        _client = gspread.authorize(creds)
        _spreadsheet = _client.open_by_key(GOOGLE_SHEET_ID)
    return _spreadsheet


def _get_or_create_worksheet_sync(name: str):
    ss = _get_spreadsheet()
    try:
        ws = ss.worksheet(name)
    except gspread.WorksheetNotFound:
        try:
            ws = ss.add_worksheet(title=name, rows=1000, cols=20)
        except Exception as exc:
            raise RuntimeError(f"Не удалось создать лист «{name}» в таблице: {exc}") from exc
    # Проставляем заголовки, если лист пуст (требует права Редактора)
    if not ws.row_values(1):
        try:
            ws.append_row(_HEADERS[name])
        except gspread.exceptions.APIError:
            pass
    return ws


def _sheet_has_conditional_formats(sheet_id: int) -> bool:
    meta = _get_spreadsheet().fetch_sheet_metadata()
    for sheet in meta.get("sheets", []):
        if sheet["properties"]["sheetId"] == sheet_id:
            return bool(sheet.get("conditionalFormats"))
    return False


def _apply_status_coloring_sync(name: str, ws) -> None:
    """Красит колонку «Статус» в зависимости от значения ячейки (зелёный/красный).

    Правило добавляется только один раз — если у листа уже есть условное
    форматирование, повторный вызов при следующем старте бота ничего не делает
    (иначе правила накапливались бы бесконечно при каждом перезапуске).
    """
    if name not in _STATUS_COLOR_RULES:
        return
    if _sheet_has_conditional_formats(ws.id):
        return

    col_index, rules = _STATUS_COLOR_RULES[name]
    requests = []
    for value, color in rules:
        requests.append({
            "addConditionalFormatRule": {
                "rule": {
                    "ranges": [{
                        "sheetId": ws.id,
                        "startRowIndex": 1,  # пропускаем строку заголовка
                        "startColumnIndex": col_index - 1,
                        "endColumnIndex": col_index,
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "TEXT_EQ",
                            "values": [{"userEnteredValue": value}],
                        },
                        "format": {"backgroundColor": color},
                    },
                },
                "index": 0,
            }
        })
    try:
        ws.spreadsheet.batch_update({"requests": requests})
    except gspread.exceptions.APIError:
        pass  # нет прав на форматирование — не критично, данные всё равно запишутся


def _ensure_sheets_sync():
    for name in (SHEET_STATUS, SHEET_ACTS, SHEET_FINANCE):
        ws = _get_or_create_worksheet_sync(name)
        _apply_status_coloring_sync(name, ws)


async def ensure_sheets() -> None:
    """Вызывается один раз при старте бота — создаёт листы с нужными названиями,
    заголовками и цветным форматированием колонки «Статус»."""
    await asyncio.to_thread(_ensure_sheets_sync)


def _row_number_from_append_result(ws, result) -> int:
    """gspread возвращает сырой ответ Sheets API на append_row; из него можно
    получить точный номер добавленной строки через updatedRange (например,
    "'Лист1'!A12:H12" → 12). Раньше здесь ошибочно использовался ws.row_count,
    который возвращает общее число строк в листе (обычно 1000), а не номер
    строки с данными — из-за этого статусы обновлялись не в ту строку."""
    try:
        updated_range = result["updates"]["updatedRange"]
        cell_ref = updated_range.split("!")[-1].split(":")[0]  # "A12"
        match = re.search(r"\d+", cell_ref)
        if match:
            return int(match.group())
    except (KeyError, TypeError):
        pass
    # Резервный вариант, если формат ответа неожиданно изменится
    return len(ws.get_all_values())


def _append_row_sync(sheet_name: str, row: list) -> int:
    ws = _get_or_create_worksheet_sync(sheet_name)
    result = ws.append_row(row, value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
    return _row_number_from_append_result(ws, result)


def _update_cell_sync(sheet_name: str, row: int, col: int, value: str) -> None:
    ws = _get_or_create_worksheet_sync(sheet_name)
    ws.update_cell(row, col, value)


async def append_row(sheet_name: str, row: list) -> int:
    return await asyncio.to_thread(_append_row_sync, sheet_name, row)


async def update_cell(sheet_name: str, row: int, col: int, value: str) -> None:
    if row <= 0:
        return
    await asyncio.to_thread(_update_cell_sync, sheet_name, row, col, value)


def _txt(val: str | None) -> str:
    if not val:
        return ""
    val_str = str(val).strip()
    if val_str.startswith("=") or val_str.startswith("'"):
        return val_str
    return f"'{val_str}"


# ---------- Высокоуровневые функции для конкретных листов ----------

async def add_status_row(date: str, time_left: str, employee: str, destination: str,
                          reason: str, expected_return: str) -> int:
    row = [_txt(date), _txt(time_left), employee, destination, reason, _txt(expected_return), "", "Отсутствует"]
    return await append_row(SHEET_STATUS, row)


async def update_status_return(row_number: int, actual_return_time: str) -> None:
    # Колонка 7 — "Время возврата (факт)", колонка 8 — "Статус"
    await update_cell(SHEET_STATUS, row_number, 7, _txt(actual_return_time))
    await update_cell(SHEET_STATUS, row_number, 8, "Вернулся")


async def add_act_row(number: int, date: str, time_: str, item: str, from_user: str,
                       to_user: str, due_date: str) -> int:
    row = [number, _txt(date), _txt(time_), item, from_user, to_user, _txt(due_date), "Не возвращен"]
    return await append_row(SHEET_ACTS, row)


async def update_act_return(row_number: int) -> None:
    await update_cell(SHEET_ACTS, row_number, 8, "Возвращен")


async def add_finance_row(date: str, time_: str, employee: str, category: str,
                           amount: str, description: str, receipt_link: str) -> int:
    row = [_txt(date), _txt(time_), employee, category, amount, description, receipt_link]
    return await append_row(SHEET_FINANCE, row)


def get_spreadsheet_url() -> str:
    return f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit"

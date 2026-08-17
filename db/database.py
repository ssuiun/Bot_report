"""
Слой работы с базой данных (SQLite через aiosqlite).

Хранит:
- users       — сотрудники, их роль, права и текущий статус (в офисе/отошёл)
- movements   — история перемещений (для "Мой профиль" и обновления строк в Sheets)
- acts        — акты передачи документов/имущества (для отслеживания "возвращено/нет")
"""
import aiosqlite
from datetime import datetime
from utils.formatting import get_now

from config import DB_PATH, SUPER_ADMIN_IDS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    position TEXT,
    phone TEXT,
    role TEXT NOT NULL DEFAULT 'employee',   -- 'admin' | 'employee'
    active INTEGER NOT NULL DEFAULT 1,       -- 1 = доступ разрешён, 0 = заблокирован
    status TEXT NOT NULL DEFAULT 'in_office',-- 'in_office' | 'away'
    away_destination TEXT,
    away_reason TEXT,
    away_expected_return TEXT,
    away_since TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sheet_row INTEGER,
    left_at TEXT,
    destination TEXT,
    reason TEXT,
    expected_return TEXT,
    returned_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS acts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_row INTEGER,
    from_user_id INTEGER NOT NULL,
    to_user TEXT NOT NULL,
    item TEXT NOT NULL,
    due_date TEXT,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'not_returned', -- 'not_returned' | 'returned'
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_user_id) REFERENCES users (id)
);
"""


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()

        # Гарантируем, что SUPER_ADMIN_IDS всегда имеют роль 'admin' и активны,
        # даже после перезапуска контейнера (Railway сбрасывает эфемерную ФС).
        # Если пользователь уже зарегистрирован — только обновляем роль,
        # сохраняя его имя и данные профиля.
        for admin_id in SUPER_ADMIN_IDS:
            cur = await db.execute("SELECT id, full_name FROM users WHERE telegram_id = ?", (admin_id,))
            row = await cur.fetchone()
            if row is None:
                # Пользователь ещё не регистрировался — создаём запись-заглушку.
                # Бот предложит ему заполнить профиль при первом /start.
                await db.execute(
                    "INSERT INTO users (telegram_id, full_name, position, phone, role, active, created_at) "
                    "VALUES (?, ?, ?, ?, 'admin', 1, ?)",
                    (admin_id, "Администратор", "Руководство", "", get_now().isoformat()),
                )
            else:
                # Пользователь уже есть — восстанавливаем роль admin и активность,
                # не трогая имя, должность и телефон.
                await db.execute(
                    "UPDATE users SET role = 'admin', active = 1 WHERE telegram_id = ?",
                    (admin_id,),
                )
        await db.commit()


# ---------- Пользователи ----------

async def get_user(telegram_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def restore_super_admin(telegram_id: int) -> None:
    """Восстанавливает роль 'admin' и активность для супер-администратора."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET role = 'admin', active = 1 WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()


async def get_user_by_id(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_active_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE active = 1 ORDER BY full_name")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def list_all_admins() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE role = 'admin' AND active = 1")
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def add_user(telegram_id: int, full_name: str, position: str, phone: str, role: str = "employee") -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (telegram_id, full_name, position, phone, role, active, created_at) "
            "VALUES (?, ?, ?, ?, ?, 1, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET "
            "full_name=excluded.full_name, position=excluded.position, phone=excluded.phone, active=1",
            (telegram_id, full_name, position, phone, role, get_now().isoformat()),
        )
        await db.commit()


async def deactivate_user(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET active = 0 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


async def set_status_away(telegram_id: int, destination: str, reason: str, expected_return: str, since: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET status='away', away_destination=?, away_reason=?, "
            "away_expected_return=?, away_since=? WHERE telegram_id=?",
            (destination, reason, expected_return, since, telegram_id),
        )
        await db.commit()


async def set_status_in_office(telegram_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET status='in_office', away_destination=NULL, away_reason=NULL, "
            "away_expected_return=NULL, away_since=NULL WHERE telegram_id=?",
            (telegram_id,),
        )
        await db.commit()


# ---------- Перемещения (для истории и обновления строк в Sheets) ----------

async def add_movement(user_id: int, sheet_row: int, left_at: str, destination: str,
                        reason: str, expected_return: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO movements (user_id, sheet_row, left_at, destination, reason, expected_return) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, sheet_row, left_at, destination, reason, expected_return),
        )
        await db.commit()
        return cur.lastrowid


async def get_open_movement(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM movements WHERE user_id = ? AND returned_at IS NULL "
            "ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def close_movement(movement_id: int, returned_at: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE movements SET returned_at = ? WHERE id = ?", (returned_at, movement_id))
        await db.commit()


async def set_movement_sheet_row(movement_id: int, sheet_row: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE movements SET sheet_row = ? WHERE id = ?", (sheet_row, movement_id))
        await db.commit()


async def list_movements(user_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM movements WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---------- Акты ----------

async def add_act(sheet_row: int, from_user_id: int, to_user: str, item: str,
                   due_date: str, comment: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO acts (sheet_row, from_user_id, to_user, item, due_date, comment, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'not_returned', ?)",
            (sheet_row, from_user_id, to_user, item, due_date, comment, get_now().isoformat()),
        )
        await db.commit()
        return cur.lastrowid


async def list_open_acts(from_user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM acts WHERE from_user_id = ? AND status = 'not_returned' ORDER BY id DESC",
            (from_user_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_act(act_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM acts WHERE id = ?", (act_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_act_returned(act_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE acts SET status = 'returned' WHERE id = ?", (act_id,))
        await db.commit()


async def set_act_sheet_row(act_id: int, sheet_row: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE acts SET sheet_row = ? WHERE id = ?", (sheet_row, act_id))
        await db.commit()

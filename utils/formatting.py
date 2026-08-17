from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from config import TIMEZONE

def get_now() -> datetime:
    try:
        tz = ZoneInfo(TIMEZONE)
    except Exception:
        tz = None
    return datetime.now(tz)


def now_date() -> str:
    return get_now().strftime("%d.%m.%Y")


def now_time() -> str:
    return get_now().strftime("%H:%M")


def away_card(employee: str, destination: str, reason: str, return_time: str) -> str:
    return (
        "🔴 <b>Сотрудник отошёл</b>\n\n"
        f"👤 <b>Кто:</b> {employee}\n"
        f"📍 <b>Куда:</b> {destination}\n"
        f"🎯 <b>Зачем:</b> {reason}\n"
        f"🕐 <b>Ожидаемое возвращение:</b> {return_time}\n"
        f"🕐 <b>Время ухода:</b> {now_time()}"
    )


def return_card(employee: str, actual_time: str, plan_time: str | None = None) -> str:
    text = (
        "🟢 <b>Сотрудник вернулся</b>\n\n"
        f"👤 <b>Кто:</b> {employee}\n"
        f"🕐 <b>Время возврата:</b> {actual_time}"
    )
    if plan_time:
        text += f"\n📝 <b>План был:</b> {plan_time}"
    return text


def who_is_in_office(users: list[dict]) -> str:
    if not users:
        return "Список сотрудников пуст."
    lines = ["👥 <b>Кто сейчас в офисе</b>\n"]
    for u in users:
        if u["status"] == "away":
            lines.append(
                f"🔴 <b>{u['full_name']}</b> ({u['position']}) — {u['away_destination']}"
                f" ({u['away_reason']}), план: {u['away_expected_return']}"
            )
        else:
            lines.append(f"🟢 <b>{u['full_name']}</b> ({u['position']}) — в офисе")
    return "\n".join(lines)


def act_card(item: str, from_user: str, to_user: str, due_date: str, comment: str) -> str:
    text = (
        "📄 <b>Акт передачи создан</b>\n\n"
        f"📦 <b>Что передано:</b> {item}\n"
        f"👤 <b>От кого:</b> {from_user}\n"
        f"👥 <b>Кому:</b> {to_user}\n"
        f"📅 <b>Срок возврата:</b> {due_date}\n"
        f"🕐 <b>Дата/время:</b> {now_date()} {now_time()}"
    )
    if comment:
        text += f"\n💬 <b>Комментарий:</b> {comment}"
    return text


def finance_card(employee: str, category: str, amount: str, description: str) -> str:
    return (
        "💰 <b>Новый расход добавлен</b>\n\n"
        f"👤 <b>Сотрудник:</b> {employee}\n"
        f"🏷 <b>Категория:</b> {category}\n"
        f"💵 <b>Сумма:</b> {amount} ₽\n"
        f"💬 <b>Описание:</b> {description}"
    )


def profile_card(user: dict, movements: list[dict]) -> str:
    status_text = "🟢 В офисе" if user["status"] == "in_office" else (
        f"🔴 Отошёл: {user['away_destination']} ({user['away_reason']}), "
        f"план возврата {user['away_expected_return']}"
    )
    lines = [
        f"🙋 <b>Мой профиль</b>\n",
        f"👤 <b>{user['full_name']}</b>",
        f"💼 {user['position']}",
        f"📌 Статус: {status_text}",
        "\n<b>Последние перемещения:</b>",
    ]
    if not movements:
        lines.append("— пока нет записей —")
    for m in movements:
        ret = m["returned_at"] or "ещё не вернулся"
        lines.append(f"• {m['left_at']} → {m['destination']} ({m['reason']}), возврат: {ret}")
    return "\n".join(lines)

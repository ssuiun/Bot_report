from aiogram.fsm.state import State, StatesGroup


class AddUserForm(StatesGroup):
    full_name = State()
    position = State()
    phone = State()
    telegram_id = State()


class AwayForm(StatesGroup):
    destination = State()
    reason = State()
    return_time = State()


class ActForm(StatesGroup):
    item = State()
    whom = State()
    due_date = State()
    comment = State()


class FinanceForm(StatesGroup):
    category = State()
    amount = State()
    description = State()
    photo = State()

from aiogram.fsm.state import State, StatesGroup

class AddItem(StatesGroup):
    name = State()
    quantity = State()
    price = State()

class RemoveItem(StatesGroup):
    name = State()
    confirm = State()
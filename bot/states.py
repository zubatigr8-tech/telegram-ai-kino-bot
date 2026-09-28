from aiogram.fsm.state import State, StatesGroup


class AdminFlow(StatesGroup):
    add_channel_chatid = State()
    broadcast_text = State()

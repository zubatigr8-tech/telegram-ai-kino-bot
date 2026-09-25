from aiogram.fsm.state import State, StatesGroup


class AdminFlow(StatesGroup):
    add_movie_file = State()
    add_movie_code = State()
    add_movie_title = State()
    add_movie_description = State()
    delete_movie_code = State()
    add_channel_chatid = State()
    add_channel_username = State()
    add_channel_title = State()
    broadcast_text = State()

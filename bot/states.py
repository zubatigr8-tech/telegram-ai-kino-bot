from aiogram.fsm.state import State, StatesGroup


class AdminFlow(StatesGroup):
    add_movie_file = State()
    add_movie_code = State()
    add_movie_title = State()
    add_movie_description = State()
    delete_movie_code = State()
    edit_movie_code = State()
    edit_movie_value = State()
    post_movie_code = State()
    post_movie_photo = State()
    add_channel_chatid = State()
    broadcast_message = State()
    add_short_video = State()
    add_short_code = State()
    delete_short_id = State()
    card_number = State()
    card_owner = State()
    premium_price = State()
    manage_user_id = State()
    approve_days = State()


class UserFlow(StatesGroup):
    send_receipt = State()

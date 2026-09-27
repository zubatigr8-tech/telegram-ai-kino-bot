import secrets

from fastapi import Request

from shared.config import settings


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("logged_in"))


def check_credentials(username: str, password: str) -> bool:
    # compare_digest — parolni vaqt farqi orqali taxmin qilishning oldini oladi
    user_ok = secrets.compare_digest(username.encode(), settings.ADMIN_PANEL_USERNAME.encode())
    pass_ok = secrets.compare_digest(password.encode(), settings.ADMIN_PANEL_PASSWORD.encode())
    return user_ok and pass_ok

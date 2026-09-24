from fastapi import Request

from shared.config import settings


def is_logged_in(request: Request) -> bool:
    return bool(request.session.get("logged_in"))


def check_credentials(username: str, password: str) -> bool:
    return username == settings.ADMIN_PANEL_USERNAME and password == settings.ADMIN_PANEL_PASSWORD

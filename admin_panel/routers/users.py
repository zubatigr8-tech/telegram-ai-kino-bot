from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from admin_panel.auth import is_logged_in
from admin_panel.templating import templates
from shared.db.database import get_session
from shared.db.models import User

router = APIRouter()


@router.get("/users")
async def list_users(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        result = await session.execute(select(User).order_by(User.joined_at.desc()).limit(300))
        users = list(result.scalars().all())

    return templates.TemplateResponse("users.html", {"request": request, "users": users})


@router.post("/users/{tg_id}/toggle")
async def toggle_block(tg_id: int, request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        user = await session.get(User, tg_id)
        if user:
            user.is_blocked = not user.is_blocked
            await session.commit()

    return RedirectResponse("/users", status_code=302)

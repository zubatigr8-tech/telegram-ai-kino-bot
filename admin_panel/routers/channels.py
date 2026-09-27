from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from admin_panel.auth import is_logged_in
from admin_panel.templating import templates
from bot.channels import clean_username
from shared.db.database import get_session
from shared.db.models import Channel

router = APIRouter()


@router.get("/channels")
async def list_channels(request: Request, error: str | None = None):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        result = await session.execute(select(Channel))
        channels = list(result.scalars().all())

    return templates.TemplateResponse("channels.html", {"request": request, "channels": channels, "error": error})


@router.post("/channels/add")
async def add_channel(
    request: Request,
    chat_id: int = Form(...),
    username: str = Form(""),
    title: str = Form(""),
):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    # Noto'g'ri username (masalan kanal nomi) saqlanmaydi — havola bot tomonidan avtomatik olinadi
    username = clean_username(username)
    async with get_session() as session:
        session.add(Channel(chat_id=chat_id, username=username, title=title.strip() or None))
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return RedirectResponse("/channels?error=Bu+kanal+allaqachon+qo'shilgan", status_code=302)

    return RedirectResponse("/channels", status_code=302)


@router.post("/channels/{channel_id}/toggle")
async def toggle_channel(channel_id: int, request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            channel.is_active = not channel.is_active
            await session.commit()

    return RedirectResponse("/channels", status_code=302)


@router.post("/channels/{channel_id}/delete")
async def delete_channel(channel_id: int, request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        channel = await session.get(Channel, channel_id)
        if channel:
            await session.delete(channel)
            await session.commit()

    return RedirectResponse("/channels", status_code=302)

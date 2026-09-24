from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from admin_panel.auth import is_logged_in
from shared.db.database import get_session
from shared.db.models import Channel

router = APIRouter()
templates = Jinja2Templates(directory="admin_panel/templates")


@router.get("/channels")
async def list_channels(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        result = await session.execute(select(Channel))
        channels = list(result.scalars().all())

    return templates.TemplateResponse("channels.html", {"request": request, "channels": channels})


@router.post("/channels/add")
async def add_channel(
    request: Request,
    chat_id: int = Form(...),
    username: str = Form(""),
    title: str = Form(""),
):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        session.add(Channel(chat_id=chat_id, username=username or None, title=title or None))
        await session.commit()

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

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from admin_panel.auth import is_logged_in
from shared.db.database import get_session
from shared.db.models import BroadcastJob

router = APIRouter()
templates = Jinja2Templates(directory="admin_panel/templates")


@router.get("/broadcast")
async def broadcast_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        result = await session.execute(select(BroadcastJob).order_by(BroadcastJob.created_at.desc()).limit(20))
        jobs = list(result.scalars().all())

    return templates.TemplateResponse("broadcast.html", {"request": request, "jobs": jobs})


@router.post("/broadcast/send")
async def send_broadcast(request: Request, text: str = Form(...), photo_file_id: str = Form("")):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        session.add(BroadcastJob(text=text, photo_file_id=photo_file_id or None))
        await session.commit()

    return RedirectResponse("/broadcast", status_code=302)

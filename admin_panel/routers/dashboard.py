from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from admin_panel.auth import is_logged_in
from shared.db.database import get_session
from shared.db.models import BroadcastJob, Channel, Movie, User

router = APIRouter()
templates = Jinja2Templates(directory="admin_panel/templates")


@router.get("/")
async def dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        total_users = (await session.execute(select(func.count(User.tg_id)))).scalar_one()
        blocked_users = (
            await session.execute(select(func.count(User.tg_id)).where(User.is_blocked == True))  # noqa: E712
        ).scalar_one()
        total_movies = (await session.execute(select(func.count(Movie.id)))).scalar_one()
        total_channels = (await session.execute(select(func.count(Channel.id)))).scalar_one()
        pending_jobs = (
            await session.execute(select(func.count(BroadcastJob.id)).where(BroadcastJob.status == "pending"))
        ).scalar_one()
        total_sent = (await session.execute(select(func.sum(BroadcastJob.sent_count)))).scalar_one() or 0

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_users": total_users,
            "active_users": total_users - blocked_users,
            "blocked_users": blocked_users,
            "total_movies": total_movies,
            "total_channels": total_channels,
            "pending_jobs": pending_jobs,
            "total_sent": total_sent,
        },
    )

import logging

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from admin_panel.auth import check_credentials
from admin_panel.routers import broadcast, channels, dashboard, users
from admin_panel.templating import STATIC_DIR, templates
from shared.config import settings
from shared.db.database import init_db

logger = logging.getLogger(__name__)

app = FastAPI(title="Video Downloader Admin Panel")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.ADMIN_PANEL_SECRET_KEY,
    same_site="strict",  # boshqa saytlardan panelga yashirin so'rov (CSRF) yuborilishining oldini oladi
    max_age=7 * 24 * 60 * 60,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(channels.router)
app.include_router(broadcast.router)


@app.on_event("startup")
async def on_startup():
    await init_db()
    if settings.ADMIN_PANEL_SECRET_KEY in ("dev-secret-key", "iltimos-shu-yerni-tasodifiy-matnga-almashtiring"):
        logger.warning("ADMIN_PANEL_SECRET_KEY o'zgartirilmagan! .env faylida tasodifiy matnga almashtiring.")
    if settings.ADMIN_PANEL_PASSWORD in ("admin", "admin123"):
        logger.warning("Admin panel paroli juda oddiy! .env faylida ADMIN_PANEL_PASSWORD'ni almashtiring.")


@app.get("/login")
async def login_page(request: Request, error: str | None = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    if check_credentials(username, password):
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=302)
    return RedirectResponse("/login?error=Login+yoki+parol+xato", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


if __name__ == "__main__":
    import os

    import uvicorn

    # Railway/Render kabi hostinglar portni $PORT orqali o'zi beradi;
    # mahalliy kompyuterda esa .env'dagi ADMIN_PANEL_PORT ishlatiladi.
    port = int(os.environ.get("PORT", settings.ADMIN_PANEL_PORT))
    uvicorn.run("admin_panel.main:app", host=settings.ADMIN_PANEL_HOST, port=port, reload=False)

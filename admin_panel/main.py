from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from admin_panel.auth import check_credentials
from admin_panel.routers import broadcast, channels, dashboard, movies, users
from shared.config import settings
from shared.db.database import init_db

app = FastAPI(title="Kino Bot Admin Panel")
app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_PANEL_SECRET_KEY)
app.mount("/static", StaticFiles(directory="admin_panel/static"), name="static")
templates = Jinja2Templates(directory="admin_panel/templates")

app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(movies.router)
app.include_router(channels.router)
app.include_router(broadcast.router)


@app.on_event("startup")
async def on_startup():
    await init_db()


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

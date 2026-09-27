from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from admin_panel.auth import is_logged_in
from admin_panel.templating import templates
from shared.db.database import get_session
from shared.db.models import Movie

router = APIRouter()

MAX_CODE = 999_999_999  # bot 9 xonagacha bo'lgan kodlarni qidiradi


@router.get("/movies")
async def list_movies(request: Request, error: str | None = None):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        result = await session.execute(select(Movie).order_by(Movie.code))
        movies = list(result.scalars().all())

    return templates.TemplateResponse("movies.html", {"request": request, "movies": movies, "error": error})


@router.post("/movies/add")
async def add_movie(
    request: Request,
    code: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    file_id: str = Form(...),
    file_type: str = Form("video"),
):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    if not 0 <= code <= MAX_CODE:
        return RedirectResponse("/movies?error=Kod+0+dan+999999999+gacha+bo'lishi+kerak", status_code=302)
    if file_type not in ("video", "document"):
        file_type = "video"

    async with get_session() as session:
        existing = await session.execute(select(Movie).where(Movie.code == code))
        if existing.scalar_one_or_none() is not None:
            return RedirectResponse(f"/movies?error=Kod+{code}+allaqachon+band", status_code=302)

        session.add(
            Movie(
                code=code,
                title=title.strip()[:255],
                description=description.strip() or None,
                file_id=file_id.strip(),
                file_type=file_type,
            )
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            return RedirectResponse(f"/movies?error=Kod+{code}+allaqachon+band", status_code=302)

    return RedirectResponse("/movies", status_code=302)


@router.post("/movies/{movie_id}/delete")
async def delete_movie(movie_id: int, request: Request):
    if not is_logged_in(request):
        return RedirectResponse("/login", status_code=302)

    async with get_session() as session:
        movie = await session.get(Movie, movie_id)
        if movie:
            await session.delete(movie)
            await session.commit()

    return RedirectResponse("/movies", status_code=302)

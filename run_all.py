"""Hosting (Railway/Render) uchun: bot va admin panelni BITTA jarayonda,
bir vaqtda ishga tushiradi — shunda ikkalasi bitta ma'lumotlar bazasi
faylini muammosiz bo'lisha oladi (alohida servisga bo'lib tashlansa,
ular bir-biridan ajratilgan fayl tizimida ishlaydi va bazani bo'lisha olmaydi).

Ikkalasi bitta asyncio event loop'da ishlaydi: bazaga ulanishlar (engine)
umumiy bo'lgani uchun ularni turli oqimlar (thread) orasida bo'lishish xatolikka olib keladi.

Mahalliy kompyuterda ishlash uchun bu fayl SHART EMAS — u yerda
`python -m bot.main` va `python -m admin_panel.main` alohida ishlatiladi."""
import asyncio
import os

import uvicorn

from admin_panel.main import app as admin_app
from bot.main import main as run_bot
from shared.config import settings


async def main() -> None:
    port = int(os.environ.get("PORT", settings.ADMIN_PANEL_PORT))
    config = uvicorn.Config(admin_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    admin_task = asyncio.create_task(server.serve())
    try:
        await run_bot()
    finally:
        # Bot to'xtaganda admin panelni ham yopamiz
        server.should_exit = True
        await asyncio.gather(admin_task, return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())

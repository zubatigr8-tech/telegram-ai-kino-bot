"""Hosting (Railway/Render) uchun: bot va admin panelni BITTA jarayonda,
bir vaqtda ishga tushiradi — shunda ikkalasi bitta ma'lumotlar bazasi
faylini muammosiz bo'lisha oladi (alohida servisga bo'lib tashlansa,
ular bir-biridan ajratilgan fayl tizimida ishlaydi va bazani bo'lisha olmaydi).

Mahalliy kompyuterda ishlash uchun bu fayl SHART EMAS — u yerda
`python -m bot.main` va `python -m admin_panel.main` alohida ishlatiladi."""
import asyncio
import logging
import os
import threading

import uvicorn

from admin_panel.main import app as admin_app
from bot.main import main as run_bot
from shared.config import settings

logger = logging.getLogger(__name__)


def _run_admin_panel() -> None:
    port = int(os.environ.get("PORT", settings.ADMIN_PANEL_PORT))
    uvicorn.run(admin_app, host="0.0.0.0", port=port, log_level="info")


def main() -> None:
    admin_thread = threading.Thread(target=_run_admin_panel, daemon=True, name="admin-panel")
    admin_thread.start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()

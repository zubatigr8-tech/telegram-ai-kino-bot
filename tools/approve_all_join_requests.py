"""Kanalga yig'ilib qolgan BARCHA qo'shilish so'rovlarini (zayavkalarni) bir martada tasdiqlaydi.

Bot buni qila olmaydi: Telegram botga u admin bo'lishidan oldingi so'rovlarni ko'rsatmaydi.
Shuning uchun skript kanal ADMININING o'z akkaunti orqali ishlaydi (Telegram'ning
"barcha so'rovlarni tasdiqlash" funksiyasi).

Kerak bo'ladi:
  1. my.telegram.org → API development tools → api_id va api_hash
  2. pip install telethon
  3. python approve_all_join_requests.py

Xavfsizlik: login ma'lumotlari faqat xotirada turadi — kompyuterga hech qanday fayl yozilmaydi,
skript tugashi bilan sessiya yopiladi. api_hash va SMS kodni hech kimga bermang."""
import asyncio
import sys

from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, FloodWaitError
from telethon.sessions import StringSession
from telethon.tl import functions, types

MAX_ROUNDS = 10  # Telegram ko'p so'rovni bir necha bosqichda bajarishi mumkin


async def pending_count(client: TelegramClient, channel) -> int:
    result = await client(functions.messages.GetChatInviteImportersRequest(
        peer=channel, requested=True, offset_date=None,
        offset_user=types.InputUserEmpty(), limit=1,
    ))
    return result.count


async def find_channel(client: TelegramClient, query: str):
    """@username, t.me havolasi yoki kanal nomi bo'yicha topadi."""
    query = query.strip()
    if query.startswith("@") or ("t.me/" in query and "/+" not in query and "joinchat" not in query):
        return await client.get_entity(query)
    async for dialog in client.iter_dialogs():
        if dialog.is_channel and dialog.title.strip().lower() == query.lower():
            return dialog.entity
    return None


async def main() -> None:
    print("=== Barcha zayavkalarni tasdiqlash ===\n")
    api_id = int(input("api_id (my.telegram.org dan): ").strip())
    api_hash = input("api_hash: ").strip()
    query = input("Kanal (@username yoki kanal nomi, masalan Nextgoal): ")

    async with TelegramClient(StringSession(), api_id, api_hash, flood_sleep_threshold=120) as client:
        # Birinchi marta telefon raqam va Telegram yuborgan kodni so'raydi
        await client.start()
        channel = await find_channel(client, query)
        if channel is None:
            print(f"❌ «{query}» kanali topilmadi. Kanal nomini Telegram'dagidek aniq yozing.")
            return

        try:
            before = await pending_count(client, channel)
        except ChatAdminRequiredError:
            print("❌ Siz bu kanalda admin emassiz yoki «Foydalanuvchilarni qo'shish» huquqingiz yo'q.")
            return
        print(f"\n📢 Kanal: {channel.title}\n⏳ Kutilayotgan zayavkalar: {before}")
        if before == 0:
            print("✅ Tasdiqlanadigan zayavka yo'q.")
            return
        if input("Hammasini tasdiqlaymizmi? (ha/yo'q): ").strip().lower() not in ("ha", "h", "yes", "y"):
            print("Bekor qilindi.")
            return

        remaining = before
        for round_no in range(1, MAX_ROUNDS + 1):
            try:
                await client(functions.messages.HideAllChatJoinRequestsRequest(peer=channel, approved=True))
            except FloodWaitError as exc:
                print(f"⏳ Telegram {exc.seconds} soniya kutishni so'radi...")
                await asyncio.sleep(exc.seconds + 1)
                continue
            await asyncio.sleep(3)
            remaining = await pending_count(client, channel)
            print(f"   {round_no}-bosqich: qolgan zayavkalar — {remaining}")
            if remaining == 0:
                break

        print(f"\n✅ Tasdiqlandi: {before - remaining} ta")
        if remaining:
            print(f"⚠️ Qolgan: {remaining} ta — skriptni birozdan so'ng qayta ishga tushiring.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit("\nTo'xtatildi.")

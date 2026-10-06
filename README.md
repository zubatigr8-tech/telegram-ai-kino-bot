# 📥 Video Downloader — Telegram bot

**Video Downloader** — Instagram, YouTube va TikTok havolasidan videoni yuklab beradigan,
videodagi qo'shiqni aniqlab (Shazam), uning to'liq versiyasini audio qilib yuboradigan bot.
(Repozitoriy nomi tarixan `telegram-ai-kino-bot` bo'lib qolgan.)

> Bot nomi: **Video Downloader**. @BotFather → `/newbot` → nom: `Video Downloader`,
> username (oxiri `bot` bilan tugashi shart, noyob bo'lishi kerak), masalan:
> `@VideoDownloaderUzBot`, `@UzVideoDownloaderBot`, `@VideoDownloader_Uz_bot`.

## Foydalanuvchi uchun oqim

1. Foydalanuvchi `/start` bosadi (bosmaguncha bot boshqa xabarlarga javob bermaydi, faqat `/start` so'raydi)
2. Majburiy kanal(lar)ga obuna bo'lishi so'raladi → obuna bo'lib **✅ Tekshirish**ni bosadi
3. **Havola yuboradi** (Instagram / YouTube / TikTok):
   1. 📥 bot videoni yuklab yuboradi (720p gacha, 50 MB dan oshsa — pastroq sifatda)
   2. 🎵 videodagi qo'shiqni Shazam orqali aniqlaydi (topilmasa — platforma ko'rsatgan qo'shiq nomidan)
   3. 🎧 qo'shiqning to'liq versiyasini YouTube'dan topib, audio qilib yuboradi (Shazam / YouTube tugmalari bilan)
   4. qo'shiq aniqlanmasa — videoning o'z ovozi MP3 qilib yuboriladi

## Imkoniyatlar

- 📥 Instagram (Reels, post), YouTube (video, Shorts), TikTok videolarini yuklash
- 🎵 Videodagi qo'shiqni aniqlash (Shazam, API kalit shart emas) va to'liq qo'shiqni yuborish
- ✍️ Qo'shiq nomi yoki **matnidan parcha** bo'yicha qidirish — natijalar ro'yxati, tanlangani audio bo'lib keladi
- ✅ Kanal/guruhga qo'shilish so'rovlarini (zayavka) avtomatik tasdiqlash va so'rov yuborganlarga xabar
- ⚡ Kesh: bir xil havola yoki qo'shiq qayta so'ralsa — qayta yuklamasdan darhol yuboriladi
- 🚦 Navbat: bir vaqtda `MAX_CONCURRENT_DOWNLOADS` tadan ortiq yuklash bo'lmaydi, har bir foydalanuvchi bittadan havola
- 📢 Majburiy kanal obunasini tekshirish
- 👤 Foydalanuvchilarni bazada saqlash, bloklash
- ⚙️ Alohida veb-admin panel (statistika, foydalanuvchilar, kanallar, xabar yuborish)
- 📱 Xuddi shu boshqaruv botning o'zida ham — `/admin` buyrug'i (faqat adminlarga ko'rinadi)
- 🔔 Barcha foydalanuvchilarga avtomatik xabar yuborish (broadcast)

## Tuzilma

```
telegram-ai-kino-bot/
├── bot/            # Telegram bot (aiogram 3)
├── admin_panel/    # Veb-admin panel (FastAPI)
├── shared/         # Ikkalasi ham ishlatadigan DB va sozlamalar
├── .env.example    # Sozlamalar namunasi
└── requirements.txt
```

Bot va admin panel — ikki alohida jarayon, lekin bitta ma'lumotlar bazasini (SQLite)
birga ishlatadi. Shu sababli **ikkalasini alohida terminalda** ishga tushirish kerak.

## 1. O'rnatish

> ⚠️ **Python 3.12** kerak. Qo'shiqni aniqlaydigan `shazamio` kutubxonasi Python 3.13 va undan
> yangi versiyalarda o'rnatilmaydi. Tekshirish: `py --version`. Python 3.12 ni python.org dan
> yoki `py install 3.12` buyrug'i bilan o'rnating va venv'ni `py -3.12 -m venv .venv` bilan yarating.

```bash
cd telegram-ai-kino-bot
python -m venv .venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Sozlash

`.env.example` faylidan nusxa olib, `.env` deb nomlang, so'ng qiymatlarni to'ldiring:

```bash
cp .env.example .env
```

| O'zgaruvchi | Qayerdan olinadi |
|---|---|
| `BOT_TOKEN` | Telegramda [@BotFather](https://t.me/BotFather) → `/newbot` |
| `ADMIN_IDS` | Botga `/myid` yuborib, chiqqan raqam (vergul bilan bir nechtasi bo'lishi mumkin) |
| `ADMIN_PANEL_USERNAME` / `ADMIN_PANEL_PASSWORD` | O'zingiz o'ylab kiritasiz — admin panelga kirish uchun |
| `ADMIN_PANEL_SECRET_KEY` | Ixtiyoriy tasodifiy uzun matn (sessiya shifrlash uchun) |

## 3. Ishga tushirish

**1-terminal — bot:**
```powershell
.venv\Scripts\Activate.ps1
python -m bot.main
```

**2-terminal — admin panel:**
```powershell
.venv\Scripts\Activate.ps1
python -m admin_panel.main
```

Admin panel ochiladi: **http://localhost:8000** (login/parolni `.env`dagi
`ADMIN_PANEL_USERNAME` / `ADMIN_PANEL_PASSWORD` bilan kiritasiz).

## 4. Bot ichidagi admin panel

Veb-panelga qo'shimcha ravishda, `ADMIN_IDS`dagi foydalanuvchilar botning o'zida
**`/admin`** buyrug'i orqali ham boshqarishlari mumkin: statistika, foydalanuvchilar
(bloklash), kanallar (qo'shish/o'chirish) va xabar
yuborish — hammasi inline tugmalar orqali. Oddiy foydalanuvchilarga bu buyruq
umuman ko'rinmaydi.

## 7. Majburiy kanal obunasi

1. Botni kerakli kanalga **admin** qilib qo'shing (kanal a'zolarini ko'rish uchun shart).
2. Kanalning chat ID'sini bilish uchun: kanalga biror xabar yuborib, uni
   [@JsonDumpBot](https://t.me/JsonDumpBot) kabi botga forward qiling — yoki kanal
   `@username`li bo'lsa, `username`ni to'g'ridan-to'g'ri admin panelga kiritish kifoya
   (chat_id maydoniga vaqtincha `-100` bilan boshlanadigan raqam kerak bo'ladi —
   buni Telegram API orqali yoki tegishli botlar yordamida topish mumkin).
3. Admin panel → **📢 Kanallar** → qo'shing. Shundan so'ng bot faqat shu
   kanal(lar)ga obuna bo'lgan foydalanuvchilarga xizmat ko'rsatadi.

Kanal qo'shilmagan bo'lsa (ro'yxat bo'sh), obuna tekshiruvi umuman ishlamaydi —
ya'ni bu funksiya ixtiyoriy.

## 8. Xabar yuborish (broadcast)

Admin panel → **🔔 Xabar yuborish** (yoki botda `/admin` → **🔔 Xabar yuborish**) →
matnni yozib yuborasiz. Bot fon rejimida (har 5 soniyada tekshirib) uni barcha
bloklanmagan foydalanuvchilarga avtomatik yetkazadi, flood-limitga tushmasligi
uchun sekin-asta yuboradi.

## 9. Zaxira nusxalar (backup)

Bot ishga tushganda va har 6 soatda avtomatik ravishda ma'lumotlar bazasining
zaxira nusxasini `backups/` papkasiga oladi (oxirgi 20 tasi saqlanadi, eskilari
o'zi o'chadi). Qo'lda hech narsa qilish shart emas.

## 10. Video/qo'shiq yuklash sozlamalari

Hech narsa qo'shimcha o'rnatish shart emas: `yt-dlp`, `shazamio` va `imageio-ffmpeg`
(tayyor ffmpeg bilan) `requirements.txt` orqali o'rnatiladi. Serverda ffmpeg bo'lsa, o'shanisi ishlatiladi.

| O'zgaruvchi | Ma'nosi |
|---|---|
| `DOWNLOAD_DIR` | Vaqtinchalik fayllar papkasi (yuborilgach o'chiriladi) |
| `MAX_CONCURRENT_DOWNLOADS` | Bir vaqtda nechta yuklash (standart 3) |
| `MAX_UPLOAD_MB` | Telegram limiti — 50 MB |
| `MAX_VIDEO_DURATION` | Eng uzun video, soniyada (standart 1200 = 20 daqiqa) |
| `COOKIES_FILE` | Instagram/YouTube "login talab qilinadi" desa — brauzerdan eksport qilingan `cookies.txt` yo'li |

**Muhim:**
- Instagram ko'pincha serverlardan login so'raydi. Shunda Instagram akkauntingizga
  brauzerda kirib, "Get cookies.txt LOCALLY" kabi kengaytma bilan `cookies.txt`ni
  eksport qiling va `COOKIES_FILE`ga yo'lini yozing.
- Platformalar tez-tez o'zgaradi — `yt-dlp`ni vaqti-vaqti bilan yangilab turing:
  `pip install -U yt-dlp`.
- Yopiq (private) videolarni yuklab bo'lmaydi.

## 11. Railway'ga joylash (24/7 ishlashi uchun)

1. railway.com → GitHub bilan kiring → **New Project → Deploy from GitHub repo** → shu repozitoriy.
2. Servis → **Settings → Source → Branch** — kodi bor branchni tanlang.
3. Servis → **Variables** → quyidagilarni qo'shing:
   `BOT_TOKEN`, `ADMIN_IDS`, `ADMIN_PANEL_USERNAME`, `ADMIN_PANEL_PASSWORD`, `ADMIN_PANEL_SECRET_KEY`,
   `DATABASE_URL=sqlite+aiosqlite:////data/bot_database.db`, `BACKUP_DIR=/data/backups`,
   ixtiyoriy: `COOKIES_TEXT` (cookies.txt ichidagi matn).
4. Servis ustida o'ng tugma → **Attach Volume** → Mount path: `/data` (baza qayta joylashda o'chib ketmasligi uchun).
5. **Settings → Networking → Generate Domain** — admin panel manzili.
6. ⚠️ Kompyuteringizdagi botni o'chiring: bitta token bilan ikki joyda ishlasa, `Conflict` xatosi chiqadi.

## Kengaytirish g'oyalari

- Qo'shiq nomini matn bilan yozib qidirish (`/music Believer`)
- Ovozli xabar / audio yuborib qo'shiqni aniqlash
- 50 MB dan katta videolar uchun lokal Bot API server (2 GB gacha)

- Ko'p tilli interfeys
- SQLite o'rniga PostgreSQL (`DATABASE_URL`ni almashtirish kifoya)

## 12. Zayavkalarni avtomatik tasdiqlash

1. Botni kanalga **admin** qiling va unga **"Foydalanuvchilarni qo'shish" (Invite users via link)** huquqini bering.
2. Kanal havolasini **"Qo'shilish so'rovi" (Request to join)** rejimida yarating.
3. Kimdir so'rov yuborsa, bot unga xabar yuboradi va so'rovni o'zi tasdiqlaydi.

Sozlamalar: `AUTO_APPROVE_JOIN_REQUESTS` (true/false) va `JOIN_WELCOME_TEXT` (xabar matni).
Telegram qoidasi: bot bunday foydalanuvchiga faqat so'rov paytida yoza oladi. Keyingi xabarlar
(broadcast) unga faqat u botga `/start` bosgan bo'lsa yetadi — shuning uchun xabarda "Botni ishga
tushirish" tugmasi bor.

## Foydali buyruqlar (faqat adminlar uchun)

- `/admin` — bot ichidagi admin panel
- `/server` — bot qayerda ishlayotganini ko'rsatadi (☁️ Railway yoki 🖥️ kompyuter)
- `/cookies` — cookies holati; cookies faylini (`.txt`/`.json`) botga **fayl qilib** yuborsangiz, bot uni saqlaydi
- `/myid` — Telegram ID'ingiz (hamma uchun; `ADMIN_IDS` ga shu raqam yoziladi)

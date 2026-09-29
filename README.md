# 🎬 Telegram Kino Bot

Kino kodini qidirib topadigan, majburiy kanal obunasini tekshiradigan va alohida
veb-admin panelga ega Telegram bot.

> 🚗 Shu repoda haydovchilar uchun alohida **antiradar bot** ham bor — qarang: [antiradar/README.md](antiradar/README.md)

## Foydalanuvchi uchun oqim

1. Foydalanuvchi `/start` bosadi (bosmaguncha bot boshqa xabarlarga javob bermaydi, faqat `/start` so'raydi)
2. Majburiy kanal(lar)ga obuna bo'lishi so'raladi → obuna bo'lib **✅ Tekshirish**ni bosadi
3. Kino kodini (raqam) yuboradi → bot kinoni yuboradi

## Imkoniyatlar

- 🎬 Kino kodi (raqam) orqali video/fayl topib berish
- 📢 Majburiy kanal obunasini tekshirish
- 👤 Foydalanuvchilarni bazada saqlash, bloklash
- ⚙️ Alohida veb-admin panel (statistika, foydalanuvchilar, kinolar, kanallar, xabar yuborish)
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
(bloklash), kinolar (ko'rish + qo'shish), kanallar (qo'shish/o'chirish) va xabar
yuborish — hammasi inline tugmalar orqali. Oddiy foydalanuvchilarga bu buyruq
umuman ko'rinmaydi.

## 6. Kino qo'shish tartibi

**Veb-panel orqali:**
1. Botga (admin sifatida, `ADMIN_IDS`da bo'lgan holda) kino videosini yoki faylini yuboring.
2. Bot javob qaytaradi: `file_id` va turi (`video`/`document`).
3. Admin panel → **🎬 Kinolar** → shu `file_id`ni, kodni (masalan `7`), nomini kiritib qo'shing.
4. Foydalanuvchi botga `7` deb yozganda — shu kino avtomatik yuboriladi.

**Yoki bot ichidan:** `/admin` → **🎬 Kinolar** → **➕ Yangi kino qo'shish** — bot
video, kod, nom va tavsifni ketma-ket so'raydi, `file_id`ni qo'lda ko'chirish shart emas.

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

## Kengaytirish g'oyalari

- Ko'p tilli interfeys
- SQLite o'rniga PostgreSQL (`DATABASE_URL`ni almashtirish kifoya)
- Kino kategoriyalari/qidiruv nom bo'yicha

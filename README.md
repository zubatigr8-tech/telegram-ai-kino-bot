# 🎬 Telegram Kino Bot

Kino kodini qidirib topadigan, majburiy kanal obunasini tekshiradigan va alohida
veb-admin panelga ega Telegram bot.

## Foydalanuvchi uchun oqim

1. Foydalanuvchi `/start` bosadi (bosmaguncha bot boshqa xabarlarga javob bermaydi, faqat `/start` so'raydi)
2. Majburiy kanal(lar)ga obuna bo'lishi so'raladi → obuna bo'lib **✅ Tekshirish**ni bosadi
3. Kino kodini (raqam) yuboradi → bot kinoni yuboradi

Pastki menyuda **🎬 Shorts** (qisqa videolar, "To'liq kino" tugmasi bilan) va
**💎 Premium** (kartaga to'lov → chek → admin tasdig'i; premium foydalanuvchi
majburiy kanallarga obuna bo'lmasdan kinolarni oladi) tugmalari bor.
Kanal postidagi **🎬 Kinoni ko'rish** tugmasi botni `/start <kod>` bilan ochadi va
kinoni (obuna tekshiruvidan keyin) darhol yuboradi.

## Imkoniyatlar

- 🎬 Kino kodi (raqam) orqali video/fayl topib berish
- 📢 Majburiy kanal obunasini tekshirish
- 👤 Foydalanuvchilarni bazada saqlash, bloklash
- ⚙️ Alohida veb-admin panel (statistika, foydalanuvchilar, kinolar, kanallar, xabar yuborish)
- 📱 Botning o'zida to'liq admin panel — `/admin` (kinolar, shorts, kanallar, premium, adminlar)
- 💎 Premium (kartaga to'lov, chekni admin tasdiqlaydi) va 🎬 Shorts
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

Adminlar botda **`/admin`** (yoki **📋 Boshqarish** tugmasi) orqali pastki menyuli
admin panelni ochadi:

| Tugma | Vazifasi |
|---|---|
| 📣 Kanallarni sozlash | Majburiy kanallar: qo'shish (post forward / ID / @username), yoqish/o'chirish, kanal admini, zayavkalar soni va ularni tasdiqlash |
| 📈 Statistika | Foydalanuvchilar, faollik, premium, kinolar, ko'rishlar, eng ko'p ko'rilgan kinolar |
| ✉️ Xabar yuborish | Istalgan xabar (matn/rasm/video) nusxasi barcha foydalanuvchilarga, xohlasangiz kanallarga ham |
| 🤖 Bot holati | Ishlash vaqti, navbatdagi xabarlar, to'lovlar, har bir kanalda bot admin ekanligi |
| 📥 Kino yuklash / 🗑 Kino o'chirish / ✏️ Kino tahrirlash | Kinolar (nom, tavsif, kod, fayl) |
| 📣 Kino postini yuborish | Kanalga poster + "🎬 Kinoni ko'rish" tugmali post |
| 🎬 Shorts yuklash / 🗑 Shorts o'chirish | Qisqa videolar (kino kodiga bog'lash mumkin) |
| 💳 Karta sozlamalari | Premium to'lovi uchun karta raqami, egasi va narx |
| 👤 Boshqarish | ID bo'yicha foydalanuvchi: bloklash, premium berish/olish, admin qilish |
| 👑 Adminlar ro'yxati / 💎 Premiumlar ro'yxati | Ro'yxatlar |
| 🔄 Premium holati | Premiumni yoqish/o'chirish, kutilayotgan to'lovlar |

`.env`dagi `ADMIN_IDS` — asosiy adminlar; faqat ular boshqa adminlarni qo'sha/o'chira oladi.
Bot orqali qo'shilgan adminlar bazada saqlanadi.

**Kanal zayavkalari** (📣 Kanallarni sozlash → kanalni tanlash):
- Bot zayavkalarni **hech qachon o'zi tasdiqlamaydi** — ular faqat yig'iladi.
- Bot zayavka talab qiladigan maxsus havola yaratadi (🔗 Zayavka havolasi). So'rov yuborgan foydalanuvchi
  darhol obuna bo'lgan hisoblanadi va kino oladi, so'rov esa tasdiqlanmay turadi. Zayavkalar soni
  1000, 5000, 10000 (keyin har 10000) ga yetganda kanal admini va bot adminlariga xabar boradi;
  **✅ Hammasini tasdiqlash** tugmasi barcha kutilayotgan so'rovlarni birdan tasdiqlaydi.
- **👤 Kanal admini** — kanal egasining Telegram ID si. U botda **📊 Kanalim** (yoki `/kanal`) orqali
  kanaldagi obunachilar, bot orqali kelgan zayavkalar sonini ko'radi va zayavkalarni tasdiqlaydi.

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

## 🩸 Qon tahlili boti (`qon_tahlili/`)

Kino botdan **alohida** bot: foydalanuvchi qon tahlili natijalarini yuboradi, bot esa
- har bir ko'rsatkichni jins/yoshga mos norma bilan solishtiradi (⬇️ / ✅ / ⬆️ / 🚨 xavfli daraja),
- **hozirgi holat** bo'yicha ehtimoliy sabablarni ko'rsatadi (kamqonlik turlari, infeksiya, diabet, jigar, buyrak, qalqonsimon bez, elektrolitlar...),
- **kelajakdagi xavflarni** aytadi (prediabet → diabet, dislipidemiya → infarkt/insult, metabolik sindrom, podagra, osteoporoz, buyrak faoliyati pasayishi...),
- har biri uchun **chora-tadbirlar**, qaysi **shifokorga** borish va qanday **qo'shimcha tahlillar** kerakligini yozadi,
- xavfli qiymatlarda 🚨 shoshilinch ogohlantirish beradi (103).

> ⚠️ Dastur shifokor emas va tashxis qo'ymaydi — u natijani tushunish va shifokorga to'g'ri savol bilan borish uchun.
> Dori dozalari hech qachon tavsiya qilinmaydi. Tahlil natijalari bazaga **saqlanmaydi**.

**Qo'llab-quvvatlanadigan ko'rsatkichlar (38 ta):** gemoglobin, eritrotsit, gematokrit, MCV, MCH, leykotsit va
leykoformula, trombotsit, ECHT; glyukoza, HbA1c; xolesterin, LDL, HDL, triglitseridlar; ALT, AST, GGT, ishqoriy
fosfataza, bilirubin, umumiy oqsil, albumin; kreatinin (+ eGFR CKD-EPI 2021), mochevina, siydik kislotasi; TTG, erkin T4;
ferritin, temir, B12, vitamin D; CRP, kaliy, natriy, kalsiy. Nomlar o'zbekcha, ruscha yoki inglizcha yozilishi mumkin,
mg/dL kabi boshqa birliklar ko'p hollarda avtomatik o'giriladi.

**Ishga tushirish:**
1. @BotFather'da yangi bot oching, tokenni `.env` dagi `QON_BOT_TOKEN` ga yozing.
2. (Ixtiyoriy) blankani rasmdan o'qish uchun `ANTHROPIC_API_KEY` ni kiriting.
3. `python -m qon_tahlili.bot`

**Terminalda sinash:**
```bash
python -m qon_tahlili.cli --jins f --yosh 52 "Gemoglobin 98, MCV 74, ferritin 9, glyukoza 6.1, LDL 4.2"
```

**Testlar:** `pip install pytest && python -m pytest tests`

Yangi qoida qo'shish: `qon_tahlili/markers.py` — ko'rsatkich va normalar, `qon_tahlili/analyzer.py` — kasallik/xavf qoidalari.

## Kengaytirish g'oyalari

- Ko'p tilli interfeys
- SQLite o'rniga PostgreSQL (`DATABASE_URL`ni almashtirish kifoya)
- Kino kategoriyalari/qidiruv nom bo'yicha

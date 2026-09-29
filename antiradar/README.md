# 🚗 AI Antiradar bot (haydovchilar uchun)

BotFather'da tavsiya etilgan nom: **AI Antiradar**, username masalan `@ai_antiradar_uz_bot`.

Telegram bot haydovchining **jonli joylashuvi** (Live Location) bo'yicha tezlik kameralari,
radarlar, YPX postlari va **yo'l belgilariga** yaqinlashganda oldindan **ovozli** ogohlantiradi. Hozircha faqat
**O'zbekiston** uchun, 4 tilda: o'zbek, rus, ingliz, turk.

> Bot haqiqiy radar signalini sezmaydi (buni faqat mashinadagi qurilma qila oladi). U
> Waze / Yandex kabi ishlaydi: kameralar joylashuvi bazada saqlanadi, bot esa haydovchining
> GPS nuqtasini ular bilan solishtiradi.

## Foydalanuvchi uchun oqim

1. `/start` → til tanlanadi (Telegram ilovasi tiliga mosi birinchi turadi)
2. Avtomatik **bepul sinov davri** beriladi (standart 3 kun)
3. 📎 → Joylashuv → **Jonli joylashuvni ulashish**
4. Har ogohlantirish **avval ovozli xabar**, keyin matnli xabar bo'lib keladi:
   - radar/kameraga **500 m** va **200 m** qolganda: turi, tezlik chegarasi, limitdan oshsangiz — «Tezlikni kamaytiring!»
   - yo'l belgisiga **150 m** qolganda (bir marta)
5. Sinov tugagach — **oylik obuna** (Telegram Stars ⭐, har oy avtomatik yangilanadi)

## Imkoniyatlar

- 🔊 Ovozli ogohlantirish 4 tilda (edge-tts, bepul). Iboralar keshlanadi, TTS ishlamasa ham matn baribir keladi
- 🪧 Yo'l belgilari: tezlik cheklovi, piyodalar o'tish joyi, STOP, «Yo'l bering», sun'iy notekislik,
  temir yo'l kesishmasi, «Ehtiyot bo'ling, bolalar». Sozlamalarda o'chirib qo'yish mumkin (radarlar doim yoqilgan)
- 🧭 Faqat **oldindagi** va sizning yo'nalishingizni o'lchaydigan kameralar haqida xabar beriladi
- 🚀 Tezlik GPS nuqtalaridan hisoblanadi; kamera limitidan oshsangiz — 🔴 ogohlantirish
- ⚙️ Shaxsiy tezlik chegarasi (masalan 90 km/soat) — undan oshsangiz eslatadi
- ⭐ Telegram Stars orqali oylik obuna, sinov davri
- 🗺 **Radarlar bazasi avtomatik**: bot har kuni OpenStreetMap'dan radar va belgilarni o'zi yangilaydi
  (OSM'dan o'chirilganlari botdan ham o'chadi). Haydovchilar hech narsa qo'shmaydi
- 📥 Tayyor ro'yxatni yuklash: admin botga `.csv` fayl yuboradi (rasmiy ro'yxat yoki litsenziyali baza)
- 👮 Admin: `/stats`, `/osm` (hozir yangilash), oddiy joylashuv yuborib nuqta qo'shish, `/delcam <id>`

## Sozlash

`.env` fayliga (kino bot bilan umumiy) qo'shing:

| O'zgaruvchi | Tavsif |
|---|---|
| `ANTIRADAR_BOT_TOKEN` | @BotFather'dan **yangi** bot tokeni (kino botnikidan boshqa) |
| `ANTIRADAR_ADMIN_IDS` | Adminlar ID si, vergul bilan (bo'sh bo'lsa `ADMIN_IDS` olinadi) |
| `ANTIRADAR_PRICE_STARS` | Oylik obuna narxi, Stars'da (standart 100) |
| `ANTIRADAR_TRIAL_DAYS` | Bepul sinov kunlari (standart 3) |
| `ANTIRADAR_OSM_REFRESH_HOURS` | OSM'dan necha soatda bir yangilash (standart 24, `0` — o'chirilgan) |
| `ANTIRADAR_VOICE` | `false` — ovozsiz, faqat matn (standart `true`) |
| `ANTIRADAR_DATABASE_URL` | Ixtiyoriy. Standart: `antiradar.db` (SQLite) |

## Ishga tushirish

```bash
pip install -r requirements.txt

# Botni ishga tushirish — radarlar bazasi OSM'dan avtomatik yuklanadi va har kuni yangilanadi
python -m antiradar.main

# (ixtiyoriy) OSM importini qo'lda ishga tushirish
python -m antiradar.osm_import
```

## Radarlar qayerdan olinadi

1. **OpenStreetMap** — avtomatik, har kuni. O'zbekiston bo'yicha to'liq emas.
2. **CSV fayl** — admin botga yuboradi. Ustunlar: `lat`, `lon`, `kind`, `speed_limit`, `direction`
   (faqat `lat` va `lon` majburiy; `;` yoki `,` bilan ajratilgan, Excel'dan saqlash mumkin):

   ```csv
   lat;lon;kind;speed_limit
   41.311081;69.240562;fixed;60
   41.299496;69.268440;crossing;
   ```
   `kind` qiymatlari: `fixed`, `mobile`, `red_light`, `average`, `police`, `speed_limit`, `crossing`,
   `stop`, `give_way`, `speed_bump`, `railway_crossing`, `children`. 15 m ichidagi takrorlar o'tkazib yuboriladi.
3. **Qo'lda** — admin botga oddiy (jonli emas) joylashuv yuboradi → turi → tezlik chegarasi.

> Mobil radarlar (YPX qo'lda ushlab turadigan) joyi har kuni o'zgaradi — ularni hech qanday
> bazadan avtomatik bilib bo'lmaydi.

## Testlar

```bash
pip install pytest
python -m pytest tests
```

## Tuzilma

```
antiradar/
├── main.py          # botni ishga tushirish
├── config.py        # .env sozlamalari
├── db.py            # modellar: users, cameras, payments
├── geo.py           # masofa, azimut
├── alerts.py        # ogohlantirish mantiqi (Telegram'ga bog'liq emas)
├── voice.py         # ovozli xabar (TTS + kesh)
├── i18n.py          # tarjimalar
├── locales/         # uz / ru / en / tr
├── osm_import.py    # OpenStreetMap importi + kunlik avtomatik yangilash
├── file_import.py   # CSV fayldan import
└── handlers/        # start, settings, subscription, location, admin
```

## Keyingi bosqichlar

- Admin veb-panelda xarita
- Boshqa davlatlar (Markaziy Osiyo, Turkiya, Yevropa, AQSh) — `/start`da davlat tanlash
- AI: ovozli buyruqlar, yo'l qoidalari bo'yicha yordamchi

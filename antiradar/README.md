# 🚗 Antiradar bot (haydovchilar uchun)

Telegram bot haydovchining **jonli joylashuvi** (Live Location) bo'yicha tezlik kameralari,
radarlar va YPX postlariga yaqinlashganda oldindan ogohlantiradi. Hozircha faqat
**O'zbekiston** uchun, 4 tilda: o'zbek, rus, ingliz, turk.

> Bot haqiqiy radar signalini sezmaydi (buni faqat mashinadagi qurilma qila oladi). U
> Waze / Yandex kabi ishlaydi: kameralar joylashuvi bazada saqlanadi, bot esa haydovchining
> GPS nuqtasini ular bilan solishtiradi.

## Foydalanuvchi uchun oqim

1. `/start` → til tanlanadi (Telegram ilovasi tiliga mosi birinchi turadi)
2. Avtomatik **bepul sinov davri** beriladi (standart 3 kun)
3. 📎 → Joylashuv → **Jonli joylashuvni ulashish**
4. Kameraga **500 m** va **200 m** qolganda xabar keladi: turi, tezlik chegarasi, limitdan
   oshgan bo'lsa — ogohlantirish
5. Sinov tugagach — **oylik obuna** (Telegram Stars ⭐, har oy avtomatik yangilanadi)

## Imkoniyatlar

- 🧭 Faqat **oldindagi** va sizning yo'nalishingizni o'lchaydigan kameralar haqida xabar beriladi
- 🚀 Tezlik GPS nuqtalaridan hisoblanadi; kamera limitidan oshsangiz — 🔴 ogohlantirish
- ⚙️ Shaxsiy tezlik chegarasi (masalan 90 km/soat) — undan oshsangiz eslatadi
- ⭐ Telegram Stars orqali oylik obuna, sinov davri
- 👮 Admin: `/stats`, oddiy joylashuv yuborib kamera qo'shish, `/delcam <id>`
- 🗺 OpenStreetMap'dan kameralarni import qilish

## Sozlash

`.env` fayliga (kino bot bilan umumiy) qo'shing:

| O'zgaruvchi | Tavsif |
|---|---|
| `ANTIRADAR_BOT_TOKEN` | @BotFather'dan **yangi** bot tokeni (kino botnikidan boshqa) |
| `ANTIRADAR_ADMIN_IDS` | Adminlar ID si, vergul bilan (bo'sh bo'lsa `ADMIN_IDS` olinadi) |
| `ANTIRADAR_PRICE_STARS` | Oylik obuna narxi, Stars'da (standart 100) |
| `ANTIRADAR_TRIAL_DAYS` | Bepul sinov kunlari (standart 3) |
| `ANTIRADAR_DATABASE_URL` | Ixtiyoriy. Standart: `antiradar.db` (SQLite) |

## Ishga tushirish

```bash
pip install -r requirements.txt

# 1) Kameralarni OpenStreetMap'dan yuklash (bir marta, keyin vaqti-vaqti bilan yangilash)
python -m antiradar.osm_import

# 2) Botni ishga tushirish
python -m antiradar.main
```

OSM'da O'zbekiston kameralari to'liq emas. Qolganini admin qo'shadi: botga oddiy
(jonli emas) joylashuv yuboring → kamera turi → tezlik chegarasi.

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
├── i18n.py          # tarjimalar
├── locales/         # uz / ru / en / tr
├── osm_import.py    # OpenStreetMap importi
└── handlers/        # start, settings, subscription, location, admin
```

## Keyingi bosqichlar

- Haydovchilar o'zlari kamera/YPX postini qo'shishi va tasdiqlashi (👍/👎)
- Ovozli ogohlantirish
- Admin veb-panelda xarita
- Boshqa davlatlar (Markaziy Osiyo, Turkiya, Yevropa, AQSh) — `/start`da davlat tanlash
- AI: ovozli buyruqlar, yo'l qoidalari bo'yicha yordamchi

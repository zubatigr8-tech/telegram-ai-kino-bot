# 🧱 Qurilish mollari do'koni: AI sotuvchi bot

Telegram bot do'kon sotuvchisi kabi gaplashadi. U Claude AI (Anthropic) asosida ishlaydi.

## Nima qila oladi (1-versiya)

- 💬 Qurilish materiallari bo'yicha maslahat beradi: qaysi sement, kafel yelimi, gruntovka va h.k.
- 📐 Material miqdorini taxminiy hisoblaydi (kafel, bo'yoq, g'isht, sement...), zaxirasi bilan.
- 🛒 **Zayavka qabul qiladi**: mijozning ismi, telefoni, nima kerakligi va manzilini suhbat
  davomida so'raydi. Keyin zayavkani sotuvchining Telegramiga yuboradi va `leads.jsonl` fayliga yozadi.
- 📷 Rasmni tushunadi: mijoz devor, quvur yoki eski mahsulot rasmini yuborsa, maslahat beradi.
- 🌐 Mijoz qaysi tilda yozsa (o'zbek lotin/kirill yoki rus), o'sha tilda javob beradi.
- 🚫 **Narx va qoldiqni o'ylab topmaydi.** Mahsulotlar bazasi hali yo'q, shuning uchun narx
  so'ralsa, zayavka qoldirishni taklif qiladi.

## O'rnatish

```bash
cd telegram-ai-kino-bot
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r stroy_bot/requirements.txt
```

1. @BotFather'da **yangi** bot oching va tokenni oling.
2. https://console.anthropic.com dan Claude API kalitini oling.
3. `stroy_bot/.env.example` faylini `stroy_bot/.env` nomi bilan nusxalang va to'ldiring.
4. **`stroy_bot/store_info.md`** faylida do'kon nomi, manzil, telefon, ish vaqti, yetkazib
   berish va to'lov turlarini yozing. Bot faqat shu ma'lumotlarga tayanadi.

## Ishga tushirish

```bash
python -m stroy_bot.main
```

So'ng botga `/myid` yuboring, chiqqan raqamni `.env` dagi `STROY_ADMIN_IDS` ga yozing va
botni qayta ishga tushiring. Shundan keyin zayavkalar sizga keladi.

## Buyruqlar

| Buyruq | Vazifasi |
|--------|----------|
| `/start` | Salomlashish va menyu |
| `/new` yoki 🔄 | Suhbatni yangidan boshlash |
| `/myid` | O'z Telegram ID raqamingizni bilish |

## Fayllar

```
stroy_bot/
├── main.py         # Telegram handlerlar, zayavkani adminga yuborish
├── ai_agent.py     # Claude bilan suhbat, mijoz tarixi, zayavka vositasi
├── prompts.py      # Sotuvchining xarakteri va qoidalari
├── store_info.md   # Do'kon ma'lumotlari (egasi o'zi to'ldiradi)
├── config.py       # .env sozlamalari
└── .env.example
```

## Hozirgi cheklovlar

- Suhbat tarixi xotirada saqlanadi, bot qayta ishga tushsa tozalanadi.
- Ovozli xabarlarni hali tushunmaydi (mijozdan yozib yuborishni so'raydi).

## Keyingi bosqichlar

1. Mahsulotlar katalogi: nom, rasm, narx, qoldiq (bazaga va admin panelga), Excel orqali import.
2. Agentga `mahsulot_qidirish` vositasini qo'shish: narxlarni faqat bazadan oladi.
3. Mahsulot rasmlarini mijozga yuborish.
4. Savat va buyurtma, yetkazib berish narxini hisoblash.
5. Ovozli xabarlarni matnga o'girish.
6. Suhbatlar va zayavkalarni bazada saqlash, statistika.

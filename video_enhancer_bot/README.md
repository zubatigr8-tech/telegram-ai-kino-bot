# 🎞 Jonli Kadr — video sifatini oshiruvchi Telegram bot

Telegram: **@JonliKadrBot**

Obunachi eski yoki sifati past videoni (masalan, 15 yil oldingi kinodan lavha) yuboradi —
bot uni kattalashtiradi, shovqindan tozalaydi, ranglarini yorqin qiladi va tiniqlashtirib qaytaradi.

## Foydalanuvchi uchun oqim

1. `/start` → bot nima qila olishini tushuntiradi
2. Video yuboriladi (oddiy video, fayl, GIF yoki dumaloq video)
3. Uslub tanlanadi:
   - **✨ Avtomatik (tavsiya)** — muvozanatli rang + tiniqlik
   - **🌈 Juda yorqin ranglar** — "hozir olingandek" to'q, jonli ranglar
   - **🎞 Tabiiy** — ranglar deyarli o'zgarmaydi, faqat aniqlik va tiniqlik
4. Bot navbat va foizni ko'rsatib turadi (`▰▰▰▰▱▱▱ 57%`), tayyor bo'lgach videoni qaytaradi

## Video bilan nima qilinadi

| Bosqich | Nima uchun |
|---|---|
| Interleysni olib tashlash (`bwdif`) | Eski TV/DVD yozuvlaridagi "taroq" chiziqlar |
| Shovqinni tozalash (`hqdn3d`) | Donador, "qor yog'ayotgan"dek tasvir |
| Kattalashtirish (`lanczos` yoki **AI**) | 360p/480p → 1080p (yoki 4K) |
| Debanding | Siqilgan videodagi osmon/devorlardagi "zinapoya" gradientlar |
| Avtomatik rang tiklash (`normalize`) | Eski plyonkaning sarg'ish/ko'kish tusi va xiraligini olib tashlash |
| Kontrast, gamma, to'yinganlik, vibrance | Xira, "yuvilgan" ranglarni jonlantirish |
| Tiniqlashtirish (`cas`) | Yumshoq, loyqa chegaralarni aniqlashtirish |

## Uch xil "dvigatel" (`ENGINE`)

| ENGINE | Sifat | Tezlik | Talab | Narx |
|---|---|---|---|---|
| `ffmpeg` (standart) | Yaxshi — ranglar va tiniqlik sezilarli yaxshilanadi | 1 daqiqalik video ≈ 1–3 daq | Istalgan server | Bepul |
| `realesrgan` | **Eng yaxshi** — AI yo'qolgan tafsilotlarni "qayta chizadi" | GPU bilan tez, CPU'da juda sekin | NVIDIA/AMD GPU (Vulkan) | Bepul |
| `replicate` | **Eng yaxshi** (Topaz Video AI va b.) | Bulutda | Faqat internet | Pullik (har video uchun) |

> ⚠️ Halol aytganda: hech bir texnologiya 15 yillik videoni *aynan* bugungi 4K kamerada
> olingandek qila olmaydi — yo'qolgan ma'lumotni to'liq tiklab bo'lmaydi. Lekin AI
> (`realesrgan`/`replicate`) bilan natija juda katta farq qiladi: yuzlar, matn, chegaralar
> aniq bo'ladi. `ffmpeg` rejimi esa asosan ranglar, shovqin va o'lchamni yaxshilaydi.

## O'rnatish

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r video_enhancer_bot/requirements.txt
```

**ffmpeg** o'rnatilgan bo'lishi shart:
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: `winget install ffmpeg` (yoki ffmpeg.org'dan yuklab, PATH'ga qo'shing)
- macOS: `brew install ffmpeg`

## Sozlash

```bash
cp video_enhancer_bot/.env.example video_enhancer_bot/.env
```

Eng kamida `BOT_TOKEN` kiritiladi. Qolgan sozlamalar `.env.example`da izohlangan.

### @BotFather'da botni yaratish

1. [@BotFather](https://t.me/BotFather) → `/newbot`
2. Nomi: `🎞 Jonli Kadr`
3. Username: `JonliKadrBot` (band bo'lsa: `JonliKadr_uzbot`)
4. Berilgan tokenni `.env`dagi `BOT_TOKEN`ga qo'ying (kino bot tokenini ishlatmang)
5. `/setdescription` — bot ochilganda "Start" tugmasi ustida chiqadigan matn:
   ```
   🎞 Eski videolaringizga yangi hayot bering!

   Sifati past, xira yoki eski kinodan lavha yuboring — men uni:
   🔍 HD / Full HD ga kattalashtiraman
   🧹 shovqindan tozalayman
   🌈 ranglarini yorqin va jonli qilaman
   ✨ tiniqlashtiraman

   Boshlash uchun «Start» ni bosing 👇
   ```
6. `/setabouttext` — bot profilidagi qisqa matn (120 belgigacha):
   ```
   Eski va sifati past videolarni HD, yorqin va tiniq qilib beraman 🎞✨
   ```
7. `/setuserpic` — bot rasmi (masalan, kinoplyonka + sehrli tayoqcha tasviri)

## Ishga tushirish

Repozitoriy ildizidan:

```bash
python -m video_enhancer_bot.main
```

Docker orqali:

```bash
docker build -f video_enhancer_bot/Dockerfile -t video-enhancer .
docker run --env-file video_enhancer_bot/.env video-enhancer
```

## AI rejimini yoqish

### Real-ESRGAN (o'z serveringizda, GPU bilan)

1. [Real-ESRGAN-ncnn-vulkan relizlari](https://github.com/xinntao/Real-ESRGAN/releases)dan
   operatsion tizimingizga mos arxivni yuklab oching (modellar ichida bor).
2. `.env`:
   ```
   ENGINE=realesrgan
   REALESRGAN_BIN=/yo'l/realesrgan-ncnn-vulkan
   REALESRGAN_MODEL=realesrgan-x4plus   # tezroq variant: realesr-animevideov3 + SCALE=2
   REALESRGAN_SCALE=4
   ```
Bot videoni kadrlarga ajratadi, har bir kadrni AI bilan kattalashtiradi, so'ng ovoz bilan
qayta yig'ib, rang/tiniqlik beradi.

### Replicate (bulutda, server kuchi kerak emas)

1. [replicate.com](https://replicate.com) → API token oling, hisobga pul qo'ying.
2. `.env`:
   ```
   ENGINE=replicate
   REPLICATE_API_TOKEN=r8_...
   REPLICATE_MODEL=topazlabs/video-upscale
   REPLICATE_VIDEO_FIELD=video
   REPLICATE_EXTRA_INPUT={"target_resolution": "1080p"}
   ```
Boshqa video-upscale model tanlasangiz, uning sahifasidagi **API** bo'limidan video
maydoni nomi (`REPLICATE_VIDEO_FIELD`) va qo'shimcha parametrlarini (`REPLICATE_EXTRA_INPUT`) ko'chiring.

## Fayl hajmi cheklovlari

Oddiy Telegram Bot API: bot **20 MB** gacha videoni yuklab oladi va **50 MB** gacha yuboradi.
Bot natijani avtomatik ravishda 50 MB ga sig'adigan bitreyt bilan kodlaydi. Kattaroq videolar
(2 GB gacha) kerak bo'lsa, [Local Bot API server](https://github.com/tdlib/telegram-bot-api)
ishga tushiring va `.env`da `TELEGRAM_API_URL` + `TELEGRAM_API_LOCAL=true` ni yoqing.

## Tuzilma

```
video_enhancer_bot/
├── main.py          # ishga tushirish
├── handlers.py      # /start, video qabul qilish, uslub tanlash
├── jobs.py          # navbat, progress, natijani yuborish
├── media.py         # ffprobe, filtrlar zanjiri, uslublar (PRESETS), kodlash
├── engines/
│   ├── ffmpeg.py      # klassik filtrlar
│   ├── realesrgan.py  # lokal AI
│   └── replicate.py   # bulutli AI
├── config.py
├── Dockerfile
└── .env.example
```

## Kengaytirish g'oyalari

- Qora-oq videolarni avtomatik bo'yash (DeOldify kabi colorization modeli)
- FPS'ni 60 ga oshirish (RIFE — kadrlar orasini AI bilan to'ldirish)
- Yuzlarni tiklash (GFPGAN / CodeFormer)
- Kanal obunasi va kunlik limit (kino botdagi `SubscriptionMiddleware` kabi)

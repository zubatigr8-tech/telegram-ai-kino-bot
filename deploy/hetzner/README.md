# Hetzner'ga ko'chish (zaxira reja)

Railway ishlamay qolsa, ikkala botni (kino bot va Video Downloader) bitta Hetzner serverida
24/7 ishlatish uchun qo'llanma. Server oyiga taxminan €4–6 turadi, ikkala botga yetadi.

## 1. Server sotib olish

1. **hetzner.com/cloud** → **Sign up**. Ro'yxatdan o'tishda pasport/ID tasdiqlashni so'rashi mumkin.
   To'lov: Visa/Mastercard yoki PayPal.
2. **Cloud Console** → **New project** (masalan, `botlar`) → **Add Server**:
   - **Location**: Helsinki, Nuremberg yoki Falkenstein (istalgani)
   - **Image**: **Ubuntu 24.04**
   - **Type**: **Shared vCPU → x86 (Intel/AMD)**, eng arzoni (2 vCPU, 4 GB RAM).
     ARM (Ampere) emas — ba'zi kutubxonalar ARM'da o'rnatilmasligi mumkin.
   - **Networking**: **Public IPv4** belgilangan bo'lsin (Telegram va Instagram uchun kerak)
   - **SSH keys**: bo'sh qoldirsangiz, root paroli emailga keladi
   - **Name**: `botlar` → **Create & Buy now**
3. Server yaratilgach, uning **IP manzilini** (masalan `65.21.xx.xx`) nusxalab oling.

## 2. Serverga ulanish (Windows)

**PowerShell**'ni oching va yozing (IP o'rniga o'zingiznikini qo'ying):

```
ssh root@65.21.xx.xx
```

- Birinchi marta `Are you sure you want to continue connecting?` deb so'raydi → `yes` yozing.
- Parolni so'raydi → emaildagi parolni qo'ying (yozayotganda ko'rinmaydi, bu normal) → Enter.
- Birinchi kirishda yangi parol o'ylab topishni so'rashi mumkin.

## 3. Tokenlarni tayyorlab qo'ying

Skript har bir bot tokenini so'raydi. Ularni **@BotFather → /mybots → bot → API Token** dan oling.
Admin ID — sizniki: botga `/myid` yuborib bilasiz.

> ⚠️ O'rnatishdan **oldin** kompyuterdagi botni to'xtating (terminalda `Ctrl + C`).
> Bitta token bilan ikki joyda ishlagan bot javob bermay qoladi.

## 4. O'rnatish — 2 ta buyruq

Serverda (ssh ichida):

```
curl -fsSL https://raw.githubusercontent.com/zubatigr8-tech/telegram-ai-kino-bot/claude/amazing-archimedes-bh1qbb/deploy/hetzner/setup.sh -o setup.sh
bash setup.sh videobot
```

- `bash setup.sh videobot` — **faqat Video Downloader**.
- `bash setup.sh` — **ikkala bot**. Kino botni faqat uning bazasi Railway'dan
  ko'chirilgandan keyin o'rnating (5-bo'lim), aks holda u bo'sh bazadan boshlanadi.

O'rnatish 5–10 daqiqa davom etadi. Oxirida shunday chiqishi kerak:

```
✅ videobot ishlayapti
```

Shundan keyin Telegram'da botga `/start` yozib tekshiring. Instagram ovozi uchun cookie
faylini botga qaytadan yuboring (`/cookies` buyrug'i bilan holatini ko'rasiz).

## 5. Kino bot bazasini ko'chirish

Kino botning kinolari, kodlari va foydalanuvchilari Railway diskida (`/data/bot_database.db`).
Uni olib chiqish uchun Railway'ga kira olishimiz kerak — Railway ochilganda bu qadamni birga qilamiz.
Fayl serverga tushgach:

```
systemctl stop kinobot
cp bot_database.db /opt/bots/kinobot/data/bot_database.db
chown bots:bots /opt/bots/kinobot/data/bot_database.db
systemctl start kinobot
```

## Kundalik buyruqlar

| Nima qilish | Buyruq |
|---|---|
| Bot ishlayaptimi | `systemctl status videobot` |
| Loglarni jonli ko'rish (chiqish: `Ctrl + C`) | `journalctl -u videobot -f` |
| Botni qayta ishga tushirish | `systemctl restart videobot` |
| Kodni GitHub'dan yangilash | `bash /opt/bots/videobot/app/deploy/hetzner/update.sh` |
| Admin panel parollari | `cat /root/bot-parollar.txt` |
| Tokenni o'zgartirish | `nano /opt/bots/videobot/app/.env` → saqlash `Ctrl+O`, Enter, chiqish `Ctrl+X` → `systemctl restart videobot` |

Kino bot uchun `videobot` o'rniga `kinobot` yozing.

Admin panellar: kino bot — `http://SERVER_IP:8000`, Video Downloader — `http://SERVER_IP:8001`
(login `admin`, parol — `/root/bot-parollar.txt` faylida, skript tasodifiy kuchli parol yaratadi).

## Muhim

- Server qayta yuklansa yoki bot xato bilan to'xtasa, botlar **avtomatik** qayta ishga tushadi.
- Ma'lumotlar `/opt/bots/<bot>/data/` papkasida saqlanadi, kino bot u yerda har 6 soatda zaxira oladi.
- Instagram/YouTube serverlarni (datacenter IP) Railway'dagi kabi cheklashi mumkin —
  cookie'lar bu yerda ham kerak.
- Railway'da to'lov o'tib, botlar u yerda ham ishga tushsa — bir joydagisini to'xtating:
  `systemctl stop videobot && systemctl disable videobot`.

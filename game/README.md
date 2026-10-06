# 🥊 Turon MMA

Android uchun aralash jang san'ati (MMA) o'yini. Godot 4.3 dvigatelida yozilgan.

## 1-bosqich: jang mexanikasi (hozirgi versiya)

- Sakkiz burchakli ring, ikki jangchi, yon tomondan kuzatuvchi kamera
- Zarbalar: jab, kross, xuk, apperkot, past tepki, baland tepki
- Blok, qochish, chidamlilik (stamina) va sog'lik
- Kontr-zarba (raqib zarbaga tayyorlanayotganda urilsa +35% zarar), himoyani sindirish
- Bot raqib: masofani ushlaydi, kombinatsiyalar uradi, blok qo'yadi va qochadi
- 3 raund × 90 soniya, nokaut yoki hakamlar qarori (10 balli tizim)

## Boshqaruv

| Harakat | Telefon | Klaviatura |
|---|---|---|
| Yurish | Chap tomondagi joystik | W A S D / strelkalar |
| Jab / Kross | JAB / KROSS | J / K |
| Xuk / Apperkot | XUK / APPERKOT | L / U |
| Past / Baland tepki | PAST TEPKI / BALAND TEPKI | I / O |
| Blok (bosib turish) | BLOK | Probel |
| Qochish | QOCHISH | Shift |

## APK yig'ish

`game/` papkasidagi har bir o'zgarishda GitHub Actions
(`.github/workflows/turon-mma-android.yml`) avtomatik ravishda bot-vs-bot sinovini
o'tkazadi va debug APK yig'adi. APK Actions sahifasidagi run ichida
**turon-mma-apk** artefakti sifatida yuklab olinadi.

Lokal ishga tushirish:

```bash
godot --path game                       # o'yinni ochish
godot --headless --path game --fixed-fps 60 -s res://tests/sim_test.gd   # avtomatik sinov
```

## Tuzilma

```
game/
├── project.godot
├── export_presets.cfg       # Android eksport (uz.turonmma.game)
├── scenes/main.tscn
├── scripts/
│   ├── main.gd              # ring, kamera, raundlar, hakamlar
│   ├── fighter.gd           # jangchi: tana, zarbalar, blok, nokaut
│   ├── ai_controller.gd     # bot
│   ├── player_controller.gd # o'yinchi boshqaruvi
│   ├── hud.gd               # interfeys
│   ├── touch_button.gd      # sensorli tugma
│   └── virtual_joystick.gd  # joystik
└── tests/
    ├── sim_test.gd          # bot-vs-bot to'liq jang sinovi
    └── screenshot.gd        # vizual tekshiruv uchun skrinshot
```

## Keyingi bosqichlar

2. Jangchi profili va garderob (qo'lqop, shortik, kapa)
3. Do'kon: tanga va olmos, kunlik bonuslar
4. Mavsumiy pass va sandiqlar
5. Google Play Billing, AdMob va Play Market'ga chiqarish

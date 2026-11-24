# Rise of the Ninja 2.2

Android (arm64) versiyasi. O'yin dvigateli NarutoSenki-V2 manba kodiga asoslangan, ustiga Rise of the Ninja ko'rinishi, qahramonlari va Wi-Fi jang qo'shilgan.

## Imkoniyatlar
- 61 qahramon: V2 qahramonlari, alohida tanlanadigan shakllar (Sage/Rikudo Naruto, Nagato, Immortal Sasuke, Sage Jiraiya) va Rise of the Ninja'ning 20 qahramoni (Killer Bee, Madara, Hashirama...).
- Rejimlar: 1 VS 1, 2 VS 2, 3 VS 3.
- Online Battle: bitta Wi-Fi tarmog'ida 2–6 o'yinchi, bo'sh o'rinlarni botlar egallaydi.

## Tuzilishi
- `engine/` — cocos2d-x 2.2 dvigateli va o'yin kodi (`engine/projects/NarutoSenki/Classes`, `lua`, `Resources`).
  - `Classes/Mp/` — Wi-Fi jang (lockstep).
  - `Classes/Data/Skins.h` — Rise of the Ninja qahramonlari ro'yxati.
- `app/` — Android ilovasi va build skripti.
  - `overlay/` — Rise of the Ninja rasmlari, sprite'lari va ovozlari (tayyor holda).
  - `extra/` — qo'shimcha rasmlar.
  - `tools/`, `rotn_assets.py` — `overlay/` ni asl Rise of the Ninja fayllaridan qayta yaratish skriptlari.

## Yig'ish (macOS yoki Linux)
Kerak: Android SDK (build-tools, platform, NDK), JDK, Python 3 va Pillow (`pip install pillow`).

```
cd app
./build.sh        # -> app/build/RiseOfTheNinja-2.2-arm64.apk
```

Ixtiyoriy sozlamalar:
- `KEYSTORE=<fayl>` (va `KEYSTORE_PASS`) — imzo kaliti. Ko'rsatilmasa, `app/build-key/` da yangi kalit yaratiladi. Boshqa kalit bilan imzolangan APK eski o'rnatilgan versiya ustidan yangilanmaydi.
- `app/music/Audio/Music/` — menyu, tanlash va jang uchun qo'shimcha musiqa (repozitoriyda yo'q).
- `ROTN_ASSETS=<papka>` — asl Rise of the Ninja fayllari berilsa, `app/overlay` qayta yaratiladi.

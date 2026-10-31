# FaceID Next — yangi avlod yuz orqali autentifikatsiya

Kompyuteringizda **to'liq oflayn** ishlaydigan biometrik kirish tizimi. Yuz
tanib olish, soxta yuzni aniqlash (rasm, ekran, video), soxta video oqimidan
himoya va shifrlangan saqlash bir dasturda jamlangan.

> 2.0 versiya — 2024-yildagi o'quv prototipi (`legacy/`) asosida noldan qayta yozilgan.

## Asosiy imkoniyatlar

| | |
|---|---|
| 🧠 **Aniq tanib olish** | ArcFace R50 (WebFace600K) — 512 o'lchamli vektor, 1:1 tasdiqlash va 1:N identifikatsiya |
| 🛡 **Ikki qatlamli liveness** | Passiv: MiniFASNet ansambli (rasm/ekranni bitta kadrdan aniqlaydi). Aktiv: har safar tasodifiy tanlanadigan harakatlar (ko'z qisish, jilmayish, og'iz ochish, bosh burish) |
| 🎥 **Injection himoyasi** | Virtual kameralarni bloklash (OBS, ManyCam, DroidCam...), muzlagan va shovqinsiz (sintetik) oqimni aniqlash |
| 👤 **Uzluksizlik nazorati** | Tekshiruv davomida kadrda faqat bitta yuz; yuz "sakrashi" yoki almashishi aniqlanadi |
| 📸 **Sifat nazorati** | ISO/IEC 29794-5 ga asoslangan baho: o'lcham, o'tkirlik, yorug'lik, kontrast, bosh holati |
| 🔐 **Shifrlangan saqlash** | Rasmlar saqlanmaydi. Shablonlar AES-256-GCM bilan shifrlanadi, kalit Windows DPAPI (Credential Manager) da |
| 📜 **Audit jurnali** | HMAC xesh-zanjir — har qanday o'zgartirish yoki o'chirish aniqlanadi |
| 🚫 **Bruteforce himoyasi** | Foydalanuvchi va umumiy darajada eksponensial bloklash |
| 🌐 **3 til** | O'zbek, rus, ingliz; ovozli ko'rsatmalar |

## Standartlarga moslik

Tizim quyidagi standartlar **asosida loyihalangan** va ichki sinovdan o'tkazilgan.
Rasmiy sertifikat (masalan, iBeta yoki FIDO) faqat akkreditatsiyalangan laboratoriyada olinadi.

| Soha | Standart | Amalga oshirilishi |
|---|---|---|
| Soxta yuzga qarshi himoya (PAD) | ISO/IEC 30107-1/-3 | Passiv + aktiv liveness; `evaluate` buyrug'i APCER/BPCER ni hisoblaydi |
| Injection hujumlari | CEN/TS 18099 | Virtual kamera, muzlagan/sintetik oqim va o'lcham o'zgarishi tekshiruvlari |
| Tasvir sifati | ISO/IEC 29794-5:2025 | `faceid/core/quality.py` |
| Tanib olish aniqligi | ISO/IEC 19795-1 | `evaluate` — FMR, FNMR, EER va berilgan FMR uchun chegara |
| Shablon himoyasi | ISO/IEC 24745 | AES-256-GCM, AAD bilan yozuvga bog'lash, xom tasvirlar saqlanmaydi |
| Shaxsiy ma'lumotlar | O'zR ZRU-547, GDPR 9-modda | Aniq rozilik, ma'lumotlar faqat shu kompyuterda, to'liq o'chirish imkoniyati |
| Ilova xavfsizligi | OWASP ASVS 5.0 | Argon2id parol, bloklash, audit, model fayllari SHA-256 bilan tekshiriladi, telemetriya o'chirilgan |

## Qanday ishlaydi

```
Kamera ──► Injection monitori ──► SCRFD (yuz + 5 nuqta) ──► Sifat bahosi
                                         │
                                         ├─► MediaPipe (478 nuqta, mimika, bosh holati) ──► Tasodifiy challenge
                                         ├─► MiniFASNet ×2 (passiv PAD, har 2-kadr)
                                         └─► ArcFace (boshida va oxirida) ──► Uzluksizlik + solishtirish
                                                                                   │
                                                  Barcha shartlar bajarildi? ◄─────┘
```

Kirish faqat **barcha** shartlar bajarilganda ruxsat etiladi:

1. Injection signallari yo'q.
2. Butun sessiya davomida kadrda bitta yuz bo'lgan va u uzilmagan.
3. Passiv PAD o'rtachasi chegaradan yuqori.
4. Tasodifiy harakatlar vaqtida bajarilgan.
5. Boshlang'ich va yakuniy kadrdagi shaxs bir xil.
6. Shaxs ro'yxatdagi foydalanuvchiga mos keladi.

## O'rnatish (Windows)

1. [python.org](https://www.python.org/downloads/) dan **Python 3.12 yoki 3.13** ni o'rnating.
   O'rnatishda "Add python.exe to PATH" belgisini qo'ying.
2. Repozitoriyni yuklab oling (yoki ZIP qilib oling) va papkani oching.
3. **`install.bat`** ni ikki marta bosing. U virtual muhit yaratadi, kutubxonalarni o'rnatadi
   va modellarni (~290 MB, bir marta) yuklab oladi.
4. **`run.bat`** — ilovani ishga tushiradi.

Linux/macOS uchun `./install.sh` va `./run.sh` dan foydalaning.

## Foydalanish

1. **Ro'yxatdan o'tish.** Ismingizni kiriting va rozilik bering. Keyin ko'rsatmalarni bajaring:
   tasodifiy harakatlar, so'ng turli burchaklardan 5 ta namuna olinadi.
   Birinchi foydalanuvchi **administrator** bo'ladi va boshqaruv paneli uchun parol o'rnatadi.
   Keyingi foydalanuvchilarni qo'shish uchun administrator paroli talab qilinadi.
2. **Yuz orqali kirish.** Kameraga qarang va ekrandagi 3 ta tasodifiy harakatni bajaring.
   Odatda bu 3–6 soniya oladi.
3. **Boshqaruv paneli:**
   - foydalanuvchilarni ko'rish va o'chirish;
   - audit jurnali va uning yaxlitligini ko'rish;
   - sozlamalar (kamera, chegaralar, challenge soni);
   - barcha ma'lumotlarni o'chirish.

### Yaxshi natija uchun maslahatlar

- Yuzingiz oldidan bir tekis yoritilgan bo'lsin, orqangizda yorqin deraza bo'lmasin.
- Kameradan 40–70 sm masofada o'tiring.
- "Chapga burilish" teskari ishlasa, sozlamalarda **"Kamera tasvirni o'zi ko'zgulaydi"** ni yoqing.
- Ovozli ko'rsatmalar Windows'dagi ovozlardan foydalanadi. O'zbek tili uchun Windows'da ovoz yo'q,
  shuning uchun bu tilda faqat ekrandagi matn ko'rsatiladi. Rus yoki ingliz tilida ovoz ishlaydi.

## Buyruq qatori

```bash
python -m faceid doctor
```

`doctor` — diagnostika: modellar, kameralar (virtual kameralar belgilanadi), kalit ombori,
audit zanjiri va tezlik o'lchovi.

```bash
python -m faceid verify
```

`verify` — GUI'siz kirish. JSON chiqaradi, chiqish kodi 0 bo'lsa muvaffaqiyat.
Keyinchalik boshqa tizimlar bilan integratsiya qilish uchun mo'ljallangan.

```bash
python -m faceid verify --user Alyorbek --preview
```

Bu 1:1 rejim: faqat ko'rsatilgan foydalanuvchi tekshiriladi va jarayon OpenCV oynasida ko'rsatiladi.

```bash
python -m faceid users
```

```bash
python -m faceid audit
```

```bash
python -m faceid evaluate --root D:\dataset\faces
```

Tanib olish ko'rsatkichlari: FMR, FNMR, EER. Papkada har bir shaxs uchun alohida papka bo'lishi kerak
(yoki LFW formatidan `--pairs` bilan foydalaniladi).

```bash
python -m faceid evaluate --pad-real D:\pad\real --pad-attack D:\pad\attack
```

PAD ko'rsatkichlari: APCER va BPCER. O'z kamerangiz bilan olingan haqiqiy yuz va hujum
(telefon ekrani, bosma rasm) suratlaridan foydalaning.

`verify` natijasiga misol:

```json
{"success": true, "reason": "", "user": "Alyorbek", "score": 0.7412, "liveness": 0.962}
```

## Ma'lumotlar va maxfiylik

- Barcha ma'lumotlar `%LOCALAPPDATA%\FaceIDNext` papkasida saqlanadi. Internetga hech narsa yuborilmaydi
  (ONNX Runtime telemetriyasi ham o'chirilgan).
- **Rasmlar saqlanmaydi.** Faqat 512 o'lchamli vektorlar saqlanadi, ular AES-256-GCM bilan shifrlanadi.
  Kalit Windows Credential Manager'da (DPAPI) turadi, ya'ni boshqa Windows foydalanuvchisi yoki boshqa
  kompyuter bazani ocha olmaydi.
- Shifrlangan shablonni boshqa foydalanuvchi yozuviga ko'chirib bo'lmaydi (AAD bog'lashi).
- Foydalanuvchini o'chirish uning barcha shablonlarini butunlay yo'q qiladi (`secure_delete`).

## Cheklovlar

Tizim haqidagi ochiq ma'lumot:

- Oddiy RGB web-kamera ishlatiladi. Chuqurlik yoki infraqizil (IR) datchik yo'q, shuning uchun
  Apple Face ID yoki Windows Hello IR kameralari darajasidagi 3D himoya mumkin emas.
  Sifatli silikon 3D niqob yoki apparat darajasidagi video almashtirish (HDMI capture) nazariy
  jihatdan himoyani chetlab o'tishi mumkin.
- Chegaralar (`match_threshold` = 0,45, `passive_threshold` = 0,70) umumiy qiymatlar.
  Ularni o'z kamerangiz va yoritishingiz uchun `evaluate` bilan kalibrlash tavsiya etiladi.
- Tanib olish modellari (InsightFace `buffalo_l`) faqat **notijorat/ilmiy** foydalanish uchun litsenziyalangan.
  Tijoriy foydalanish uchun litsenziyasi ochiq model bilan almashtirish kerak (`faceid/models.py`).

## Loyiha tuzilmasi

```
faceid/
  core/        detektor (SCRFD), tekislash, embedding (ArcFace), sifat, solishtirish
  liveness/    MediaPipe landmarklar, passiv PAD, challenge, injection monitori
  storage/     AES-GCM shifrlash, kalit ombori, SQLite + audit xesh-zanjiri
  services/    ilova mantiqi: admin, bloklash, ro'yxatdan o'tish
  gui/         PySide6 interfeysi
  session.py   biometrik sessiya holat mashinasi
  engine.py    modellarni yuklash
  evaluation.py FMR/FNMR, APCER/BPCER
assets/models/ MiniFASNet ONNX (Apache 2.0)
tools/         MiniFASNet → ONNX konvertatsiyasi (ishlab chiquvchi uchun)
tests/         unit va integratsiya testlari
legacy/        avvalgi (1.0) versiya
docs/          tahdidlar modeli
```

## Testlar

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```

70 ga yaqin test bor. Unit testlar modellarsiz ishlaydi. Integratsiya testlari yuklangan
modellar bilan ishga tushadi.

## Muallif

**To'xtasinov Alyorbek** — TATU Nurafshon filiali, 730-22-guruh.

## Litsenziyalar

Uchinchi tomon modellari va ularning litsenziyalari: [`assets/models/README.md`](assets/models/README.md).

# 👁 Face ID orqali kirish va hayotiylikni tekshirish tizimi

Bu loyiha foydalanuvchining yuzini aniqlash va hayotiyligini (tirikligini) tekshirish orqali xavfsiz kirish tizimini yaratishga qaratilgan. Loyihada **OpenCV**, **Mediapipe**, **Face Recognition**, va **Tkinter** texnologiyalari qo‘llangan.

## 📌 Asosiy imkoniyatlar

- Real vaqt rejimida yuzni aniqlash
- Yuz harakatlarini aniqlash orqali hayotiylikni tekshirish (chapga, o‘ngga, to‘g‘ri qarash)
- Yuzni oldindan o‘rgatilgan yuzlar bilan taqqoslab aniqlash
- TTS (Text-to-Speech) orqali og‘zaki yo‘riqnoma
- Tkinter interfeysi bilan qulay GUI

## ⚙ Texnik tavsif

- **Python 3.8+**
- **Kutubxonalar**: `opencv-python`, `mediapipe`, `face_recognition`, `Pillow`, `pyttsx3`, `tkinter`
- **Ma’lumotlar bazasi**: `SQLite` (kelgusida)

## 🚀 Ishga tushirish

1. `requirements.txt` orqali kutubxonalarni o‘rnating:
   ```bash
   pip install -r requirements.txt
   ```

2. `Alyorbek.jpg` faylini loyihaga joylashtiring (foydalanuvchi yuz tasviri).

3. Asosiy dasturni ishga tushiring:
   ```bash
   python main.py
   ```

## 🧠 Texnologiyalar

- **OpenCV** – kompyuter ko‘rish uchun asosiy kutubxona
- **Mediapipe** – yuz landshaftlarini aniqlash va liveness
- **Face Recognition** – yuzni o‘rganish va solishtirish
- **Tkinter** – foydalanuvchi interfeysi yaratish

## 📄 Muallif

**To‘xtasinov Alyorbek**  
TATU Nurafshon filiali, 730-22-guruh talabasi

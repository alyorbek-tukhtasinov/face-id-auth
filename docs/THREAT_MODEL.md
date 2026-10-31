# Tahdidlar modeli

Tizim — bitta kompyuterda ishlaydigan lokal biometrik autentifikatsiya.
Himoya qilinadigan aktivlar: foydalanuvchilarning biometrik shablonlari va
"faqat ro'yxatdagi tirik shaxs kira oladi" degan kafolat.

| # | Hujum | Himoya | Qoldiq xavf |
|---|---|---|---|
| T1 | Bosma rasm kamera oldida | Passiv PAD (moire, rang, tekstura); aktiv challenge — rasm jilmaya olmaydi, ko'zini qisa olmaydi | Past |
| T2 | Telefon yoki monitor ekranida rasm yoki video (replay) | Passiv PAD; tasodifiy challenge — oldindan yozilgan video ketma-ketlikni bilmaydi; PAD aniq soxtalikda sessiyani darhol to'xtatadi | Past |
| T3 | Yuzga taqiladigan qog'oz niqob yoki ko'z teshikli rasm | Ham bosh burish (3D), ham mimika talab qilinadi; passiv PAD | O'rta |
| T4 | Sifatli silikon/lateks 3D niqob | Passiv PAD qisman aniqlaydi | **Yuqori** — chuqurlik/IR datchik kerak |
| T5 | Virtual kamera orqali deepfake yoki video (injection) | Virtual kamera nomlari bloklanadi; muzlagan/sintetik oqim aniqlanadi; real vaqtdagi challenge | O'rta — USB qurilmani apparat darajasida almashtirish aniqlanmaydi |
| T6 | Tekshiruv paytida yuzni almashtirish (avval egasi, keyin boshqasi) | Har kadrda bitta yuz; yuz sakrashi aniqlanadi; boshlang'ich va yakuniy embedding mos kelishi shart | Past |
| T7 | Ko'p urinish bilan "taxmin qilish" | Foydalanuvchi va umumiy darajada eksponensial bloklash; audit | Past |
| T8 | Baza faylini o'g'irlash | AES-256-GCM; kalit DPAPI'da (faqat shu Windows foydalanuvchisi); rasmlar yo'q | Past (administrator huquqli zararli dastur bundan mustasno) |
| T9 | Shablonni boshqa yozuvga ko'chirish | AAD = foydalanuvchi va shablon ID | Past |
| T10 | Audit jurnalini o'zgartirish yoki o'chirish | HMAC xesh-zanjir; `audit` buyrug'i va panel tekshiradi | Past |
| T11 | O'zini ro'yxatga qo'shib olish | Birinchi foydalanuvchidan keyin administrator paroli (Argon2id) talab qilinadi | Past |
| T12 | Soxta yoki buzilgan model fayli | Har bir model SHA-256 bilan tekshiriladi; PyTorch pickle yuklanmaydi (ONNX) | Past |
| T13 | Telemetriya orqali ma'lumot sizishi | To'liq oflayn; ONNX Runtime telemetriyasi o'chirilgan | Past |

## Tizimdan tashqarida

- Administrator yoki SYSTEM huquqiga ega zararli dastur: u xotiradagi kalitni o'qishi
  yoki dasturni almashtirishi mumkin. Bu holda OS darajasidagi himoya (masalan, Windows Hello
  ESS, TPM) kerak bo'ladi.
- Fizik majburlash (egasini kameraga qaratib qo'yish).

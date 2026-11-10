# Telegram Botlar Tizimi (Admin & User Bots)

Ushbu ekotizim ikkita o'zaro bog'langan botdan iborat:

1. **Admin Bot (@iskndrAcc_Bot):**
   - Faqat siz (admin) uchun maxsus boshqaruv paneli.
   - Kanallarga o'yin va ilovalarni chiroyli rasm, ta'rif, janr, versiya, mod ma'lumotlari va APK fayli bilan joylash (rasmdagidek shablon asosida).
   - Foydalanuvchilar a'zo bo'lishi shart bo'lgan majburiy homiy kanallarni qo'shish va o'chirish.
   - Botdagi barcha foydalanuvchilarga xabar tarqatish (Broadcast).
   - O'yinlar va ilovalarni ko'rish, o'chirish va umumiy statistika.

2. **Foydalanuvchilar Boti (@IskndrvGames_bot):**
   - Odamlar kiradigan asosiy platforma.
   - Majburiy obuna tekshiruvi: Agar foydalanuvchi Admin botda kiritilgan kanallarga a'zo bo'lmasa, botdan foydalana olmaydi. Xato bermasdan xavfsiz ishlaydi.
   - 🎮 O'yinlar (Janrlar bo'yicha saralangan yoki barchasi).
   - 📱 Ilovalar (Ruknlar bo'yicha).
   - 🔍 Qidiruv (Nom bo'yicha tezkor izlash).
   - Har bir o'yin kartochkasi va to'g'ridan-to'g'ri APK faylni yuklab olish imkoniyati.
   - ℹ️ Kanal va bot haqida ma'lumot.

---

### Ishga tushirish:
1. `start_bots.bat` faylini ikki marta bosing, yoki terminalda:
   ```bash
   cd "C:\Users\Shahriyor Iskandarov\.gemini\antigravity\scratch\telegram_bots_ecosystem"
   python run.py
   ```
2. Telegramda [@iskndrAcc_Bot](https://t.me/iskndrAcc_Bot) ga kirib `/start` bosing.
   Agar parol so'rasa: `/setadmin admin777` deb yuboring.
3. Kanalingizga ikkala botni ham **Administrator** qilib qo'shing (*"Post messages"* huquqini bering).

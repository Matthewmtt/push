import os
import asyncio
import random
import speech_recognition as sr
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackContext, filters
from pydub import AudioSegment
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
import time
import nest_asyncio
from transformers import pipeline
from deep_translator import GoogleTranslator  # تغییر به deep-translator

# بارگذاری تنظیمات از فایل .env
load_dotenv()

# دریافت توکن از متغیر محیطی
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ توکن ربات مشخص نشده است! لطفاً متغیر محیطی TELEGRAM_BOT_TOKEN را تنظیم کنید.")

# لیستی از نقل‌قول‌ها
quotes = [
    "زندگی همیشه سخت نیست، اما همیشه یک فرصت برای موفقیت وجود دارد. – مارک زاکربرگ",
    "موفقیت نتیجه تصمیمات درست است. تصمیمات درست نتیجه تجربیات است. و تجربیات نتیجه تصمیمات نادرست است. – تونی رابینز",
    "تنها راه برای انجام کار بزرگ این است که عاشق کاری که انجام می‌دهید باشید. – استیو جابز",
    "شجاعت این نیست که هیچ ترسی نداشته باشی، بلکه توانایی ایستادن در برابر ترس است. – نلسون ماندلا",
    "آنچه که ذهن انسان می‌تواند تصور کند، بدن انسان می‌تواند به دست آورد. – ناپلئون هیل"
]

# تابع برای ارسال نقل قول
async def send_quote(update: Update, context: CallbackContext):
    """ارسال نقل قول به صورت دوره‌ای"""
    quote = random.choice(quotes)
    await update.message.reply_text(f"💡 نقل قول: {quote}")

# تابع برای ترجمه متن به انگلیسی
async def translate_text_to_english(text: str, update: Update, context: CallbackContext):
    """ترجمه متن به انگلیسی با استفاده از deep-translator"""
    translator = GoogleTranslator(source='auto', target='en')
    translation = translator.translate(text)
    await update.message.reply_text(f"🌍 ترجمه به انگلیسی: {translation}")

# دریافت و پردازش پیام صوتی
async def handle_voice(update: Update, context: CallbackContext):
    """دریافت و تبدیل فایل صوتی به متن"""
    voice = update.message.voice

    if not voice:
        await update.message.reply_text("❌ هیچ فایلی ارسال نکردی! لطفاً یک فایل صوتی ارسال کن.")
        return

    file = await context.bot.get_file(voice.file_id)  # دریافت فایل صوتی
    file_path = f"{file.file_id}.ogg"
    wav_path = f"{file.file_id}.wav"

    try:
        await update.message.reply_text("🔄 دارم فایل صوتی رو پردازش می‌کنم... شاید چند دقیقه‌ای طول بکشه. 😅")

        # شروع تایمر
        start_time = time.time()

        # دانلود فایل صوتی
        await file.download_to_drive(file_path)

        # تبدیل ogg به wav
        audio = AudioSegment.from_file(file_path, format="ogg")

        # بررسی طول فایل صوتی و تقسیم آن به بخش‌های کوچکتر اگر نیاز باشد
        chunk_length_ms = 30000  # 30 seconds per chunk
        chunks = []

        for i in range(0, len(audio), chunk_length_ms):
            chunk = audio[i:i + chunk_length_ms]
            chunk_path = f"{file.file_id}_chunk_{i // chunk_length_ms}.wav"
            chunk.export(chunk_path, format="wav")
            chunks.append(chunk_path)

        # پردازش بخش‌ها
        text = ""
        scheduler = AsyncIOScheduler()
        job = scheduler.add_job(send_quote, 'interval', seconds=30, args=[update, context])

        scheduler.start()  # شروع ارسال نقل‌قول‌ها هر 30 ثانیه

        for chunk_path in chunks:
            recognizer = sr.Recognizer()
            with sr.AudioFile(chunk_path) as source:
                audio_data = recognizer.record(source)
                try:
                    text += recognizer.recognize_google(audio_data, language="fa-IR", show_all=False)
                except sr.UnknownValueError:
                    text += "[متنی یافت نشد]"
                except sr.RequestError:
                    text += "[خطا در پردازش]"

            # حذف فایل‌های موقت
            os.remove(chunk_path)

        # توقف ارسال نقل‌قول‌ها بعد از پردازش
        job.remove()

        await update.message.reply_text(f"📄 متن تبدیل شده:\n{text}")

        # ذخیره متن برای استفاده در ترجمه
        context.user_data['last_text'] = text

        # افزودن دکمه ترجمه به انگلیسی
        keyboard = [
            ["ترجمه به انگلیسی", "بازگشت به حالت اول"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "متن تبدیل شده است. می‌خواهید ترجمه کنید؟",
            reply_markup=reply_markup
        )

    except Exception as e:
        await update.message.reply_text(f"🚨 یه خطا پیش اومد: {e}")
    finally:
        # حذف فایل‌های موقت
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(wav_path):
            os.remove(wav_path)

# شروع مکالمه
async def start(update: Update, context: CallbackContext):
    """ارسال پیام خوشامدگویی به کاربر و کیبورد سفارشی"""
    keyboard = [
        ["ارسال ویس", "دریافت نقل‌قول"],
        ["کمک", "تنظیمات"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
       "سلام! 🌟 به دنیای جادویی تبدیل ویس به متن خوش اومدی! 🎤\nفقط کافیه ویس خودتو ارسال کنی، من متنش رو بهت میگم. آماده‌ای؟ 🙌\n\n\n\nCreated By: Matthew🐱‍👤",
       reply_markup=reply_markup
    )

# پاسخ به دکمه‌ها
async def handle_button(update: Update, context: CallbackContext):
    """پاسخ به دکمه‌های فشار داده شده"""
    text = update.message.text

    if text == "ارسال ویس":
        await update.message.reply_text("🎤 لطفاً فایل صوتی خود را ارسال کنید.")

    elif text == "دریافت نقل‌قول":
        await send_quote(update, context)

    elif text == "ترجمه به انگلیسی":
        # بررسی وجود متن ذخیره شده
        if 'last_text' in context.user_data:
            await translate_text_to_english(context.user_data['last_text'], update, context)
        else:
            await update.message.reply_text("❌ هنوز هیچ متنی برای ترجمه وجود ندارد. لطفاً ابتدا یک ویس ارسال کن.")

    elif text == "کمک":
        await update.message.reply_text("🆘 برای ارسال فایل صوتی، کافی است دکمه 'ارسال ویس' را فشار دهید.\nبرای دریافت نقل‌قول، دکمه 'دریافت نقل‌قول' را فشار دهید.\nبرای ترجمه به انگلیسی، ابتدا یک ویس ارسال کنید.")

    elif text == "تنظیمات":
        await update.message.reply_text("⚙️ تنظیمات ربات در حال حاضر در دسترس نیست.")
    
    elif text == "بازگشت به حالت اول":
        # بازگشت به حالت اولیه
        keyboard = [
            ["ارسال ویس", "دریافت نقل‌قول"],
            ["کمک", "تنظیمات"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "به حالت اول بازگشتید. 🌟 اکنون می‌توانید یک ویس ارسال کنید.",
            reply_markup=reply_markup
        )

async def main():
    """راه‌اندازی و اجرای ربات"""
    # ساخت اپلیکیشن
    app = Application.builder().token(TOKEN).build()

    # افزودن دستورات به ربات
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT, handle_button))

    # اجرای ربات
    print("🤖 ربات در حال اجرا است...")

    await app.run_polling()

# ✅ استفاده از nest_asyncio برای حل مشکل event loop
nest_asyncio.apply()  # اضافه کردن این خط

# ✅ اجرای ایمن در محیط‌هایی که event loop در حال اجرا است
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    if loop.is_running():
        print("⚠️ event loop در حال اجرا است، از nest_asyncio استفاده می‌شود.")
        loop.create_task(main())
    else:
        asyncio.run(main())

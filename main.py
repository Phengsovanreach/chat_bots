import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
import yt_dlp
import telegram

# ---------------------- Config ----------------------
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

# ---------------------- Safe edit function ----------------------
async def safe_edit(message, text):
    try:
        await message.edit_text(text)
    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            raise

# ---------------------- /start Command ----------------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hello! Send me a video link and I will download it as MP4 (up to 2GB)."
    )

# ---------------------- Download Handler ----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    status_msg = await update.message.reply_text("⬇️ Downloading... 0%")
    last_percent = -1
    filename = None

    # ---------------------- Progress hook ----------------------
    def progress_hook(d):
        nonlocal last_percent
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                downloaded = d['downloaded_bytes']
                percent = int(downloaded / total_bytes * 100)
                if percent % 10 == 0 and percent != last_percent:
                    last_percent = percent
                    asyncio.create_task(safe_edit(status_msg, f"⬇️ Downloading... {percent}%"))

    # ---------------------- yt-dlp options ----------------------
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "format": "bestvideo[height<=720]+bestaudio/best",  # best quality under 720p
        "progress_hooks": [progress_hook],
        "quiet": True,
        "restrictfilenames": True,
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",  # converts any format to MP4
                "preferedformat": "mp4"
            }
        ],
    }

    try:
        # ---------------------- Download ----------------------
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Ensure filename ends with .mp4 after conversion
            filename = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp4"

        file_size = os.path.getsize(filename)
        if file_size > MAX_FILE_SIZE:
            await update.message.reply_text("⚠️ Video too large (>2GB) to send on Telegram.")
            return

        # ---------------------- Send video ----------------------
        with open(filename, "rb") as video_file:
            await update.message.reply_document(
                document=video_file,
                caption=f"✅ Download completed! ({file_size//1024//1024} MB)"
            )

    except Exception as e:
        await update.message.reply_text(f"❌ Failed to download.\nError: {e}")
        print(f"Error: {e}")

    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)
        await status_msg.delete()

# ---------------------- Build Bot ----------------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 Bot is running...")
app.run_polling()

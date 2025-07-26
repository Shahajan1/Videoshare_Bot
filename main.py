import os
import sys
import random
import string
import sqlite3
import logging
from dotenv import load_dotenv

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.error import BadRequest

# === Print version info for Render log ===
print(f"🐍 Python version: {sys.version}")
print(f"📦 python-telegram-bot version: {telegram.__version__}")

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === Load .env (local only) ===
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME")
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_INVITE_LINK = os.getenv("CHANNEL_INVITE_LINK")

if not all([BOT_TOKEN, BOT_USERNAME, CHANNEL_ID, CHANNEL_INVITE_LINK]):
    raise ValueError("❌ One or more environment variables are missing.")

# === SQLite setup ===
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS videos (code TEXT PRIMARY KEY, file_id TEXT)")

# === Helpers ===
def generate_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except BadRequest:
        return False

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        code = args[0]
        data = cursor.execute("SELECT file_id FROM videos WHERE code=?", (code,)).fetchone()
        if not data:
            await update.message.reply_text("❌ Invalid or expired video code.")
            return

        user_id = update.effective_user.id
        if not await is_member(context.bot, user_id):
            button = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_INVITE_LINK)]
            ])
            await update.message.reply_text("🔒 Join the channel to unlock the video.", reply_markup=button)
            return

        await update.message.reply_video(data[0])
    else:
        await update.message.reply_text(
            "👋 Welcome! Send me a video to get a sharable link, or send a code to retrieve a video."
        )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    video = update.message.video
    if not user or not video:
        return

    file_id = video.file_id
    code = generate_code()
    while cursor.execute("SELECT * FROM videos WHERE code=?", (code,)).fetchone():
        code = generate_code()

    cursor.execute("INSERT INTO videos VALUES (?, ?)", (code, file_id))
    conn.commit()

    share_link = f"https://t.me/{BOT_USERNAME}?start={code}"
    await update.message.reply_text(
        f"🎥 Video saved!\n\n🔗 Share this link:\n{share_link}"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    data = cursor.execute("SELECT file_id FROM videos WHERE code=?", (code,)).fetchone()

    if not data:
        await update.message.reply_text("❌ Invalid code.")
        return

    user_id = update.effective_user.id
    if not await is_member(context.bot, user_id):
        button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_INVITE_LINK)]
        ])
        await update.message.reply_text("🔒 Join the channel to access the video.", reply_markup=button)
        return

    await update.message.reply_video(data[0])

# === Bot Startup ===
def main():
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.VIDEO, handle_video))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print("✅ Bot is starting...")
        app.run_polling()
    except Exception as e:
        logging.error(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()

import os
import json
import logging
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === MEMORY STORE ===
user_memory = {}
USERS_FILE = "users.json"


# === LOAD USERS ON START ===
def load_users():
    """Load known users from JSON file."""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return []


def save_users(users):
    """Save known users to JSON file."""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)


known_users = load_users()


# === FLASK KEEP-ALIVE SERVER ===
def keep_alive():
    app = Flask(__name__)

    @app.route('/')
    def home():
        return "✅ Telegram AI bot is running live on Render!"

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


# === OPENROUTER AI REQUEST ===
async def ask_openrouter(messages: list) -> str:
    """Send conversation to OpenRouter API and return AI reply."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",
        "X-Title": "Render Telegram Bot"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",
        "messages": messages
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=60) as response:
            if response.status != 200:
                text = await response.text()
                logging.error(f"OpenRouter API error {response.status}: {text}")
                return "❌ Sorry, there was a problem connecting to the AI."

            data = await response.json()
            return data["choices"][0]["message"]["content"].strip()


# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in known_users:
        known_users.append(user_id)
        save_users(known_users)

    await update.message.reply_text(
        "Hey 👋! I’m your AI assistant powered by @Uknowntech1 🚀\n\n"
        "Send me any question — I’ll remember our chat!"
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total_users = len(known_users)
    await update.message.reply_text(f"👥 Total users who interacted with me: {total_users}")


# === MESSAGE HANDLER WITH MEMORY ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text

    # Register user if new
    if user_id not in known_users:
        known_users.append(user_id)
        save_users(known_users)

    # Load or initialize chat memory
    history = user_memory.get(user_id, [])
    history.append({"role": "user", "content": user_input})
    history = history[-8:]

    messages = [
        {"role": "system", "content": "You are a friendly Telegram assistant by @dionbett and powered by @Uknowntech1."}
    ] + history

    await update.message.reply_text("🤖 Thinking...")

    try:
        ai_reply = await ask_openrouter(messages)
        await update.message.reply_text(ai_reply)

        history.append({"role": "assistant", "content": ai_reply})
        user_memory[user_id] = history[-8:]

    except Exception as e:
        logging.exception("Error during AI response:")
        await update.message.reply_text("⚠️ Something went wrong. Please try again later.")


# === MAIN ===
def main():
    if not BOT_TOKEN:
        raise ValueError("❗ TELEGRAM_BOT_TOKEN environment variable is missing.")
    if not OPENROUTER_API_KEY:
        raise ValueError("❗ OPENROUTER_API_KEY environment variable is missing.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ Telegram bot is running.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


# === ENTRY POINT ===
if __name__ == "__main__":
    Thread(target=keep_alive).start()
    main()
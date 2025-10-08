import os
import logging
import aiohttp
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # Set this in Render

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === MEMORY STORE ===
# Simple in-memory conversation history per user
user_memory = {}

# === FLASK KEEP-ALIVE SERVER ===
def keep_alive():
    app = Flask(__name__)

    @app.route('/')
    def home():
        return "✅ Telegram AI bot is running successfully on Render!"

    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# === OPENROUTER AI REQUEST ===
async def ask_openrouter(messages: list) -> str:
    """
    Send a conversation to OpenRouter API and return the model's reply.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",  # required by OpenRouter
        "X-Title": "Render Telegram Bot"
    }

    payload = {
        "model": "openai/gpt-3.5-turbo",  # You can change to gpt-4o or another model
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
    await update.message.reply_text(
        "Hey 👋! I’m your AI assistant powered by OpenRouter.\n\n"
        "Just send me any question or topic — I’ll remember our conversation!"
    )

# === MESSAGE HANDLER WITH SESSION MEMORY ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text

    # Load or initialize memory for this user
    history = user_memory.get(user_id, [])

    # Add the latest user message
    history.append({"role": "user", "content": user_input})
    history = history[-8:]  # keep only the last 5 exchanges for memory efficiency

    # Prepare messages with context
    messages = [{"role": "system", "content": "You are a friendly and helpful Telegram assistant."}] + history

    await update.message.reply_text("🤖 Thinking...")

    try:
        ai_reply = await ask_openrouter(messages)
        await update.message.reply_text(ai_reply)

        # Save assistant reply in memory
        history.append({"role": "assistant", "content": ai_reply})
        user_memory[user_id] = history[-5:]

    except Exception as e:
        logging.exception("Error during AI response:")
        await update.message.reply_text("⚠️ Something went wrong. Please try again later.")

# === MAIN FUNCTION ===
def main():
    if not BOT_TOKEN:
        raise ValueError("❗ TELEGRAM_BOT_TOKEN environment variable is missing.")
    if not OPENROUTER_API_KEY:
        raise ValueError("❗ OPENROUTER_API_KEY environment variable is missing.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logging.info("✅ Telegram bot is now running with OpenRouter + session memory.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# === ENTRY POINT ===
if __name__ == "__main__":
    # Start Flask web server to keep Render container alive
    Thread(target=keep_alive).start()
    main()
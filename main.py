import os
import logging
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === CONFIG ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")  # set this in Render

# === LOGGING ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# === COMMAND HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey 👋! I’m your AI assistant powered by OpenRouter.\n\n"
        "Just send me any question or topic!"
    )


# === AI RESPONSE HANDLER ===
async def ask_openrouter(prompt: str) -> str:
    """
    Send a prompt to OpenRouter API and return the model's response.
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com",  # required by OpenRouter
        "X-Title": "Render Telegram Bot"
    }

    payload = {
        "model": "gpt-3.5-turbo",  # or another available OpenRouter model
        "messages": [
            {"role": "system", "content": "You are a helpful Telegram AI assistant."},
            {"role": "user", "content": prompt}
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=60) as response:
            if response.status != 200:
                text = await response.text()
                logging.error(f"OpenRouter API error {response.status}: {text}")
                return "❌ Sorry, there was a problem connecting to the AI."

            data = await response.json()
            return data["choices"][0]["message"]["content"].strip()


# === TELEGRAM MESSAGE HANDLER ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    await update.message.reply_text("🤖 Thinking...")

    try:
        ai_reply = await ask_openrouter(user_input)
        await update.message.reply_text(ai_reply)
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
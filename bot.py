import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from knowledge.llm import ClaudeLLMClient
from storage import ensure_storage_dir, save_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Module-level LLM client, initialized in main()
llm = None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        "Hello! I'm your personal knowledge base bot. "
        "Send me any message and I'll respond with the help of an LLM."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process incoming text messages through the LLM and reply."""
    user = update.effective_user
    text = update.message.text

    # Save to the legacy log file
    save_message(
        file_path=config.MESSAGES_FILE,
        user_id=user.id,
        username=user.username or user.first_name,
        text=text,
    )

    # Send through the LLM
    response = await llm.chat(text)

    logger.info("Processed message from user %s (id=%d)", user.username, user.id)
    await update.message.reply_text(response)


def main() -> None:
    """Validate config, initialize LLM, build application, and start polling."""
    global llm
    config.validate_config()
    ensure_storage_dir(config.MESSAGES_FILE)

    llm = ClaudeLLMClient(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.LLM_MODEL,
    )

    auth = filters.User(user_id=config.AUTHORIZED_USER_ID)

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command, filters=auth))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & auth, handle_message)
    )

    logger.info(
        "Bot starting with LLM model %s. Listening for user ID %d.",
        config.LLM_MODEL,
        config.AUTHORIZED_USER_ID,
    )
    app.run_polling()


if __name__ == "__main__":
    main()

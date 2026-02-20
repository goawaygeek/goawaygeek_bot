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
from storage import ensure_storage_dir, save_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        "Hello! I'm your personal note-taking bot. "
        "Send me any message and I'll save it for you."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Save incoming text messages to storage."""
    user = update.effective_user
    text = update.message.text

    save_message(
        file_path=config.MESSAGES_FILE,
        user_id=user.id,
        username=user.username or user.first_name,
        text=text,
    )

    logger.info("Saved message from user %s (id=%d)", user.username, user.id)
    await update.message.reply_text("Saved.")


def main() -> None:
    """Validate config, build application, and start polling."""
    config.validate_config()
    ensure_storage_dir(config.MESSAGES_FILE)

    auth = filters.User(user_id=config.AUTHORIZED_USER_ID)

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command, filters=auth))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & auth, handle_message)
    )

    logger.info(
        "Bot starting. Listening for messages from user ID %d.", config.AUTHORIZED_USER_ID
    )
    app.run_polling()


if __name__ == "__main__":
    main()

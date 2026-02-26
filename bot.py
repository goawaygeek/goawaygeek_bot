import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from knowledge.brain import KnowledgeBrain
from knowledge.conversation_log import SQLiteConversationLog
from knowledge.llm import ClaudeLLMClient
from knowledge.prompt_manager import PromptManager
from knowledge.store import SQLiteStore
from storage import ensure_storage_dir, save_message

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Module-level brain, initialized in main()
brain = None  # type: Optional[KnowledgeBrain]

# context.user_data key for a pending capability-gap feature proposal
_PENDING_FEATURE_KEY = "pending_feature"


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        "Hello! I'm your personal knowledge base bot.\n\n"
        "Send me anything and I'll file it intelligently. "
        "Type /help to see what I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command."""
    await update.message.reply_text(
        "/ask <question> \u2014 Ask your knowledge base\n"
        "/search <query> \u2014 Search your notes\n"
        "/recent \u2014 Show recent items\n"
        "/overview \u2014 See your rolling overview\n"
        "/refresh \u2014 Refresh the overview\n"
        "/confirm_feature \u2014 Apply a proposed prompt improvement\n"
        "/help \u2014 Show this message"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Capture an incoming message into the knowledge base."""
    user = update.effective_user
    text = update.message.text

    # Legacy log (kept for backward compatibility)
    save_message(
        file_path=config.MESSAGES_FILE,
        user_id=user.id,
        username=user.username or user.first_name,
        text=text,
    )

    # Route through the knowledge brain
    response = await brain.capture(text)

    logger.info("Captured message from user %s (id=%d)", user.username, user.id)
    await update.message.reply_text(response)


async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /ask command — query the knowledge base."""
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text("Usage: /ask <your question>")
        return

    answer = await brain.query(question)

    # Check whether the answer reveals a capability gap
    gap = await brain.check_capability_gap(question, answer)
    if gap:
        context.user_data[_PENDING_FEATURE_KEY] = gap
        proposal_text = gap.get("proposal", "I could improve my prompts to support this.")
        response = (
            f"{answer}\n\n"
            f"---\n"
            f"{proposal_text}\n\n"
            f"Type /confirm_feature to apply this improvement."
        )
    else:
        response = answer

    await update.message.reply_text(response)


async def confirm_feature_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Apply a pending capability-gap prompt update."""
    gap = context.user_data.pop(_PENDING_FEATURE_KEY, None)
    if not gap:
        await update.message.reply_text(
            "No pending feature proposal. Use /ask first — if I detect a gap "
            "I'll offer to fix it."
        )
        return

    prompt_name = gap.get("prompt_name")
    prompt_update = gap.get("prompt_update")

    if not prompt_name or not prompt_update:
        await update.message.reply_text(
            "The proposal didn't include enough detail to apply automatically. "
            "No changes made."
        )
        return

    result = await brain.evolve_prompt(prompt_name, prompt_update)
    await update.message.reply_text(result)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /search command — keyword search."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Usage: /search <query>")
        return
    results = brain.search(query)
    if not results:
        await update.message.reply_text("No results found.")
        return
    lines = []
    for r in results[:5]:
        tags = ", ".join(r.item.tags) if r.item.tags else ""
        summary = r.item.summary or r.item.content[:80]
        line = f"[{r.item.item_type.value}] {summary}"
        if tags:
            line += f"\n  Tags: {tags}"
        lines.append(line)
    await update.message.reply_text("\n\n".join(lines))


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /recent command — show recent items."""
    items = brain.recent(limit=5)
    if not items:
        await update.message.reply_text("No items yet.")
        return
    lines = []
    for item in items:
        tags = ", ".join(item.tags) if item.tags else "no tags"
        summary = item.summary or item.content[:80]
        lines.append(
            f"[{item.item_type.value}] {summary}\n"
            f"  Tags: {tags}"
        )
    await update.message.reply_text("\n\n".join(lines))


async def overview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /overview command — show the rolling overview."""
    overview = await brain.get_overview()
    await update.message.reply_text(overview)


async def refresh_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /refresh command — deep overview refresh."""
    result = await brain.refresh_overview()
    await update.message.reply_text(result)


def main() -> None:
    """Validate config, initialize brain, build application, and start polling."""
    global brain
    config.validate_config()
    ensure_storage_dir(config.MESSAGES_FILE)

    # Initialize prompt manager (base prompts always present; user repo optional)
    prompt_manager = PromptManager(
        base_dir=config.PROMPTS_BASE_DIR,
        user_dir=config.PROMPTS_USER_DIR if config.PROMPTS_REPO_URL else None,
        repo_url=config.PROMPTS_REPO_URL,
    )

    # Initialize the knowledge brain
    llm = ClaudeLLMClient(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.LLM_MODEL,
    )
    store = SQLiteStore(
        db_path=config.DB_PATH,
        overview_md_path=config.OVERVIEW_MD_PATH,
    )
    conversation_log = SQLiteConversationLog(
        db_path=config.CONVERSATION_LOG_DB_PATH,
    )
    brain = KnowledgeBrain(
        llm=llm,
        store=store,
        conversation_log=conversation_log,
        prompt_manager=prompt_manager,
    )

    auth = filters.User(user_id=config.AUTHORIZED_USER_ID)

    app = ApplicationBuilder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command, filters=auth))
    app.add_handler(CommandHandler("help", help_command, filters=auth))
    app.add_handler(CommandHandler("ask", ask_command, filters=auth))
    app.add_handler(CommandHandler("confirm_feature", confirm_feature_command, filters=auth))
    app.add_handler(CommandHandler("search", search_command, filters=auth))
    app.add_handler(CommandHandler("recent", recent_command, filters=auth))
    app.add_handler(CommandHandler("overview", overview_command, filters=auth))
    app.add_handler(CommandHandler("refresh", refresh_command, filters=auth))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & auth, handle_message)
    )

    logger.info(
        "Bot starting with LLM model %s, DB at %s. Listening for user ID %d.",
        config.LLM_MODEL,
        config.DB_PATH,
        config.AUTHORIZED_USER_ID,
    )
    app.run_polling()


if __name__ == "__main__":
    main()

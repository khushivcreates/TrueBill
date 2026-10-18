"""TrueBill Telegram bot.

Sends a bill (photo or PDF) -> downloads it -> process_bill() -> Audit JSON
formatted as a readable message.

Secrets come from the .env file at the repo root; no key is ever printed.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from processor import is_supported, process_bill

# Repo root: <TrueBill-repo>/bot/this_file.py -> <TrueBill-repo>/.env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Downloads land next to this file; never outside the bot folder.
DOWNLOAD_DIR = Path(__file__).resolve().parent / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
)
# Never log HTTP requests: they include the bot token in the URL.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("truebill")

TELEGRAM_MESSAGE_LIMIT = 4096

START_MESSAGE = (
    "👋 Hi! I'm the TrueBill bot.\n\n"
    "Send me a photo 📸 or a PDF 📄 of your BRPL electricity bill and I'll "
    "audit it against the official domestic tariff.\n\n"
    "I'll check each charge, explain anything that looks off, list what I'm "
    "unsure about, and link the sources I used.\n\n"
    "Commands:\n"
    "/start — show this message\n"
    "/help — same as /start"
)


def format_audit(audit: dict) -> str:
    """Render an Audit JSON dict as a readable Telegram message."""
    lines: list[str] = ["📊 *Bill audit*", ""]

    checks = audit.get("checks") or []
    if checks:
        lines.append("*Checks*")
        for check in checks:
            icon = "✅" if check.get("status") == "ok" else "⚠️"
            item = check.get("item", "Unknown check")
            lines.append(f"{icon} *{item}*")

            billed = check.get("billed")
            expected = check.get("expected")
            if billed is not None and expected is not None:
                lines.append(f"   Billed: {billed} | Expected: {expected}")

            note = check.get("note")
            if note:
                lines.append(f"   {note}")
            lines.append("")

    explanation = audit.get("explanation")
    if explanation:
        lines.append("*Explanation*")
        lines.append(explanation)
        lines.append("")

    uncertainties = audit.get("uncertainties") or []
    if uncertainties:
        lines.append("*Uncertainties*")
        for item in uncertainties:
            lines.append(f"⚠️ {item}")
        lines.append("")

    sources = audit.get("sources") or []
    if sources:
        lines.append("*Source links*")
        for source in sources:
            title = source.get("title", "Source")
            url = source.get("url", "")
            effective = source.get("effective_date")
            suffix = f" _(effective {effective})_" if effective else ""
            lines.append(f"• [{title}]({url}){suffix}" if url else f"• {title}")
        lines.append("")

    draft = audit.get("draft_complaint")
    if draft:
        lines.append("*Draft complaint*")
        lines.append("```")
        lines.append(draft)
        lines.append("```")

    return "\n".join(lines).strip()


async def send_long_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> None:
    """Send a message, splitting it if it exceeds Telegram's 4096-char limit."""
    chat_id = update.effective_chat.id
    while text:
        chunk, text = text[:TELEGRAM_MESSAGE_LIMIT], text[TELEGRAM_MESSAGE_LIMIT:]
        # Avoid cutting a Markdown entity mid-way; if parse fails, retry plain.
        try:
            await context.bot.send_message(
                chat_id=chat_id, text=chunk, parse_mode="Markdown"
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=chunk)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(START_MESSAGE)


async def handle_bill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message

    if message.photo:
        file_id = message.photo[-1].file_id
        extension = ".jpg"
        label = "photo"
    else:
        document = message.document
        if not document.file_name or not document.file_name.lower().endswith(".pdf"):
            await message.reply_text("Please send a photo or a PDF of your bill. 📸📄")
            return
        file_id = document.file_id
        extension = ".pdf"
        label = "PDF"

    await message.chat.send_action(ChatAction.TYPING)
    log.info("Received a %s, downloading...", label)

    telegram_file = await context.bot.get_file(file_id)
    destination = DOWNLOAD_DIR / (
        f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{message.chat.id}{extension}"
    )
    await telegram_file.download_to_drive(custom_path=destination)

    try:
        if not is_supported(destination):
            await message.reply_text("Unsupported file type. Send a photo or a PDF. 📸📄")
            return

        await message.chat.send_action(ChatAction.TYPING)
        audit = process_bill(destination)
        await send_long_message(update, context, format_audit(audit))
    except Exception:
        log.exception("Failed to process the bill")
        await message.reply_text(
            "Sorry, something went wrong while auditing this bill. Please try again."
        )
    finally:
        destination.unlink(missing_ok=True)


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "I only read bills. Send me a photo 📸 or a PDF 📄 of your bill, "
        "or type /start to see how this works."
    )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        # Print the key name only, never its value.
        log.error(
            "TELEGRAM_BOT_TOKEN is missing from %s — fill it in and restart.",
            ENV_PATH,
        )
        raise SystemExit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.PDF, handle_bill)
    )
    application.add_handler(MessageHandler(~filters.COMMAND, handle_other))

    log.info("TrueBill bot is running")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

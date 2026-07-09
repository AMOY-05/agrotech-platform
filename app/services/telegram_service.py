import httpx
from app.core.config import settings
from loguru import logger
from typing import Optional

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}"
TELEGRAM_FILE_URL = "https://api.telegram.org/file/bot{token}/{file_path}"


def _get_api_url() -> str:
    return f"https://api.telegram.org/bot{settings.telegram_bot_token}"


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown"
) -> bool:
    """Sends a text message to a Telegram chat."""
    if not settings.telegram_bot_token:
        logger.error("Telegram bot token not configured")
        return False

    # Telegram has a 4096 char limit per message
    chunks = _split_message(text, max_length=4000)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            for chunk in chunks:
                response = await client.post(
                    f"{_get_api_url()}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": chunk,
                        "parse_mode": parse_mode
                    }
                )
                if response.status_code != 200:
                    logger.error(f"Telegram send error: {response.text}")
                    # Try without markdown if formatting fails
                    await client.post(
                        f"{_get_api_url()}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": chunk,
                        }
                    )
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


async def send_typing_action(chat_id: int):
    """Shows 'typing...' indicator in Telegram chat."""
    if not settings.telegram_bot_token:
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{_get_api_url()}/sendChatAction",
                json={"chat_id": chat_id, "action": "typing"}
            )
    except Exception:
        pass  # Non-critical


async def download_telegram_file(file_id: str) -> Optional[bytes]:
    """Downloads a file from Telegram servers using file_id."""
    if not settings.telegram_bot_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Get file path
            response = await client.get(
                f"{_get_api_url()}/getFile",
                params={"file_id": file_id}
            )
            if response.status_code != 200:
                logger.error(f"Could not get file info: {response.text}")
                return None

            file_path = response.json()["result"]["file_path"]

            # Step 2: Download file
            file_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
            file_response = await client.get(file_url)

            if file_response.status_code != 200:
                logger.error(f"Could not download file: {file_response.status_code}")
                return None

            return file_response.content

    except Exception as e:
        logger.error(f"File download failed: {e}")
        return None


async def set_webhook(webhook_url: str) -> bool:
    """Sets the Telegram webhook URL."""
    if not settings.telegram_bot_token:
        return False

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{_get_api_url()}/setWebhook",
                json={
                    "url": f"{webhook_url}/api/v1/telegram/webhook",
                    "allowed_updates": ["message", "callback_query"],
                    "secret_token": "agrotech_telegram_secret"
                }
            )
            data = response.json()
            if data.get("ok"):
                logger.info(f"Telegram webhook set to: {webhook_url}")
                return True
            else:
                logger.error(f"Webhook setup failed: {data}")
                return False
    except Exception as e:
        logger.error(f"Webhook setup error: {e}")
        return False


async def delete_webhook() -> bool:
    """Removes the webhook (for polling mode)."""
    if not settings.telegram_bot_token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{_get_api_url()}/deleteWebhook"
            )
            return response.json().get("ok", False)
    except Exception:
        return False


def parse_farmer_id(telegram_user_id: int) -> str:
    """Converts Telegram user ID to stable farmer_id."""
    return f"farmer_tg_{telegram_user_id}"


def _split_message(message: str, max_length: int = 4000) -> list:
    """Splits long messages into Telegram-safe chunks."""
    if len(message) <= max_length:
        return [message]

    chunks = []
    words = message.split()
    current_chunk = ""

    for word in words:
        if len(current_chunk) + len(word) + 1 <= max_length:
            current_chunk += f" {word}" if current_chunk else word
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = word

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _is_language_command(message: str) -> Optional[str]:
    """Detects language preference commands."""
    message_lower = message.lower().strip()
    languages = ["english", "yoruba", "hausa", "igbo", "pidgin"]
    for lang in languages:
        if f"language: {lang}" in message_lower or \
           f"language {lang}" in message_lower or \
           f"/language {lang}" in message_lower or \
           message_lower == lang:
            return lang
    return None
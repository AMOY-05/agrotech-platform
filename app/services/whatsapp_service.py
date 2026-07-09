from twilio.rest import Client
from app.core.config import settings
from loguru import logger
from typing import Optional

def get_twilio_client() -> Optional[Client]:
    """Returns Twilio client if credentials are configured."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning("Twilio credentials not configured")
        return None
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


async def send_whatsapp_message(to_number: str, message: str) -> bool:
    """
    Sends a WhatsApp message via Twilio.
    to_number should be in format: whatsapp:+2348012345678
    """
    client = get_twilio_client()
    if not client:
        logger.error("Cannot send WhatsApp — Twilio not configured")
        return False

    try:
        # WhatsApp has a 1600 character limit per message
        # Split long messages into chunks
        chunks = _split_message(message, max_length=1500)

        for chunk in chunks:
            client.messages.create(
                from_=settings.twilio_whatsapp_number,
                to=to_number,
                body=chunk
            )
            logger.info(f"WhatsApp message sent to {to_number}: {chunk[:50]}...")

        return True

    except Exception as e:
        logger.error(f"Failed to send WhatsApp message: {e}")
        return False


def _split_message(message: str, max_length: int = 1500) -> list:
    """Splits long messages into chunks that fit WhatsApp's limit."""
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


def parse_whatsapp_number(from_number: str) -> str:
    """
    Converts WhatsApp number to a stable farmer_id.
    whatsapp:+2348012345678 → farmer_wa_2348012345678
    """
    clean = from_number.replace("whatsapp:", "").replace("+", "").strip()
    return f"farmer_wa_{clean}"


def detect_language_from_number(phone_number: str) -> str:
    """
    Makes a best guess at preferred language from phone number country code.
    Nigerian numbers (+234) default to English but could be any Nigerian language.
    """
    if "+234" in phone_number or "234" in phone_number:
        return "english"  # Default for Nigerian numbers
    return "english"
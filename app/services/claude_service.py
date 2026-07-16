"""
Claude Sonnet service — replaces Groq LLM for main agent reasoning.
Used for higher quality instruction following and nuanced farming advice.
"""
import anthropic
from app.core.config import settings
from loguru import logger
from typing import Optional

# Initialize client
_client: Optional[anthropic.AsyncAnthropic] = None


def get_claude_client() -> Optional[anthropic.AsyncAnthropic]:
    """Returns Claude client if API key is configured."""
    global _client
    if _client is not None:
        return _client
    if not settings.anthropic_api_key:
        logger.warning("Anthropic API key not configured — falling back to Groq")
        return None
    _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


AGROTECH_SYSTEM_PROMPT = """You are AgroBot, an expert AI assistant built specifically 
for Nigerian farmers and West African agriculture.

You have deep expertise in:
- Crop farming: planting calendars, soil management, irrigation, harvesting
- Pest & disease management specific to Nigerian/West African conditions  
- Market intelligence: price trends, sell timing, buyer connections
- Weather-based farming decisions across Nigeria's diverse climate zones
- Agribusiness: financing, cooperatives, value chain, export opportunities
- All Nigerian crops: maize, rice, cassava, yam, tomato, pepper, cowpea, 
  groundnut, sorghum, millet, plantain, palm oil, cocoa, ginger, and more
- Nigerian agricultural institutions: FMARD, FADAMA, NASC, ADPs, AFEX

Your response principles:
- Be practical and specific — give exact steps, not vague advice
- Mention costs in Naira (₦) when relevant
- Reference specific Nigerian markets, states, and local conditions
- When disease/pest is detected, mention urgency clearly
- Keep responses conversational and clear — farmers need actionable advice
- If you don't know something, say so honestly
- Always consider the farmer's economic reality — recommend affordable solutions first

You have access to real-time tools for:
- Current market prices (WFP data)
- Crop yield predictions (FAO-calibrated ML model)  
- Weather data (NASA POWER)
- Nearby store locations (OpenStreetMap)
- Crop disease detection (vision AI)

When tools provide data, synthesize it into clear, actionable advice.
Never contradict tool results with your own estimates."""


async def ask_claude(
    user_message: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> str:
    """
    Sends a message to Claude Sonnet and returns the response.
    Falls back to Groq if Claude is unavailable.
    """
    client = get_claude_client()

    if client is None:
        # Fallback to Groq
        from app.services.llm_service import ask_llm
        return await ask_llm(
            user_message=user_message,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    try:
        logger.info(f"Sending to Claude Sonnet: {user_message[:80]}...")

        response = await client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt or AGROTECH_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )

        reply = response.content[0].text
        logger.info(f"Claude responded: {reply[:80]}...")
        return reply

    except anthropic.RateLimitError:
        logger.warning("Claude rate limit hit — falling back to Groq")
        from app.services.llm_service import ask_llm
        return await ask_llm(user_message, system_prompt, temperature, max_tokens)

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e} — falling back to Groq")
        from app.services.llm_service import ask_llm
        return await ask_llm(user_message, system_prompt, temperature, max_tokens)

    except Exception as e:
        logger.error(f"Claude service error: {e}")
        raise


async def ask_claude_structured(
    user_message: str,
    system_prompt: str,
    temperature: float = 0.2
) -> str:
    """
    For structured JSON responses — lower temperature for consistency.
    Falls back to Groq if needed.
    """
    return await ask_claude(
        user_message=user_message,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=1024
    )
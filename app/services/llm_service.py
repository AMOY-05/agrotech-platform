from groq import Groq
from app.core.config import settings
from loguru import logger
from typing import Optional

# Initialize Groq Client once - reused across all requests

client = Groq(api_key=settings.groq_api_key)

AGRO_SYSTEM_PROMPT = """
You are AgroBot, an expert AI assistant for Nigerian farmers. 
You have deep knowledge of:
- Crop diseases, pests, and treatments common in West Africa
- Nigerian market prices and seasonal trends
- Optimal planting and harvest timing for Nigerian climate zones
- Soil types and fertilizer recommendations
- Crops: tomato, maize, cassava, yam, rice, pepper, plantain, cowpea and all other crops available in west africa

Your response rules:
- Be practical and actionable — farmers need clear steps, not theory
- Use simple English (farmers may not be highly educated)
- Always mention urgency level when disease/pest is detected (low/medium/high)
- When relevant, mention approximate costs in Naira (₦)
- Keep responses under 200 words unless detail is critical
- If you don't know something, say so honestly

You are talking to a Nigerian farmer right now. Be helpful, warm, and direct.
"""
async def ask_llm(
    user_message: str,
    system_prompt: Optional[str] = None,
    temperature: float=0.7,
    max_tokens: int =500
) -> str:
  """
  Core function to send a message to Groq LLM and get a response.
  Used by all routes that need LLM intelligence.
  """
  try:
    logger.info(f"Sending to Groq: {user_message[:80]}...")

    response = client.chat.completions.create(
      model="llama-3.3-70b-versatile",
      messages=[
        {
          "role": "system",
          "content": system_prompt or AGRO_SYSTEM_PROMPT
        },
        {
          "role": "user",
          "content": user_message
        }
      ],
      temperature=temperature,
      max_tokens=max_tokens
    )

    reply = response.choices[0].message.content
    logger.info(f"Groq responded: {reply[:80]}...")
    return reply
  
  except Exception as e:
    logger.error(f"Groq LLM error: {e}")
    raise Exception(f"LLM service unavailable: {str(e)}")
  

async def ask_llm_structured(
    user_message: str,
    system_prompt: str,
    temperature: float = 0.3
) -> str:
    """
    For structured responses (pest detection, yield analysis).
    Lower temperature means more consistent, predictable output.
    """
    return await ask_llm(
        user_message=user_message,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=600
    )
import re
from groq import Groq
from app.core.config import settings
from app.agent.tools import AGENT_TOOLS, run_tool
from app.agent.memory import get_session, extract_and_update_context, FarmerSession
from loguru import logger
import json

client = Groq(api_key=settings.groq_api_key)

def _sanitize_reply(content: str) -> str:
    """
    Cleans agent reply of any leaked HTML, JSON, or formatting artifacts.
    """
    if not content:
        return "I couldn't generate a response. Please try again."

    # Remove leaked JSON context objects
    content = re.sub(
        r'^\s*\{[^{}]*"crop_type"[^{}]*\}\s*',
        "", content, flags=re.DOTALL
    ).strip()

    # Remove HTML tags completely
    content = re.sub(r'<[^>]+>', '', content)

    # Remove markdown code blocks
    content = re.sub(r'```json.*?```', '', content, flags=re.DOTALL)
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)

    # Remove excessive whitespace
    content = re.sub(r'\n{3,}', '\n\n', content).strip()

    return content if content else "I couldn't generate a response. Please try again."

BASE_SYSTEM_PROMPT = """
You are AgroBot, an expert AI assistant for Nigerian farmers and agribusiness professionals.

You have BROAD agricultural knowledge covering:
- Crop farming: planting, harvesting, pest/disease management, soil health
- Agribusiness: rice mills, processing plants, storage facilities, cooperatives
- Market information: buyers, sellers, prices, supply chains
- Agricultural policies, subsidies, and government programs in Nigeria
- Farm input suppliers, equipment dealers, and service providers
- Export markets and value chain actors for Nigerian crops
- Food processing industries: rice milling, cassava processing, tomato factories, etc.
- Livestock, poultry, aquaculture, and mixed farming systems
- Agricultural financing, insurance, and investment opportunities
- Weather patterns, climate zones, and seasonal farming calendars for Nigeria

You also have access to TOOLS for real-time data:
- detect_pest_disease: identify crop diseases from symptoms
- forecast_price: get current market price forecasts
- predict_yield: estimate crop yield from farm conditions

TOOL USAGE RULES:
- Use tools when a farmer describes symptoms, asks about current prices, or wants yield estimates
- For general knowledge questions (rice mills, best states for farming, farming techniques,
  agribusiness info, industry listings, etc.) answer directly from your knowledge — do NOT
  try to call a tool, especially not web search tools you don't have access to
- Farmer questions often contain MULTIPLE separate needs — call ALL relevant tools,
  not just the first one you notice
- Never guess at real-time data a tool could give you — use the tool
- Never attempt to call tools that are not in your available tools list

RESPONSE STYLE:
- Be practical and actionable — farmers need clear steps, not theory
- Use simple English (some farmers may not be highly educated)
- Always mention urgency when disease/pest is detected (low/medium/high)
- Mention costs in Naira (₦) when relevant
- For lists (e.g. rice mills, states, companies), give structured, clear information
- Keep responses focused and under 300 words unless detail is critical
- If you genuinely don't know something, say so honestly

When you know the farmer's crop type and region from prior context,
use that information automatically — don't ask the farmer to repeat themselves.

When find_nearby_stores returns marketplace results, explain to the farmer that:
- Nigerian agro-input stores are often located inside or near major markets
- They should ask market traders specifically for the agro-chemical or farm input section
- If a dedicated agro store isn't found, the nearest market is the best starting point
"""

KNOWN_TOOLS = {"detect_pest_disease", "forecast_price", "predict_yield", "find_nearby_stores"}

MAX_TOOL_ROUNDS = 3


def _build_system_prompt(session: FarmerSession) -> str:
    """Builds a personalized system prompt with known farmer context injected."""
    context_summary = session.get_context_summary()
    if context_summary:
        return BASE_SYSTEM_PROMPT + f"\n\n{context_summary}\n"
    return BASE_SYSTEM_PROMPT


async def run_agent(
    user_message: str,
    farmer_id: str = "anonymous",
    crop_context: str = None
) -> dict:
    """
    Main agent loop with memory:
    1. Load/create farmer session
    2. Extract context clues from message
    3. Build personalized system prompt with known context
    4. Run agent loop with tool calling
    5. Save conversation to session memory
    6. Return final response
    """
    # --- Load session ---
    session = get_session(farmer_id)

    # --- Extract context clues from this message ---
    await extract_and_update_context(session, user_message)

    # --- Update context from explicit crop_context parameter if provided ---
    if crop_context:
        session.update_context(crop_type=crop_context)

    # --- Build conversation messages with full history ---
    system_prompt = _build_system_prompt(session)
    messages = [{"role": "system", "content": system_prompt}]

    # Inject conversation history for multi-turn memory
    messages.extend(session.messages)

    # Add current user message
    messages.append({"role": "user", "content": user_message})

    tools_used = []

    try:
        for round_num in range(MAX_TOOL_ROUNDS):
            logger.info(f"Agent [{farmer_id}]: round {round_num + 1}")

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                tools=AGENT_TOOLS,
                tool_choice="auto",
                temperature=0.5,
                max_tokens=700
            )

            response_message = response.choices[0].message

            # --- No tool calls ---
            if not response_message.tool_calls:
                content = response_message.content or ""

                # Check for hallucinated tool-call syntax
                is_hallucinated = bool(re.search(r"<\w+>\{.*?\}</\w+>", content, re.DOTALL))

                if is_hallucinated and round_num < MAX_TOOL_ROUNDS - 1:
                    logger.warning(f"Agent [{farmer_id}]: hallucinated tool call, retrying")
                    messages.append({
                        "role": "user",
                        "content": "Please use the actual tool calling function rather than writing tool syntax as text. If no tool is needed, just answer directly."
                    })
                    continue

                # Save to session memory
                session.add_message("user", user_message)
                session.add_message("assistant", content)

                logger.info(f"Agent [{farmer_id}]: returning final answer")
                return {
                    "reply": _sanitize_reply(content) if content else "I couldn't generate a response. Please try again.",
                    "tools_used": tools_used,
                    "session_context": session.context
                }

            # --- Execute tool calls ---
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                # Guard: model tried to call a tool we don't have (e.g. brave_search)
                if tool_name not in KNOWN_TOOLS:
                    logger.warning(f"Agent [{farmer_id}]: model attempted unknown tool '{tool_name}' — redirecting to knowledge")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "error": f"Tool '{tool_name}' is not available.",
                            "instruction": "Answer this question directly from your agricultural knowledge. Do not attempt to call any other tools."
                        })
                    })
                    continue

                # Fill missing args from session context
                if "crop_type" in tool_args and not tool_args.get("crop_type"):
                    tool_args["crop_type"] = session.context.get("crop_type", "unknown")
                if "region" in tool_args and not tool_args.get("region"):
                    tool_args["region"] = session.context.get("region", "Lagos")

                logger.info(f"Agent [{farmer_id}]: calling tool '{tool_name}' with args {tool_args}")

                tool_result = await run_tool(tool_name, tool_args)
                tools_used.append(tool_name)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })

        # --- Hit max rounds, force final answer ---
        logger.warning(f"Agent [{farmer_id}]: hit max tool rounds, forcing final answer")
        final_response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=700
        )

        final_content = final_response.choices[0].message.content or ""
        session.add_message("user", user_message)
        session.add_message("assistant", final_content)

        return {
            "reply": _sanitize_reply(content) if content else "I couldn't generate a response. Please try again.",
            "tools_used": tools_used,
            "session_context": session.context
        }

    except Exception as e:
        logger.error(f"Agent [{farmer_id}] execution failed: {e}")
        raise Exception(f"Agent error: {str(e)}")
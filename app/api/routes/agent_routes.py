from fastapi import APIRouter, HTTPException
from app.models.schemas import ChatRequest, ChatResponse
from app.agent.agent import run_agent
from app.services.voice_service import translate_response_to_language
from loguru import logger
from datetime import datetime

router = APIRouter()

@router.post("/chat", response_model=ChatResponse, tags=["AI Agent"])
async def agent_chat(request: ChatRequest):
    logger.info(f"Agent chat: farmer={request.farmer_id}, "
                f"message={request.message[:50]}, "
                f"language={request.preferred_language}")

    try:
        result = await run_agent(
            user_message=request.message,
            farmer_id=request.farmer_id or "anonymous",
            crop_context=request.crop_context
        )

        reply = result["reply"]

        # Translate response if farmer prefers a different language
        if request.preferred_language and request.preferred_language != "english":
            reply = await translate_response_to_language(
                response_text=reply,
                target_language=request.preferred_language
            )

        return ChatResponse(
            success=True,
            message="Agent response generated",
            timestamp=datetime.utcnow(),
            reply=reply,
            sources=result["tools_used"],
            session_context=result["session_context"]
        )

    except Exception as e:
        logger.error(f"agent chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
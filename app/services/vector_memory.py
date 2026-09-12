"""
ChromaDB vector memory for long-term farmer knowledge.
Embeddings generated via NVIDIA's hosted nemotron-3-embed-1b API
(no local model — keeps memory footprint low on Render free tier).
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
import httpx
from datetime import datetime
from typing import Optional
from loguru import logger
from pathlib import Path
from app.core.config import settings

CHROMA_PATH = Path("data/chromadb")
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

NVIDIA_EMBED_URL = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nemotron-3-embed-1b"

_chroma_client = None
_collection = None


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        logger.info("ChromaDB client initialized")
    return _chroma_client


def get_collection():
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name="farmer_memory",
            metadata={"description": "Long-term farmer agricultural context"}
        )
        logger.info(f"ChromaDB collection ready: {_collection.count()} memories stored")
    return _collection


async def _embed(text: str, input_type: str = "passage") -> Optional[list]:
    """
    Gets embedding from NVIDIA's hosted nemotron-3-embed-1b API.
    input_type: 'passage' when storing memories, 'query' when searching.
    Returns None on failure so callers can skip gracefully instead of crashing.
    """
    if not settings.nvidia_api_key:
        logger.warning("NVIDIA_API_KEY not configured — skipping embedding")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                NVIDIA_EMBED_URL,
                headers={
                    "Authorization": f"Bearer {settings.nvidia_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "input": [text],
                    "model": NVIDIA_EMBED_MODEL,
                    "input_type": input_type,
                    "modality": "text",
                    "embedding_type": "float",
                    "encoding_format": "float"
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
    except Exception as e:
        logger.error(f"NVIDIA embedding failed: {e}")
        return None


async def store_farmer_memory(
    farmer_id: str,
    memory_type: str,
    content: str,
    metadata: Optional[dict] = None
) -> Optional[str]:
    """
    Stores a long-term memory for a farmer.
    memory_type: 'farm_profile', 'disease_history', 'market_activity',
                 'yield_history', 'preferences'
    """
    embedding = await _embed(content, input_type="passage")
    if embedding is None:
        logger.warning(f"Skipping memory store for {farmer_id} — no embedding")
        return None

    collection = get_collection()
    timestamp = datetime.utcnow().isoformat()
    doc_id = f"{farmer_id}:{memory_type}:{timestamp}"

    meta = {
        "farmer_id": farmer_id,
        "memory_type": memory_type,
        "timestamp": timestamp,
        "content_preview": content[:100]
    }
    if metadata:
        meta.update(metadata)

    try:
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
        )
        logger.info(f"Stored memory for {farmer_id}: {memory_type} — {content[:60]}")
        return doc_id
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        return None


async def retrieve_farmer_memories(
    farmer_id: str,
    query: str,
    n_results: int = 5,
    memory_type: Optional[str] = None
) -> list:
    """Retrieves relevant memories for a farmer using semantic search."""
    collection = get_collection()
    if collection.count() == 0:
        return []

    embedding = await _embed(query, input_type="query")
    if embedding is None:
        return []

    try:
        where = {"farmer_id": farmer_id}
        if memory_type:
            where["memory_type"] = memory_type

        results = collection.query(
            query_embeddings=[embedding],
            n_results=min(n_results, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        memories = []
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, dist in zip(documents, distances):
            if dist < 1.5:
                memories.append(doc)

        logger.info(f"Retrieved {len(memories)} memories for {farmer_id} — query: '{query[:50]}'")
        return memories

    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")
        return []


async def update_farmer_profile(
    farmer_id: str,
    crop_type: Optional[str] = None,
    region: Optional[str] = None,
    farm_size: Optional[float] = None,
    soil_type: Optional[str] = None
):
    """Updates or creates farmer profile memory."""
    if not any([crop_type, region, farm_size, soil_type]):
        return

    parts = []
    if crop_type:
        parts.append(f"grows {crop_type}")
    if region:
        parts.append(f"located in {region}")
    if farm_size:
        parts.append(f"farm size is {farm_size} hectares")
    if soil_type:
        parts.append(f"soil type is {soil_type}")

    if not parts:
        return

    content = f"Farmer {farmer_id} {', '.join(parts)}."

    await store_farmer_memory(
        farmer_id=farmer_id,
        memory_type="farm_profile",
        content=content,
        metadata={
            "crop_type": crop_type or "",
            "region": region or "",
            "farm_size": str(farm_size) if farm_size else "",
            "soil_type": soil_type or ""
        }
    )


async def store_disease_detection(
    farmer_id: str,
    crop_type: str,
    disease: str,
    urgency: str,
    treatment: str
):
    """Stores a disease detection event in long-term memory."""
    content = (
        f"On {datetime.utcnow().strftime('%Y-%m-%d')}, farmer's {crop_type} "
        f"was diagnosed with {disease} (urgency: {urgency}). "
        f"Treatment recommended: {treatment[:200]}"
    )
    await store_farmer_memory(
        farmer_id=farmer_id,
        memory_type="disease_history",
        content=content,
        metadata={"crop_type": crop_type, "disease": disease, "urgency": urgency}
    )


async def store_market_activity(
    farmer_id: str,
    crop_type: str,
    region: str,
    price: float,
    action: str
):
    """Stores market activity in long-term memory."""
    content = (
        f"On {datetime.utcnow().strftime('%Y-%m-%d')}, farmer checked "
        f"{crop_type} prices in {region}. "
        f"Price was ₦{price:.0f}/kg. Action: {action}"
    )
    await store_farmer_memory(
        farmer_id=farmer_id,
        memory_type="market_activity",
        content=content,
        metadata={"crop_type": crop_type, "region": region, "price": str(price)}
    )


def get_farmer_summary(farmer_id: str) -> str:
    """
    Returns a summary of everything known about a farmer.
    Synchronous — only reads already-stored documents, no embedding call needed.
    """
    collection = get_collection()
    if collection.count() == 0:
        return ""

    try:
        where = {"farmer_id": farmer_id}
        results = collection.get(where=where, include=["documents", "metadatas"])

        documents = results.get("documents", [])
        if not documents:
            return ""

        profiles, diseases, market = [], [], []

        for doc, meta in zip(documents, results.get("metadatas", [])):
            mtype = meta.get("memory_type", "")
            if mtype == "farm_profile":
                profiles.append(doc)
            elif mtype == "disease_history":
                diseases.append(doc)
            elif mtype == "market_activity":
                market.append(doc)

        summary_parts = []
        if profiles:
            summary_parts.append(f"Farm Profile: {profiles[-1]}")
        if diseases:
            summary_parts.append(f"Recent disease history: {diseases[-1]}")
        if market:
            summary_parts.append(f"Recent market activity: {market[-1]}")

        return "\n".join(summary_parts) if summary_parts else ""

    except Exception as e:
        logger.error(f"Failed to get farmer summary: {e}")
        return ""


def get_memory_stats() -> dict:
    """Returns ChromaDB statistics."""
    try:
        collection = get_collection()
        return {
            "status": "connected",
            "total_memories": collection.count(),
            "storage_path": str(CHROMA_PATH)
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
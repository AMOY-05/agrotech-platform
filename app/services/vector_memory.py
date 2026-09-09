"""
ChromaDB vector memory for long-term farmer knowledge.
Stores and retrieves farmer-specific agricultural context
across sessions using semantic search.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import Optional
from loguru import logger
from pathlib import Path

# Storage path
CHROMA_PATH = Path("data/chromadb")
CHROMA_PATH.mkdir(parents=True, exist_ok=True)

# Initialize ChromaDB client
_chroma_client = None
_collection = None
_embedder = None


def get_chroma_client():
    """Returns ChromaDB client — initialized once."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        logger.info("ChromaDB client initialized")
    return _chroma_client


def get_collection():
    """Returns or creates the farmer memory collection."""
    global _collection
    if _collection is None:
        client = get_chroma_client()
        _collection = client.get_or_create_collection(
            name="farmer_memory",
            metadata={"description": "Long-term farmer agricultural context"}
        )
        logger.info(
            f"ChromaDB collection ready: "
            f"{_collection.count()} memories stored"
        )
    return _collection


def get_embedder():
    """Returns sentence transformer for embeddings."""
    global _embedder
    if _embedder is None:
        logger.info("Loading sentence transformer model...")
        _embedder = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Sentence transformer loaded")
    return _embedder


def _embed(text: str) -> list:
    """Creates embedding for text."""
    embedder = get_embedder()
    return embedder.encode(text).tolist()


def store_farmer_memory(
    farmer_id: str,
    memory_type: str,
    content: str,
    metadata: Optional[dict] = None
):
    """
    Stores a long-term memory for a farmer.

    memory_type options:
    - 'farm_profile': farm details (location, size, crops)
    - 'disease_history': past disease detections
    - 'market_activity': selling patterns
    - 'yield_history': past yield records
    - 'preferences': farmer preferences and habits
    """
    collection = get_collection()

    # Create unique ID
    timestamp = datetime.utcnow().isoformat()
    doc_id = f"{farmer_id}:{memory_type}:{timestamp}"

    # Build metadata
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
            embeddings=[_embed(content)],
            documents=[content],
            metadatas=[meta]
        )
        logger.info(
            f"Stored memory for {farmer_id}: "
            f"{memory_type} — {content[:60]}"
        )
        return doc_id
    except Exception as e:
        logger.error(f"Failed to store memory: {e}")
        return None


def retrieve_farmer_memories(
    farmer_id: str,
    query: str,
    n_results: int = 5,
    memory_type: Optional[str] = None
) -> list:
    """
    Retrieves relevant memories for a farmer using semantic search.
    Returns list of relevant memory strings.
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    try:
        # Build where filter
        where = {"farmer_id": farmer_id}
        if memory_type:
            where["memory_type"] = memory_type

        results = collection.query(
            query_embeddings=[_embed(query)],
            n_results=min(n_results, collection.count()),
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        memories = []
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, dist in zip(documents, distances):
            # Only return relevant memories (distance < 1.5)
            if dist < 1.5:
                memories.append(doc)

        logger.info(
            f"Retrieved {len(memories)} memories for "
            f"{farmer_id} — query: '{query[:50]}'"
        )
        return memories

    except Exception as e:
        logger.error(f"Memory retrieval failed: {e}")
        return []


def update_farmer_profile(
    farmer_id: str,
    crop_type: Optional[str] = None,
    region: Optional[str] = None,
    farm_size: Optional[float] = None,
    soil_type: Optional[str] = None
):
    """
    Updates or creates farmer profile memory.
    Called when new farm context is learned.
    """
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

    store_farmer_memory(
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


def store_disease_detection(
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
    store_farmer_memory(
        farmer_id=farmer_id,
        memory_type="disease_history",
        content=content,
        metadata={
            "crop_type": crop_type,
            "disease": disease,
            "urgency": urgency
        }
    )


def store_market_activity(
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
    store_farmer_memory(
        farmer_id=farmer_id,
        memory_type="market_activity",
        content=content,
        metadata={
            "crop_type": crop_type,
            "region": region,
            "price": str(price)
        }
    )


def get_farmer_summary(farmer_id: str) -> str:
    """
    Returns a summary of everything known about a farmer
    for injection into the agent system prompt.
    """
    collection = get_collection()

    if collection.count() == 0:
        return ""

    try:
        where = {"farmer_id": farmer_id}
        results = collection.get(
            where=where,
            include=["documents", "metadatas"]
        )

        documents = results.get("documents", [])
        if not documents:
            return ""

        # Group by type
        profiles = []
        diseases = []
        market = []

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
            summary_parts.append(
                f"Recent disease history: {diseases[-1]}"
            )
        if market:
            summary_parts.append(
                f"Recent market activity: {market[-1]}"
            )

        return "\n".join(summary_parts) if summary_parts else ""

    except Exception as e:
        logger.error(f"Failed to get farmer summary: {e}")
        return ""


def get_memory_stats() -> dict:
    """Returns ChromaDB statistics."""
    try:
        collection = get_collection()
        total = collection.count()
        return {
            "status": "connected",
            "total_memories": total,
            "storage_path": str(CHROMA_PATH)
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
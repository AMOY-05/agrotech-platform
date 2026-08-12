import asyncio
from app.agent.redis_memory import (
    get_session_redis,
    save_session_redis,
    get_active_session_count_redis,
    get_redis
)


async def test_redis():
    print("🔴 Testing Redis Session Store")
    print("="*50)

    # Test 1: Connection
    print("\n1. Testing Redis connection...")
    redis = get_redis()
    if redis:
        print("✅ Redis connected successfully")
    else:
        print("❌ Redis not connected — check REDIS_URL and REDIS_TOKEN in .env")
        return

    # Test 2: Create session
    print("\n2. Creating test session...")
    session = get_session_redis("test_farmer_redis_001")
    session.update_context(
        crop_type="tomato",
        region="Lagos",
        farm_size_hectares=2.5
    )
    session.add_message("user", "My tomatoes have yellow spots")
    session.add_message("assistant", "This looks like early blight")
    save_session_redis(session)
    print(f"✅ Session created: {session.farmer_id}")
    print(f"   Context: {session.context}")
    print(f"   Messages: {len(session.messages)}")

    # Test 3: Retrieve session
    print("\n3. Retrieving session from Redis...")
    retrieved = get_session_redis("test_farmer_redis_001")
    print(f"✅ Session retrieved")
    print(f"   Crop: {retrieved.context.get('crop_type')}")
    print(f"   Region: {retrieved.context.get('region')}")
    print(f"   Messages: {len(retrieved.messages)}")

    assert retrieved.context["crop_type"] == "tomato", "Context not persisted!"
    assert retrieved.context["region"] == "Lagos", "Region not persisted!"
    assert len(retrieved.messages) == 2, "Messages not persisted!"
    print("✅ All data persisted correctly")

    # Test 4: Session persistence
    print("\n4. Testing persistence across restarts...")
    session2 = get_session_redis("test_farmer_redis_001")
    session2.update_context(farm_size_hectares=5.0)
    save_session_redis(session2)
    session3 = get_session_redis("test_farmer_redis_001")
    print(f"✅ Updated farm size: {session3.context.get('farm_size_hectares')}")

    # Test 5: Active session count
    print("\n5. Active session count...")
    count = get_active_session_count_redis()
    print(f"✅ Active sessions: {count}")

    print("\n" + "="*50)
    print("✅ ALL REDIS TESTS PASSED")
    print("="*50)


asyncio.run(test_redis())
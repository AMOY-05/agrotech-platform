import asyncio
from app.core.config import settings

async def test_claude():
    print("\n" + "="*50)
    print("TESTING CLAUDE SONNET")
    print("="*50)
    try:
        from app.services.claude_service import ask_claude
        response = await ask_claude(
            user_message="A Nigerian farmer in Lagos asks: my tomato leaves have yellow spots, what should I do?",
            temperature=0.7,
            max_tokens=300
        )
        print(f"✅ Claude responded:\n{response[:500]}")
    except Exception as e:
        print(f"❌ Claude failed: {e}")


async def test_mms():
    print("\n" + "="*50)
    print("TESTING META MMS")
    print("="*50)
    try:
        import httpx
        if not settings.huggingface_token:
            print("❌ No Hugging Face token configured")
            return

        # Test with a simple API call
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api-inference.huggingface.co/models/facebook/mms-300m",
                headers={"Authorization": f"Bearer {settings.huggingface_token}"}
            )
            print(f"MMS model status: {response.status_code}")
            data = response.json()
            print(f"Response: {data}")
            if response.status_code == 200:
                print("✅ Meta MMS model is accessible")
            elif "loading" in str(data).lower():
                print("⚠️ Model is loading — will be ready in ~30 seconds")
            else:
                print(f"⚠️ Unexpected response: {data}")
    except Exception as e:
        print(f"❌ MMS test failed: {e}")


async def test_groq_fallback():
    print("\n" + "="*50)
    print("TESTING GROQ FALLBACK")
    print("="*50)
    try:
        from app.services.llm_service import ask_llm
        response = await ask_llm(
            user_message="Say hello in one sentence",
            max_tokens=50
        )
        print(f"✅ Groq fallback working: {response}")
    except Exception as e:
        print(f"❌ Groq failed: {e}")


async def main():
    print("🌾 Testing AgroTech AI Services")

    await test_claude()
    await test_mms()
    await test_groq_fallback()

    print("\n" + "="*50)
    print("TESTING COMPLETE")
    print("="*50)


asyncio.run(main())
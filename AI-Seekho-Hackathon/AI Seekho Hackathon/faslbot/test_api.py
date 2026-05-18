import asyncio
from httpx import AsyncClient
from backend.main import app

async def test():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/v1/chat/run-agent", json={"user_query": "hello", "refresh": False, "use_openai": True})
        print(response.status_code)
        print(response.text)

asyncio.run(test())

import sys
sys.path.append(".")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
response = client.post("/api/v1/chat/run-agent", json={"user_query": "hello", "refresh": False, "use_openai": True})
print(response.status_code)
print(response.json() if response.status_code == 200 else response.text)

from fastapi import APIRouter, Query
from gigachat import GigaChat
import os

router = APIRouter()
giga = GigaChat(
    credentials="MDE5YTY4NmEtZDBjOS03OGY5LTkyNmQtNDJjMzAyN2JlZmVkOmUwOTc4YjYwLTZmZjItNGZhNS05ZDQwLTI3NmM4NjgwNTQ0Mw==",
    verify_ssl_certs=False
)


@router.get("/gen")
async def ai_test(
        prompt: str = Query(default="Hello, who are you?")
):
    try:
        response = giga.chat(prompt)

        return {
            "success": True,
            "response": response.choices[0].message.content,
            "model": "GigaChat"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
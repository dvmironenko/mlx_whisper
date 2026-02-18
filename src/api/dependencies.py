"""Зависимости для FastAPI эндпоинтов."""
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.config import API_KEY

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Валидировать API ключ."""
    if not API_KEY:
        # Если API ключ не настроен, разрешить все (для dev)
        return "dev-key"

    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key


async def get_current_api_key(api_key: str = Security(api_key_header)) -> Optional[str]:
    """Получить текущий API ключ (опционально)."""
    if not API_KEY:
        return None
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

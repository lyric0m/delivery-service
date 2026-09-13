import httpx
import os
from fastapi import HTTPException, status
from typing import Optional
from jose import jwt

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def decode_token(token: str) -> Optional[dict]:
    """Декодирование JWT токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None

async def get_user_id(token: str) -> Optional[int]:
    """Получение ID пользователя из токена"""
    payload = decode_token(token)
    if not payload:
        return None
    return payload.get("user_id")

async def get_user_roles(token: str) -> list:
    """Получение ролей пользователя через user-service"""
    try:
        payload = decode_token(token)
        if not payload:
            return []
        
        user_id = payload.get("user_id")
        if not user_id:
            return []
        
        async with httpx.AsyncClient() as client:
            roles_response = await client.get(
                f"{USER_SERVICE_URL}/users/{user_id}/roles",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5.0
            )
            if roles_response.status_code == 200:
                roles = roles_response.json()
                return [role.get("name") for role in roles]
            return []
    except Exception as e:
        print(f"Error getting user roles: {e}")
        return []

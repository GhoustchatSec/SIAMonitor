# backend/app/auth.py
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from cachetools import TTLCache
from fastapi import Depends, Header, HTTPException
from jose import jwt

# ─────────────────────────────────────────────────────────────────────────────
# Конфиг из окружения
# ─────────────────────────────────────────────────────────────────────────────
KC_ISSUER = os.environ.get("KC_ISSUER")  # например: https://host/auth/realms/siamonitor
KC_JWKS_URL = os.environ.get("KC_JWKS_URL")  # напр.: https://host/auth/realms/siamonitor/protocol/openid-connect/certs
KC_FRONTEND_CLIENT_ID = os.getenv("KC_FRONTEND_CLIENT_ID", "frontend")
KC_BACKEND_AUDIENCE = os.getenv("KC_BACKEND_AUDIENCE", "account")
KC_CA_BUNDLE = os.getenv("KC_CA_BUNDLE")  # путь до кастомного корневого сертификата (опционально)

if not KC_ISSUER or not KC_JWKS_URL:
    raise RuntimeError("KC_ISSUER и KC_JWKS_URL обязательны для валидации токена")

# Кэш JWKS на 10 минут
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=600)


# ─────────────────────────────────────────────────────────────────────────────
# JWKS helpers
# ─────────────────────────────────────────────────────────────────────────────
async def _get_jwks() -> Dict[str, Any]:
    if "jwks" in _jwks_cache:
        return _jwks_cache["jwks"]  # type: ignore[index]
    verify_arg: Any = KC_CA_BUNDLE if KC_CA_BUNDLE else True
    async with httpx.AsyncClient(timeout=10.0, verify=verify_arg) as client:
        r = await client.get(KC_JWKS_URL)  # type: ignore[arg-type]
        r.raise_for_status()
        data = r.json()
        _jwks_cache["jwks"] = data
        return data

def _rsa_key_for_kid(jwks: Dict[str, Any], kid: Optional[str]) -> Optional[Dict[str, str]]:
    if not kid:
        return None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid and key.get("kty") == "RSA":
            n = key.get("n"); e = key.get("e")
            if n and e:
                return {"kty": "RSA", "n": n, "e": e}
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Основная проверка токена
# ─────────────────────────────────────────────────────────────────────────────
async def verify_token_and_roles(token: str, need_roles: Optional[List[str]] = None) -> Dict[str, Any]:
    # 1) Заголовок и ключ
    try:
        header = jwt.get_unverified_header(token)
    except Exception as e:
        raise ValueError(f"Invalid JWT header: {e}")
    kid = header.get("kid")
    jwks = await _get_jwks()
    rsa_key = _rsa_key_for_kid(jwks, kid)
    if not rsa_key:
        raise ValueError("No matching RSA JWK for kid")

    # 2) Декод + базовые проверки iss (aud мягко)
    try:
        claims = jwt.decode(
            token,
            rsa_key,  # JWK с 'kty','n','e'
            algorithms=["RS256"],
            options={"verify_aud": False},  # aud проверим ниже вручную
            issuer=KC_ISSUER,
            audience=None,
        )
    except Exception as e:
        raise ValueError(f"JWT decode failed: {e}")

    # 3) Проверка aud (мягкая: принимаем либо frontend, либо backend audience)
    aud = claims.get("aud")
    if aud:
        valid = False
        if isinstance(aud, str):
            valid = (aud == KC_FRONTEND_CLIENT_ID) or (aud == KC_BACKEND_AUDIENCE)
        else:
            valid = any(x in (KC_FRONTEND_CLIENT_ID, KC_BACKEND_AUDIENCE) for x in aud)
        if not valid:
            raise ValueError("Invalid audience")

    # 4) Проверка ролей (если требуют)
    if need_roles:
        roles = (
            claims.get("realm_access", {}).get("roles", [])
            or claims.get("resource_access", {}).get(KC_FRONTEND_CLIENT_ID, {}).get("roles", [])
        )
        roles = roles or []
        for nr in need_roles:
            if nr not in roles:
                raise PermissionError(f"Role '{nr}' required")

    # 5) Срок действия
    exp = claims.get("exp")
    if exp and time.time() > float(exp):
        raise ValueError("Token expired")

    return claims


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI dependencies
# ─────────────────────────────────────────────────────────────────────────────
def _extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1]

async def get_current_user(Authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _extract_bearer_token(Authorization)
    try:
        claims = await verify_token_and_roles(token, need_roles=None)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    # Нормализуем поля, которыми пользуется приложение
    claims.setdefault("realm_access", {"roles": claims.get("realm_access", {}).get("roles", []) or []})
    return claims

async def require_teacher(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    roles = user.get("realm_access", {}).get("roles", []) or []
    if "teacher" not in roles:
        # На всякий — перепроверим через токен (если кто-то подменил claims)
        # но обычно достаточно проверки списка выше.
        raise HTTPException(status_code=403, detail="Teacher role required")
    return user


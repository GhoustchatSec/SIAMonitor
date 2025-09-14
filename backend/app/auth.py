import os
import time
import httpx
from jose import jwt
from cachetools import TTLCache

KC_ISSUER = os.environ["KC_ISSUER"]
KC_JWKS_URL = os.environ["KC_JWKS_URL"]
KC_FRONTEND_CLIENT_ID = os.getenv("KC_FRONTEND_CLIENT_ID", "frontend")
KC_BACKEND_AUDIENCE = os.getenv("KC_BACKEND_AUDIENCE", "account")

_jwks_cache = TTLCache(maxsize=1, ttl=600)

async def _get_jwks():
  if "jwks" in _jwks_cache:
    return _jwks_cache["jwks"]
  async with httpx.AsyncClient(timeout=10.0, verify=True) as client:
    r = await client.get(KC_JWKS_URL)
    r.raise_for_status()
    data = r.json()
    _jwks_cache["jwks"] = data
    return data

def _rsa_key_for_kid(jwks, kid):
  for key in jwks.get("keys", []):
    if key.get("kid") == kid and key.get("kty") == "RSA":
      n = key.get("n"); e = key.get("e")
      if n and e:
        return {"kty": "RSA", "n": n, "e": e}
  return None

async def verify_token_and_roles(token: str, need_roles: list[str] | None = None) -> dict:
  header = jwt.get_unverified_header(token)
  kid = header.get("kid")

  jwks = await _get_jwks()
  rsa_key = _rsa_key_for_kid(jwks, kid)
  if not rsa_key:
    raise ValueError("No matching RSA JWK for kid")

  try:
    claims = jwt.decode(
      token,
      rsa_key,
      algorithms=["RS256"],
      options={"verify_aud": False},
      issuer=KC_ISSUER,
      audience=None
    )
  except Exception as e:
    raise ValueError(f"JWT decode failed: {e}")

  aud = claims.get("aud")
  if aud:
    valid = False
    if isinstance(aud, str):
      valid = (aud == KC_FRONTEND_CLIENT_ID) or (aud == KC_BACKEND_AUDIENCE)
    else:
      valid = any(x in (KC_FRONTEND_CLIENT_ID, KC_BACKEND_AUDIENCE) for x in aud)
    if not valid:
      raise ValueError("Invalid audience")

  if need_roles:
    roles = (
      claims.get("realm_access", {}).get("roles", []) or
      claims.get("resource_access", {}).get(KC_FRONTEND_CLIENT_ID, {}).get("roles", [])
    )
    for nr in need_roles:
      if nr not in roles:
        raise PermissionError(f"Role '{nr}' required")

  exp = claims.get("exp")
  if exp and time.time() > exp:
    raise ValueError("Token expired")

  return claims


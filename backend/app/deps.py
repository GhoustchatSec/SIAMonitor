# backend/app/deps.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .auth import verify_token_and_roles

security = HTTPBearer(auto_error=False)

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    if not creds or not creds.scheme.lower() == "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = creds.credentials
    try:
        claims = await verify_token_and_roles(token)
        return claims
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")

async def require_teacher(user=Depends(get_current_user)):
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" not in roles:
        raise HTTPException(status_code=403, detail="Teacher role required")
    return user

async def require_student(user=Depends(get_current_user)):
    roles = user.get("realm_access", {}).get("roles", [])
    if "student" not in roles:
        raise HTTPException(status_code=403, detail="Student role required")
    return user


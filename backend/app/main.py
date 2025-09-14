from fastapi import FastAPI, Depends
from .db import Base, engine
from . import models  
from .deps import get_current_user, require_teacher, require_student  
from .routes import router as api_router

app = FastAPI(title="SIAMonitor API")

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backend"}

@app.get("/api/me")
async def me(user = Depends(get_current_user)):
    return {
        "sub": user.get("sub"),
        "preferred_username": user.get("preferred_username"),
        "email": user.get("email"),
        "roles": user.get("realm_access", {}).get("roles", []),
        "iss": user.get("iss"),
        "aud": user.get("aud"),
    }

@app.get("/api/teacher/ping")
async def teacher_ping(user = Depends(require_teacher)):
    return {"ok": True, "role": "teacher"}

@app.get("/api/student/ping")
async def student_ping(user = Depends(require_student)):
    return {"ok": True, "role": "student"}


app.include_router(api_router)


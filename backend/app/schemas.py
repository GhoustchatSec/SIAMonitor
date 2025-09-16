from pydantic import BaseModel, Field, constr, conint
from typing import Optional, List, Literal
from datetime import datetime

# --- профили ---
class ProfileUpdate(BaseModel):
    mode: Optional[Literal["participant", "lead"]] = None  # учителю игнорируется
    group_no: Optional[str] = Field(default=None, max_length=64)
    tg: Optional[str] = Field(default=None, max_length=128)

class ProfileOut(BaseModel):
    sub: str
    username: Optional[str] = None
    full_name: Optional[str] = None   # берём из KC/БД, только вывод
    email: Optional[str] = None       # берём из KC/БД, только вывод
    mode: Optional[Literal["participant", "lead", "teacher"]] = None
    group_no: Optional[str] = None    # редактирует только студент
    tg: Optional[str] = None          # редактируют все

    class Config:
        from_attributes = True

# --- проекты ---
class ProjectCreate(BaseModel):
    name: str
    description: Optional[constr(max_length=3000)] = None
    repo_url: Optional[str] = None
    tracker_url: Optional[str] = None
    mobile_repo_url: Optional[str] = None  # проверим на бэке, если 5 участников

class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    repo_url: Optional[str] = None
    tracker_url: Optional[str] = None
    mobile_repo_url: Optional[str] = None
    lead_sub: str
    class Config: from_attributes = True

class MemberAdd(BaseModel):
    member_sub: str
    role_in_team: Optional[str] = None

class MemberOut(BaseModel):
    id: int
    project_id: int
    role_in_team: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    group_no: Optional[str] = None
    class Config: from_attributes = True

# --- майлстоуны ---
class MilestoneCreate(BaseModel):
    title: str
    deadline: Optional[str] = None  # YYYY-MM-DD

class MilestoneOut(BaseModel):
    id: int
    title: str
    created_at: datetime | None = None
    deadline: Optional[str] = None
    class Config: from_attributes = True

class MilestoneIn(BaseModel):
    # Ввод с фронта для создания майлстоуна
    title: str = Field(..., min_length=1, max_length=200)
    deadline: Optional[str] = None  # ожидаем 'YYYY-MM-DD' или None

# --- оценки по майлстоуну ---
class GradeSet(BaseModel):
    grade: int = Field(ge=0, le=5)

class GradeOut(BaseModel):
    project_id: int
    milestone_id: int
    grade: Optional[int] = None
    presentation_path: Optional[str] = None
    report_path: Optional[str] = None
    graded_by_sub: Optional[str] = None
    graded_at: Optional[datetime] = None

class RatingRowOut(BaseModel):
    project_id: int
    project_name: str
    team_size: int
    avg_grade: Optional[float] = None
    grades: List[int] = []

class SuggestOut(BaseModel):
    score: int  # 0..5
    commits: int
    lines_changed: int
    details: str

class GradeIn(BaseModel):
    grade: conint(ge=0, le=5)

from pydantic import BaseModel, Field, constr
from typing import Optional, List


class ProfileUpdate(BaseModel):
    mode: Optional[constr(pattern="^(participant|lead)$")] = None
    full_name: Optional[str] = None
    group_no: Optional[str] = None
    email_corp: Optional[str] = None
    tg: Optional[str] = None

class ProfileOut(BaseModel):
    sub: str
    mode: str
    full_name: Optional[str] = None
    group_no: Optional[str] = None
    email_corp: Optional[str] = None
    tg: Optional[str] = None
    class Config: from_attributes = True


class ProjectCreate(BaseModel):
    name: str
    description: Optional[constr(max_length=3000)] = None
    repo_url: Optional[str] = None
    tracker_url: Optional[str] = None
    mobile_repo_url: Optional[str] = None 

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
    member_sub: str
    role_in_team: Optional[str] = None
    class Config: from_attributes = True


class MilestoneCreate(BaseModel):
    title: str
    deadline: Optional[str] = None 

class MilestoneOut(BaseModel):
    id: int
    title: str
    created_at: Optional[str] = None
    deadline: Optional[str] = None
    class Config: from_attributes = True


class GradeSet(BaseModel):
    grade: int = Field(ge=0, le=5)

class GradeOut(BaseModel):
    project_id: int
    milestone_id: int
    grade: Optional[int] = None
    presentation_path: Optional[str] = None
    report_path: Optional[str] = None


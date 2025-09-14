from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from .db import get_db
from .models import (Project, TeamMember, Milestone, ProjectMilestoneGrade, UserProfile)
from .schemas import (ProjectCreate, ProjectOut, MemberAdd, MemberOut,
                      MilestoneCreate, MilestoneOut, GradeSet, GradeOut, ProfileUpdate, ProfileOut)
from .deps import get_current_user, require_teacher, require_student
from datetime import datetime
import os

router = APIRouter(prefix="/api")

def _sub(user) -> str:
    sub = user.get("sub")
    if not sub: raise HTTPException(401, "No sub in token")
    return sub


@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof:
        prof = UserProfile(sub=sub, username=user.get("preferred_username"), email=user.get("email"))
        db.add(prof); db.commit(); db.refresh(prof)
    return prof

@router.post("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof:
        prof = UserProfile(sub=sub, username=user.get("preferred_username"), email=user.get("email"))
        db.add(prof); db.commit(); db.refresh(prof)
    if payload.mode and payload.mode != prof.mode and payload.mode == "lead":
        db.query(TeamMember).filter(TeamMember.member_sub == sub).delete()
    if payload.mode:
        prof.mode = payload.mode
    if payload.full_name is not None: prof.full_name = payload.full_name
    if payload.group_no is not None: prof.group_no = payload.group_no
    if payload.email_corp is not None: prof.email_corp = payload.email_corp
    if payload.tg is not None: prof.tg = payload.tg
    db.commit(); db.refresh(prof)
    return prof

@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof or prof.mode != "lead":
        raise HTTPException(403, "Only team lead can create a project")
    existing = db.query(Project).filter(Project.lead_sub == sub).first()
    if existing:
        raise HTTPException(400, "Lead already has a project")
    p = Project(
        name=payload.name,
        description=payload.description,
        repo_url=payload.repo_url,
        tracker_url=payload.tracker_url,
        mobile_repo_url=payload.mobile_repo_url,
        lead_sub=sub
    )
    db.add(p); db.commit(); db.refresh(p)
    db.add(TeamMember(project_id=p.id, member_sub=sub, role_in_team="lead"))
    db.commit()
    return p

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" in roles:
        return db.query(Project).order_by(Project.id.desc()).all()
    q = (db.query(Project)
           .join(TeamMember, TeamMember.project_id == Project.id)
           .filter(TeamMember.member_sub == sub)
           .order_by(Project.id.desc()))
    return q.all()

@router.post("/projects/{project_id}/members", response_model=MemberOut)
def add_member(project_id: int, payload: MemberAdd, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    p = db.get(Project, project_id)
    if not p: raise HTTPException(404, "Project not found")
    if p.lead_sub != sub: raise HTTPException(403, "Only lead can add members")
    count = db.query(TeamMember).filter(TeamMember.project_id == project_id).count()
    if count >= 5: raise HTTPException(400, "Team is full (max 5)")
    m = TeamMember(project_id=project_id, member_sub=payload.member_sub, role_in_team=payload.role_in_team)
    db.add(m); db.commit(); db.refresh(m)
    count += 1
    if count == 5 and not p.mobile_repo_url:
        raise HTTPException(400, "With 5 members, mobile_repo_url is required")
    return m

@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def get_members(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" in roles:
        return db.query(TeamMember).where(TeamMember.project_id == project_id).all()
    is_member = db.query(TeamMember).filter(TeamMember.project_id == project_id, TeamMember.member_sub == sub).first()
    if not is_member:
        raise HTTPException(403, "Forbidden")
    return db.query(TeamMember).where(TeamMember.project_id == project_id).all()

@router.post("/milestones", response_model=MilestoneOut)
def create_milestone(payload: MilestoneCreate, db: Session = Depends(get_db), user=Depends(require_teacher)):
    ms = Milestone(title=payload.title, deadline=payload.deadline)
    db.add(ms); db.commit(); db.refresh(ms)
    return ms

@router.get("/milestones", response_model=list[MilestoneOut])
def list_milestones(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Milestone).order_by(Milestone.id.desc()).all()

@router.post("/projects/{project_id}/milestones/{milestone_id}/grade", response_model=GradeOut)
def set_grade(project_id: int, milestone_id: int, payload: GradeSet, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if not db.get(Project, project_id): raise HTTPException(404, "Project not found")
    if not db.get(Milestone, milestone_id): raise HTTPException(404, "Milestone not found")
    rel = (db.query(ProjectMilestoneGrade)
             .filter(ProjectMilestoneGrade.project_id == project_id,
                     ProjectMilestoneGrade.milestone_id == milestone_id)
             .first())
    if not rel:
        rel = ProjectMilestoneGrade(project_id=project_id, milestone_id=milestone_id)
        db.add(rel); db.commit(); db.refresh(rel)
    rel.grade = payload.grade
    rel.graded_by_sub = _sub(user)
    rel.graded_at = datetime.utcnow()
    db.commit(); db.refresh(rel)
    return GradeOut(
        project_id=project_id, milestone_id=milestone_id,
        grade=rel.grade, presentation_path=rel.presentation_path, report_path=rel.report_path
    )

UPLOAD_DIR = "/app/uploads"

@router.post("/projects/{project_id}/milestones/{milestone_id}/files", response_model=GradeOut)
def upload_files(project_id: int, milestone_id: int,
                 presentation: UploadFile | None = File(None),
                 report: UploadFile | None = File(None),
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if not db.get(Project, project_id): raise HTTPException(404, "Project not found")
    if not db.get(Milestone, milestone_id): raise HTTPException(404, "Milestone not found")
    if "teacher" not in roles:
        is_member = db.query(TeamMember).filter(TeamMember.project_id == project_id, TeamMember.member_sub == sub).first()
        if not is_member: raise HTTPException(403, "Forbidden")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    rel = (db.query(ProjectMilestoneGrade)
             .filter(ProjectMilestoneGrade.project_id == project_id,
                     ProjectMilestoneGrade.milestone_id == milestone_id).first())
    if not rel:
        rel = ProjectMilestoneGrade(project_id=project_id, milestone_id=milestone_id)
        db.add(rel); db.commit(); db.refresh(rel)
    if presentation:
        path = f"{UPLOAD_DIR}/p_{project_id}_{milestone_id}_{presentation.filename}"
        with open(path, "wb") as f: f.write(presentation.file.read())
        rel.presentation_path = path
    if report:
        path = f"{UPLOAD_DIR}/r_{project_id}_{milestone_id}_{report.filename}"
        with open(path, "wb") as f: f.write(report.file.read())
        rel.report_path = path
    db.commit(); db.refresh(rel)
    return GradeOut(project_id=project_id, milestone_id=milestone_id,
                    grade=rel.grade, presentation_path=rel.presentation_path, report_path=rel.report_path)

@router.get("/projects/{project_id}/milestones/with-state", response_model=list[GradeOut])
def milestones_state(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" not in roles:
        is_member = db.query(TeamMember).filter(TeamMember.project_id == project_id, TeamMember.member_sub == sub).first()
        if not is_member: raise HTTPException(403, "Forbidden")

    m_ids = [m.id for m in db.query(Milestone).order_by(Milestone.id.asc()).all()]
    out = []
    for mid in m_ids:
        rel = (db.query(ProjectMilestoneGrade)
                .filter(ProjectMilestoneGrade.project_id == project_id,
                        ProjectMilestoneGrade.milestone_id == mid).first())
        out.append(GradeOut(
            project_id=project_id, milestone_id=mid,
            grade=rel.grade if rel else None,
            presentation_path=rel.presentation_path if rel else None,
            report_path=rel.report_path if rel else None
        ))
    return out

@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    if "teacher" in roles:
        return p
    is_member = db.query(TeamMember).filter(TeamMember.project_id == project_id, TeamMember.member_sub == sub).first()
    if not is_member:
        raise HTTPException(403, "Forbidden")
    return p


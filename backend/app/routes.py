from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from .db import get_db
from .models import (Project, TeamMember, Milestone, ProjectMilestoneGrade, UserProfile)
from .schemas import (ProjectCreate, ProjectOut, MemberAdd, MemberOut,
                      MilestoneCreate, MilestoneOut, GradeSet, GradeIn, GradeOut, ProfileUpdate, ProfileOut, MilestoneIn)
from .deps import get_current_user, require_teacher, require_student
from datetime import datetime, timedelta, timezone
import os
import re
import shutil
from datetime import datetime, timezone
import httpx
from sqlalchemy import func
from .schemas import RatingRowOut, SuggestOut
import certifi
from typing import Dict, List, Tuple
from pathlib import Path
from fastapi import UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from .auth import get_current_user, require_teacher

router = APIRouter(prefix="/api")

def _sub(user) -> str:
    sub = user.get("sub")
    if not sub:
        raise HTTPException(401, "No sub in token")
    return sub

def _roles(user) -> list[str]:
    return user.get("realm_access", {}).get("roles", []) or []

# ---------- Профиль пользователя (ЛК) ----------
@router.get("/profile", response_model=ProfileOut)
def get_profile(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof:
        prof = UserProfile(
            sub=sub,
            username=user.get("preferred_username"),
            email=user.get("email"),
        )
        db.add(prof); db.commit(); db.refresh(prof)

    # Синхронизируем ФИО/Email/username из токена KC (источник правды)
    given = (user.get("given_name") or "").strip()
    family = (user.get("family_name") or "").strip()
    full_name = (given + " " + family).strip() or None
    if full_name and prof.full_name != full_name:
        prof.full_name = full_name

    email = (user.get("email") or "").strip() or None
    if email and prof.email != email:
        prof.email = email

    uname = user.get("preferred_username")
    if uname and prof.username != uname:
        prof.username = uname

    # Помечаем преподавателей явным mode='teacher' (для фронта)
    if "teacher" in _roles(user) and prof.mode != "teacher":
        prof.mode = "teacher"

    db.commit(); db.refresh(prof)
    return prof

@router.post("/profile", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = _roles(user)

    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof:
        prof = UserProfile(
            sub=sub,
            username=user.get("preferred_username"),
            email=user.get("email"),
        )
        db.add(prof); db.commit(); db.refresh(prof)

    is_teacher = "teacher" in roles

    # Режим аккаунта: учителю запрещено менять;
    # студент может participant/lead (при lead — вычищаем членства)
    if not is_teacher and payload.mode in ("participant", "lead"):
        if payload.mode != prof.mode:
            if payload.mode == "lead":
                db.query(TeamMember).filter(TeamMember.member_sub == sub).delete()
            prof.mode = payload.mode

    # Редактируемые поля
    if not is_teacher and payload.group_no is not None:
        prof.group_no = payload.group_no
    if payload.tg is not None:
        prof.tg = payload.tg

    # Снова подливаем ФИО/email из токена KC (read-only со стороны формы)
    given = (user.get("given_name") or "").strip()
    family = (user.get("family_name") or "").strip()
    full_name = (given + " " + family).strip() or None
    if full_name and prof.full_name != full_name:
        prof.full_name = full_name

    email = (user.get("email") or "").strip() or None
    if email and prof.email != email:
        prof.email = email

    uname = user.get("preferred_username")
    if uname and prof.username != uname:
        prof.username = uname

    db.commit(); db.refresh(prof)
    return prof

# ---------- Проекты ----------
@router.post("/projects", response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    # проверим, что юзер — lead
    prof = db.query(UserProfile).filter(UserProfile.sub == sub).first()
    if not prof or prof.mode != "lead":
        raise HTTPException(403, "Only team lead can create a project")
    # один lead — один проект
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
    # добавим лида как участника
    db.add(TeamMember(project_id=p.id, member_sub=sub, role_in_team="lead"))
    db.commit()
    return p

@router.get("/projects", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" in roles:
        return db.query(Project).order_by(Project.id.desc()).all()
    # студент видит только свои проекты
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

    # Проверяем, что студент существует
    prof = db.query(UserProfile).filter(UserProfile.sub == payload.member_sub).first()
    if not prof: raise HTTPException(400, "Student not found by UUID")
    if prof.mode == "teacher": raise HTTPException(400, "Only students can be added")

    # Ограничение размера и уникальность
    count = db.query(TeamMember).filter(TeamMember.project_id == project_id).count()
    if count >= 5: raise HTTPException(400, "Team is full (max 5)")

    exists = db.query(TeamMember).filter(
        TeamMember.project_id == project_id,
        TeamMember.member_sub == payload.member_sub
    ).first()
    if exists: raise HTTPException(400, "Student already in this project")

    m = TeamMember(project_id=project_id, member_sub=payload.member_sub, role_in_team=payload.role_in_team)
    db.add(m); db.commit(); db.refresh(m)

    # Проверка mobile_repo_url при достижении 5 человек
    count += 1
    if count == 5 and not p.mobile_repo_url:
        raise HTTPException(400, "With 5 members, mobile_repo_url is required")

    return {
        "id": m.id,
        "project_id": m.project_id,
        "member_sub": m.member_sub,
        "role_in_team": m.role_in_team,
        "full_name": prof.full_name or prof.username or prof.email
    }

@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def get_members(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", [])
    if "teacher" in roles:
        return db.query(TeamMember).where(TeamMember.project_id == project_id).all()
    # студент — только если участник проекта
    is_member = db.query(TeamMember).filter(TeamMember.project_id == project_id, TeamMember.member_sub == sub).first()
    if not is_member:
        raise HTTPException(403, "Forbidden")
    return db.query(TeamMember).where(TeamMember.project_id == project_id).all()

# ---------- Майлстоуны (глобальные) ----------
@router.post("/milestones", response_model=MilestoneOut)
def create_milestone(payload: MilestoneIn, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if payload.deadline:
        try:
            dd = datetime.strptime(payload.deadline, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(400, "Invalid date format, use YYYY-MM-DD")
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date()
        if dd < tomorrow:
            raise HTTPException(400, "Deadline must be from tomorrow and later")

    m = Milestone(title=payload.title, deadline=payload.deadline)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

@router.get("/milestones", response_model=list[MilestoneOut])
def list_milestones(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Milestone).order_by(Milestone.id.desc()).all()

# ---------- Оценки и файлы по майлстоуну проекта ----------
@router.post("/projects/{project_id}/milestones/{milestone_id}/grade", response_model=GradeOut)
def set_grade(project_id: int, milestone_id: int, payload: GradeSet, db: Session = Depends(get_db), user=Depends(require_teacher)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    if not db.get(Milestone, milestone_id):
        raise HTTPException(404, "Milestone not found")

    rel = (db.query(ProjectMilestoneGrade)
             .filter(ProjectMilestoneGrade.project_id == project_id,
                     ProjectMilestoneGrade.milestone_id == milestone_id)
             .first())

    if not rel:
        rel = ProjectMilestoneGrade(
            project_id=project_id,
            milestone_id=milestone_id,
            grade=payload.grade,
            graded_by_sub=_sub(user),
            graded_at=datetime.utcnow(),
        )
        db.add(rel)
    else:
        rel.grade = payload.grade
        rel.graded_by_sub = _sub(user)
        rel.graded_at = datetime.utcnow()

    db.commit()
    db.refresh(rel)

    return GradeOut(
        project_id=project_id,
        milestone_id=milestone_id,
        grade=rel.grade,
        presentation_path=rel.presentation_path,
        report_path=rel.report_path
    )

#UPLOAD_DIR = "/app/uploads"  # смонтируем том
UPLOAD_ROOT = Path("/app/uploads")

@router.post("/projects/{project_id}/milestones/{milestone_id}/files", response_model=GradeOut)
def upload_files(project_id: int, milestone_id: int,
                 presentation: UploadFile | None = File(None),
                 report: UploadFile | None = File(None),
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    proj = db.get(Project, project_id)
    if not proj: raise HTTPException(404, "Project not found")
    if not db.get(Milestone, milestone_id): raise HTTPException(404, "Milestone not found")

    # Только тим-лид может загружать
    if proj.lead_sub != sub:
        raise HTTPException(403, "Only team lead can upload files")

    rel = (db.query(ProjectMilestoneGrade)
             .filter(ProjectMilestoneGrade.project_id == project_id,
                     ProjectMilestoneGrade.milestone_id == milestone_id).first())
    if not rel:
        rel = ProjectMilestoneGrade(project_id=project_id, milestone_id=milestone_id)
        db.add(rel)

    target_dir = UPLOAD_ROOT / str(project_id) / str(milestone_id)
    target_dir.mkdir(parents=True, exist_ok=True)

    def _safe(name: str) -> str:
        name = os.path.basename(name or "")
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", name) or "file.bin"

    if presentation:
        p = target_dir / f"presentation_{_safe(presentation.filename)}"
        with open(p, "wb") as f: f.write(presentation.file.read())
        rel.presentation_path = str(p.relative_to(UPLOAD_ROOT))

    if report:
        p = target_dir / f"report_{_safe(report.filename)}"
        with open(p, "wb") as f: f.write(report.file.read())
        rel.report_path = str(p.relative_to(UPLOAD_ROOT))

    db.commit(); db.refresh(rel)
    return GradeOut(project_id=project_id, milestone_id=milestone_id,
                    grade=rel.grade, presentation_path=rel.presentation_path, report_path=rel.report_path,
                    graded_by_sub=rel.graded_by_sub, graded_at=rel.graded_at)

@router.get("/files/{project_id}/{milestone_id}/{kind}")
def download_file(project_id: int, milestone_id: int, kind: str,
                  db: Session = Depends(get_db), user=Depends(get_current_user)):
    sub = _sub(user)
    roles = user.get("realm_access", {}).get("roles", []) or []

    proj = db.get(Project, project_id)
    if not proj: raise HTTPException(404, "Project not found")

    # Скачивать можно преподавателю и членам команды (включая лида)
    if "teacher" not in roles:
        is_member = db.query(TeamMember).filter_by(project_id=project_id, member_sub=sub).first()
        if not is_member and proj.lead_sub != sub:
            raise HTTPException(403, "Forbidden")

    rel = db.query(ProjectMilestoneGrade).filter_by(project_id=project_id, milestone_id=milestone_id).first()
    if not rel: raise HTTPException(404, "Files not found")

    rel_path = rel.presentation_path if kind == "presentation" else rel.report_path if kind == "report" else None
    if not rel_path: raise HTTPException(404, "File not uploaded")

    fp = UPLOAD_ROOT / rel_path
    if not fp.exists(): raise HTTPException(404, "File missing on server")

    return FileResponse(str(fp), filename=fp.name)

@router.get("/projects/{project_id}/milestones/with-state", response_model=list[GradeOut])
def milestones_state(project_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # доступ: участник проекта или преподаватель
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

# ---------- Рейтинг команд (учитель видит всех) ----------
@router.get("/rating", response_model=list[RatingRowOut])
def get_rating(db: Session = Depends(get_db), user=Depends(require_teacher)):
    # считаем team_size отдельно (без дублирования оценок)
    team_sizes = dict(
        db.query(TeamMember.project_id, func.count(TeamMember.id))
          .group_by(TeamMember.project_id).all()
    )
    # собираем оценки по проектам (без JOIN с участниками!)
    rows = (
        db.query(ProjectMilestoneGrade.project_id, ProjectMilestoneGrade.grade)
          .filter(ProjectMilestoneGrade.grade.isnot(None)).all()
    )
    grades_by_proj = {}
    for pid, g in rows:
        grades_by_proj.setdefault(pid, []).append(int(g))

    projects = db.query(Project.id, Project.name).order_by(Project.id.asc()).all()
    out = []
    for pid, name in projects:
        gs = grades_by_proj.get(pid, [])
        avg = (sum(gs)/len(gs)) if gs else None
        out.append(RatingRowOut(
            project_id=pid, project_name=name,
            team_size=int(team_sizes.get(pid, 0)),
            avg_grade=avg, grades=gs
        ))
    # сортировка по средней убыв., затем по id
    out.sort(key=lambda r: (-(r.avg_grade if r.avg_grade is not None else -1e9), r.project_id))
    return out

# ---------- Подсказка оценки по GitHub (0..5) ----------
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or None

def _parse_repo(url: str) -> tuple[str, str] | None:
    """Вернёт (owner, repo) из https://github.com/owner/repo(.git)? ..."""
    if not url: 
        return None
    m = re.search(r"github\.com[:/]+([^/]+)/([^/\s]+)", url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    repo = repo[:-4] if repo.endswith(".git") else repo
    return owner, repo

async def _github_stats(owner: str, repo: str, since_iso: str, until_iso: str) -> tuple[int, int]:
    """
    Возвращает (commits, lines_changed) за интервал.
    Реализация простая: листим коммиты (пагинация до 100 шт), для каждого тащим деталь и суммируем additions+deletions.
    Этого достаточно для подсказки 0..5.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    commits = 0
    lines = 0
    async with httpx.AsyncClient(timeout=10.0, verify=certifi.where()) as client:
        page = 1
        while page <= 5:  # максимум ~500 коммитов смотрим (5*100) — достаточно для оценки
            r = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"since": since_iso, "until": until_iso, "per_page": 100, "page": page},
            )
            if r.status_code == 422:
                # invalid params / repo empty
                break
            r.raise_for_status()
            arr = r.json()
            if not arr:
                break
            for c in arr:
                sha = c.get("sha")
                if not sha:
                    continue
                commits += 1
                # деталь коммита — чтобы достать additions/deletions
                r2 = await client.get(
                    f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}",
                    headers=headers,
                )
                if r2.status_code == 404:
                    continue
                r2.raise_for_status()
                det = r2.json()
                stats = det.get("stats") or {}
                lines += int(stats.get("additions") or 0)
                lines += int(stats.get("deletions") or 0)
            if len(arr) < 100:
                break
            page += 1
    return commits, lines

def _score_from_activity(commits: int, lines: int) -> int:
    """
    Простейшая формула → 0..5.
    Нормируем: 20 коммитов = максимум по коммитам; 2000 строк = максимум по строкам.
    Вес: 0.6 по коммитам, 0.4 по строкам. Округляем до целого и клиппим.
    """
    c_part = min(commits / 20.0, 1.0)
    l_part = min(lines / 2000.0, 1.0)
    raw = 5.0 * (0.6 * c_part + 0.4 * l_part)
    s = int(round(raw))
    return max(0, min(5, s))

@router.post("/projects/{project_id}/milestones/{milestone_id}/suggest", response_model=SuggestOut)
async def suggest_grade(project_id: int, milestone_id: int, db: Session = Depends(get_db), user=Depends(require_teacher)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    m = db.get(Milestone, milestone_id)
    if not m:
        raise HTTPException(404, "Milestone not found")
    if not p.repo_url:
        raise HTTPException(400, "Project has no main repo_url")

    parsed = _parse_repo(p.repo_url)
    if not parsed:
        raise HTTPException(400, "Unsupported repo_url format (need https://github.com/owner/repo)")
    owner, repo = parsed

    since_dt = m.created_at or datetime.now(timezone.utc)
    until_dt = datetime.now(timezone.utc)
    since_iso = since_dt.astimezone(timezone.utc).isoformat()
    until_iso = until_dt.astimezone(timezone.utc).isoformat()

    commits, lines = await _github_stats(owner, repo, since_iso, until_iso)
    score = _score_from_activity(commits, lines)
    return SuggestOut(
        score=score,
        commits=commits,
        lines_changed=lines,
        details=f"{owner}/{repo} from {since_iso} to {until_iso}",
    )

@router.post("/admin/wipe")
def admin_wipe(
    db: Session = Depends(get_db),
    user=Depends(require_teacher)  # доступ только преподавателю
):
    # 1) Удаляем загруженные файлы (полностью каталог uploads)
    try:
        if UPLOAD_ROOT.exists():
            shutil.rmtree(UPLOAD_ROOT)
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        # не валим очистку БД, но сообщим в ответе
        files_error = str(e)
    else:
        files_error = None

    # 2) Чистим БД в корректном порядке в одной транзакции
    #    - оценки (связи проект<->майлстоун)
    #    - участники команд
    #    - проекты
    #    - майлстоуны
    #    - профили студентов (оставляем только teacher)
    deleted = {"grades": 0, "members": 0, "projects": 0, "milestones": 0, "student_profiles": 0}

    try:
        # оценки
        deleted["grades"] = db.query(ProjectMilestoneGrade).delete(synchronize_session=False)

        # участники
        deleted["members"] = db.query(TeamMember).delete(synchronize_session=False)

        # проекты
        deleted["projects"] = db.query(Project).delete(synchronize_session=False)

        # майлстоуны
        deleted["milestones"] = db.query(Milestone).delete(synchronize_session=False)

        # профили: удалить всех, у кого mode != 'teacher' (или NULL)
        q_profiles = db.query(UserProfile).filter(UserProfile.mode != "teacher")
        # В Postgres сравнение с NULL даст NULL, поэтому удалим и те, где mode IS NULL
        # корректнее так:
        q_profiles = db.query(UserProfile).filter(
            (UserProfile.mode != "teacher") | (UserProfile.mode.is_(None))
        )
        deleted["student_profiles"] = q_profiles.delete(synchronize_session=False)

        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Database wipe failed: {e!s}")

    return {
        "ok": True,
        "deleted": deleted,
        "files_error": files_error,
    }

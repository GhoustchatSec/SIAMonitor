from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

# --- Пользовательский профиль для ЛК ---
class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sub: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(256))
    # ЛК по ТЗ
    mode: Mapped[str] = mapped_column(String(16), default="participant") # participant|lead
    full_name: Mapped[str | None] = mapped_column(String(256))
    group_no: Mapped[str | None] = mapped_column(String(64))
    email_corp: Mapped[str | None] = mapped_column(String(256))
    tg: Mapped[str | None] = mapped_column(String(64))
    avatar_path: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

# --- Глобальные майлстоуны (общие для всех проектов) ---
class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    deadline: Mapped[str | None] = mapped_column(String(32)) # YYYY-MM-DD

# --- Проект (один lead, до 5 участников всего) ---
class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)      # проверим длину в схеме
    repo_url: Mapped[str | None] = mapped_column(String(300))
    tracker_url: Mapped[str | None] = mapped_column(String(300))
    mobile_repo_url: Mapped[str | None] = mapped_column(String(300))
    lead_sub: Mapped[str] = mapped_column(String(64), index=True)  # sub тим-лида
    created_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())

    members: Mapped[list["TeamMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    grades: Mapped[list["ProjectMilestoneGrade"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class TeamMember(Base):
    __tablename__ = "team_members"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    member_sub: Mapped[str] = mapped_column(String(64), index=True)
    role_in_team: Mapped[str | None] = mapped_column(String(64))
    added_at: Mapped["DateTime"] = mapped_column(DateTime, server_default=func.now())
    project: Mapped["Project"] = relationship(back_populates="members")

    __table_args__ = (
        UniqueConstraint("project_id", "member_sub", name="uq_project_member"),
    )

# --- Оценка/файлы проекта по майлстоуну ---
class ProjectMilestoneGrade(Base):
    __tablename__ = "project_milestone_grades"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    milestone_id: Mapped[int] = mapped_column(ForeignKey("milestones.id", ondelete="CASCADE"), index=True)
    grade: Mapped[int | None] = mapped_column(Integer)  # 0..5
    presentation_path: Mapped[str | None] = mapped_column(String(512))
    report_path: Mapped[str | None] = mapped_column(String(512))
    graded_by_sub: Mapped[str | None] = mapped_column(String(64))
    graded_at: Mapped["DateTime"] = mapped_column(DateTime)

    project: Mapped["Project"] = relationship(back_populates="grades")


from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Resolve repo root (parent of web/)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = os.getenv("TCM_SQLITE_PATH", str(_REPO_ROOT / "web" / "backend" / "data" / "tcm.db"))
os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema() -> None:
    """Adds columns introduced after first deploy (SQLite has no IF NOT EXISTS for columns)."""
    try:
        inspector = inspect(engine)
        if inspector.has_table("users"):
            cols = {c["name"] for c in inspector.get_columns("users")}
            with engine.begin() as conn:
                if "phone" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
                if "email" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
                if "nickname" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN nickname VARCHAR(64)"))
                if "avatar_url" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512)"))
                if "company" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN company VARCHAR(128)"))
                if "role" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(32) DEFAULT 'enterprise'"))
            cols_after = {c["name"] for c in inspect(engine).get_columns("users")}
            if "role" in cols_after:
                with engine.begin() as conn:
                    conn.execute(text("UPDATE users SET role = 'enterprise' WHERE role IS NULL OR TRIM(role) = ''"))
        if inspector.has_table("test_cases"):
            tc_cols = {c["name"] for c in inspector.get_columns("test_cases")}
            with engine.begin() as conn:
                if "project_id" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN project_id INTEGER"))
                if "preconditions" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN preconditions TEXT DEFAULT ''"))
                if "steps_json" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN steps_json TEXT DEFAULT '[]'"))
                if "priority" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN priority VARCHAR(16) DEFAULT 'P2'"))
                if "revision_no" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN revision_no INTEGER DEFAULT 1"))
        if inspector.has_table("test_runs"):
            cols = {c["name"] for c in inspector.get_columns("test_runs")}
            if "step_log" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN step_log TEXT"))
            if "robot_instance_id" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN robot_instance_id INTEGER"))
        if inspector.has_table("users"):
            ucols = {c["name"] for c in inspector.get_columns("users")}
            with engine.begin() as conn:
                if "company_id" not in ucols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN company_id INTEGER"))
        if inspector.has_table("robot_rental_orders"):
            rcols = {c["name"] for c in inspector.get_columns("robot_rental_orders")}
            with engine.begin() as conn:
                if "company_id" not in rcols:
                    conn.execute(text("ALTER TABLE robot_rental_orders ADD COLUMN company_id INTEGER"))
        if inspector.has_table("robot_instances"):
            ricols = {c["name"] for c in inspector.get_columns("robot_instances")}
            with engine.begin() as conn:
                if "company_id" not in ricols:
                    conn.execute(text("ALTER TABLE robot_instances ADD COLUMN company_id INTEGER"))
    except Exception:
        pass


def ensure_company_bootstrap() -> None:
    """从历史 users.company 文本补建 companies 表关联，并回填租用单/实例的 company_id。"""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("users"):
            return
        from app.models import Company, RobotInstance, RobotRentalOrder, User

        db = SessionLocal()
        try:
            for (name,) in (
                db.query(User.company)
                .filter(User.company.isnot(None))
                .distinct()
                .all()
            ):
                if not name or not str(name).strip():
                    continue
                nm = str(name).strip()[:128]
                if db.query(Company).filter(Company.name == nm).first() is None:
                    db.add(Company(name=nm, share_projects_cases_internally=False))
            db.commit()

            for u in db.query(User).filter(User.company_id.is_(None)).all():
                if u.company and str(u.company).strip():
                    nm = str(u.company).strip()[:128]
                    c = db.query(Company).filter(Company.name == nm).first()
                    if c is not None:
                        u.company_id = c.id
            db.commit()

            for row in db.query(RobotRentalOrder).filter(RobotRentalOrder.company_id.is_(None)).all():
                u = db.query(User).filter(User.id == row.user_id).first()
                if u and u.company_id is not None:
                    row.company_id = u.company_id
            db.commit()

            for inst in db.query(RobotInstance).filter(RobotInstance.company_id.is_(None)).all():
                u = db.query(User).filter(User.id == inst.user_id).first()
                if u and u.company_id is not None:
                    inst.company_id = u.company_id
                elif inst.rental_order_id:
                    ro = db.query(RobotRentalOrder).filter(RobotRentalOrder.id == inst.rental_order_id).first()
                    if ro and ro.company_id is not None:
                        inst.company_id = ro.company_id
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def bootstrap_rbac() -> None:
    """将指定邮箱/手机号用户提升为平台管理员（环境变量，便于首次运维）。"""
    try:
        import os

        from app.models import User
        from app.rbac import ROLE_PLATFORM_ADMIN

        email = os.getenv("TCM_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        phone = "".join(c for c in os.getenv("TCM_BOOTSTRAP_ADMIN_PHONE", "") if c.isdigit())
        if not email and not phone:
            return
        db = SessionLocal()
        try:
            if email:
                u = db.query(User).filter(User.email == email).first()
                if u is not None:
                    u.role = ROLE_PLATFORM_ADMIN
                    db.commit()
            if phone:
                u = db.query(User).filter(User.phone == phone).first()
                if u is not None:
                    u.role = ROLE_PLATFORM_ADMIN
                    db.commit()
        finally:
            db.close()
    except Exception:
        pass


def ensure_projects_bootstrap() -> None:
    """为每位用户至少创建一个默认项目空间，并将无主用例归属到该项目（多租户迁移）。"""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("projects"):
            return
        from app.models import Project, TestCase, User

        db = SessionLocal()
        try:
            for u in db.query(User).all():
                first_p = db.query(Project).filter(Project.owner_id == u.id).order_by(Project.id).first()
                if first_p is None:
                    first_p = Project(
                        owner_id=u.id,
                        name="默认项目空间",
                        tested_app_name="未指定",
                        test_objective="",
                    )
                    db.add(first_p)
                    db.flush()
                db.query(TestCase).filter(TestCase.owner_id == u.id, TestCase.project_id.is_(None)).update(
                    {TestCase.project_id: first_p.id},
                    synchronize_session=False,
                )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def ensure_personal_spaces() -> None:
    """为尚无个人空间的用户补建一条记录（兼容升级前的账号）。"""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("personal_spaces"):
            return
        from app.models import PersonalSpace, User

        db = SessionLocal()
        try:
            for uid, in db.query(User.id).all():
                exists = db.query(PersonalSpace).filter(PersonalSpace.user_id == uid).first()
                if exists is None:
                    db.add(PersonalSpace(user_id=uid, name="个人空间"))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

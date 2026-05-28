from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

_log = logging.getLogger(__name__)


def _resolve_database_url() -> str:
    url = (os.getenv("DATABASE_URL") or os.getenv("TCM_DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError(
            "请设置 DATABASE_URL 或 TCM_DATABASE_URL，例如 "
            "mysql+pymysql://tcm:tcm@127.0.0.1:3306/tcm?charset=utf8mb4"
        )
    return url


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        _log.warning("环境变量 %s=%r 无效，使用默认值 %s", name, raw, default)
        return default


def _build_engine() -> Engine:
    url = _resolve_database_url()
    kwargs: dict = {
        "echo": os.getenv("LOG_SQL", "").strip().lower() in ("1", "true", "yes"),
        "pool_pre_ping": True,
        "pool_recycle": 3600,
        "pool_size": _int_env("TCM_DB_POOL_SIZE", 10),
        "max_overflow": _int_env("TCM_DB_MAX_OVERFLOW", 20),
    }
    eng = create_engine(url, **kwargs)

    @event.listens_for(eng, "connect")
    def _set_mysql_session(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("SET time_zone = '+00:00'")
        finally:
            cursor.close()

    safe_url = url.split("@")[-1] if "@" in url else url
    _log.info("数据库连接：%s", safe_url)
    return eng


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def check_database_connection() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def ensure_schema(eng: Engine | None = None) -> None:
    """Adds columns introduced after first deploy (legacy DBs may lack newer columns)."""
    db_engine = eng or engine
    try:
        inspector = inspect(db_engine)
        if inspector.has_table("users"):
            cols = {c["name"] for c in inspector.get_columns("users")}
            with db_engine.begin() as conn:
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
            cols_after = {c["name"] for c in inspect(db_engine).get_columns("users")}
            if "role" in cols_after:
                with db_engine.begin() as conn:
                    conn.execute(text("UPDATE users SET role = 'enterprise' WHERE role IS NULL OR TRIM(role) = ''"))
        if inspector.has_table("test_cases"):
            tc_cols = {c["name"] for c in inspector.get_columns("test_cases")}
            with db_engine.begin() as conn:
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
                if "case_format" not in tc_cols:
                    conn.execute(
                        text("ALTER TABLE test_cases ADD COLUMN case_format VARCHAR(16) DEFAULT 'structured'")
                    )
                if "case_yaml" not in tc_cols:
                    conn.execute(text("ALTER TABLE test_cases ADD COLUMN case_yaml TEXT DEFAULT ''"))
        if inspector.has_table("test_case_revisions"):
            rev_cols = {c["name"] for c in inspector.get_columns("test_case_revisions")}
            with db_engine.begin() as conn:
                if "case_format" not in rev_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE test_case_revisions ADD COLUMN case_format VARCHAR(16) DEFAULT 'structured'"
                        )
                    )
                if "case_yaml" not in rev_cols:
                    conn.execute(text("ALTER TABLE test_case_revisions ADD COLUMN case_yaml TEXT DEFAULT ''"))
        if inspector.has_table("test_runs"):
            cols = {c["name"] for c in inspector.get_columns("test_runs")}
            if "step_log" not in cols:
                with db_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN step_log TEXT"))
            if "robot_instance_id" not in cols:
                with db_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN robot_instance_id INTEGER"))
            if "report_path" not in cols:
                with db_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN report_path TEXT"))
            cols = {c["name"] for c in inspector.get_columns("test_runs")}
            if "device_platform" not in cols:
                with db_engine.begin() as conn:
                    conn.execute(
                        text("ALTER TABLE test_runs ADD COLUMN device_platform VARCHAR(32)")
                    )
            cols = {c["name"] for c in inspector.get_columns("test_runs")}
            if "device_id" not in cols:
                with db_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE test_runs ADD COLUMN device_id VARCHAR(256)"))
        if inspector.has_table("users"):
            ucols = {c["name"] for c in inspector.get_columns("users")}
            with db_engine.begin() as conn:
                if "company_id" not in ucols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN company_id INTEGER"))
        if inspector.has_table("robot_rental_orders"):
            rcols = {c["name"] for c in inspector.get_columns("robot_rental_orders")}
            with db_engine.begin() as conn:
                if "company_id" not in rcols:
                    conn.execute(text("ALTER TABLE robot_rental_orders ADD COLUMN company_id INTEGER"))
        if inspector.has_table("robot_instances"):
            ricols = {c["name"] for c in inspector.get_columns("robot_instances")}
            with db_engine.begin() as conn:
                if "company_id" not in ricols:
                    conn.execute(text("ALTER TABLE robot_instances ADD COLUMN company_id INTEGER"))
                if "test_agent_backend" not in ricols:
                    conn.execute(
                        text(
                            "ALTER TABLE robot_instances ADD COLUMN test_agent_backend VARCHAR(32) DEFAULT 'autoglm'"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE robot_instances SET test_agent_backend = 'autoglm' "
                            "WHERE test_agent_backend IS NULL OR TRIM(test_agent_backend) = ''"
                        )
                    )
                if "device_platform" not in ricols:
                    conn.execute(
                        text(
                            "ALTER TABLE robot_instances ADD COLUMN device_platform VARCHAR(32) DEFAULT 'android'"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE robot_instances SET device_platform = 'harmonyos' "
                            "WHERE (device_platform IS NULL OR TRIM(device_platform) = '') "
                            "AND LOWER(COALESCE(test_agent_backend, '')) = 'midscene'"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE robot_instances SET device_platform = 'android' "
                            "WHERE device_platform IS NULL OR TRIM(device_platform) = ''"
                        )
                    )
        if inspector.has_table("project_feature_analysis_runs"):
            fa_cols = {c["name"] for c in inspector.get_columns("project_feature_analysis_runs")}
            with db_engine.begin() as conn:
                if "traverse_mode" not in fa_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE project_feature_analysis_runs "
                            "ADD COLUMN traverse_mode VARCHAR(16) DEFAULT 'hybrid'"
                        )
                    )
                if "bfs_max_depth" not in fa_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE project_feature_analysis_runs "
                            "ADD COLUMN bfs_max_depth INTEGER DEFAULT 1"
                        )
                    )
                if "fair_share_per_root" not in fa_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE project_feature_analysis_runs "
                            "ADD COLUMN fair_share_per_root INTEGER DEFAULT 0"
                        )
                    )
                if "scroll_reveal_menus" not in fa_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE project_feature_analysis_runs "
                            "ADD COLUMN scroll_reveal_menus TINYINT(1) DEFAULT 1"
                        )
                    )
                if "scroll_max_passes" not in fa_cols:
                    conn.execute(
                        text(
                            "ALTER TABLE project_feature_analysis_runs "
                            "ADD COLUMN scroll_max_passes INTEGER DEFAULT 3"
                        )
                    )
        if inspector.has_table("project_knowledge_settings"):
            pks_cols = {c["name"] for c in inspector.get_columns("project_knowledge_settings")}
            if "chunk_policy_json" not in pks_cols:
                with db_engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE project_knowledge_settings "
                            "ADD COLUMN chunk_policy_json LONGTEXT"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE project_knowledge_settings "
                            "SET chunk_policy_json = '{}' "
                            "WHERE chunk_policy_json IS NULL"
                        )
                    )
        if inspector.has_table("knowledge_documents"):
            kd_cols = {c["name"] for c in inspector.get_columns("knowledge_documents")}
            if "chunk_policy_json" not in kd_cols:
                with db_engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE knowledge_documents "
                            "ADD COLUMN chunk_policy_json LONGTEXT"
                        )
                    )
                    conn.execute(
                        text(
                            "UPDATE knowledge_documents "
                            "SET chunk_policy_json = '{}' "
                            "WHERE chunk_policy_json IS NULL"
                        )
                    )
    except Exception:
        _log.exception("ensure_schema 执行失败")


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
        _log.exception("ensure_company_bootstrap 执行失败")


def ensure_builtin_platform_admin() -> None:
    """若库中尚无任何 platform_admin，则按环境变量创建或提拔内置管理员（便于首次安装。

    生产环境请尽快修改默认密码，或设置 TCM_DISABLE_BUILTIN_ADMIN=1 并在通过注册 +
    TCM_BOOTSTRAP_ADMIN_* 获得管理员后保持禁用。
    """
    try:
        import uuid

        if os.getenv("TCM_DISABLE_BUILTIN_ADMIN", "").strip().lower() in ("1", "true", "yes"):
            return

        inspector = inspect(engine)
        if not inspector.has_table("users"):
            return

        from app.auth_utils import hash_password
        from app.models import Company, PersonalSpace, Project, User
        from app.rbac import ROLE_PLATFORM_ADMIN

        db = SessionLocal()
        try:
            if db.query(User).filter(User.role == ROLE_PLATFORM_ADMIN).first() is not None:
                return

            email = (os.getenv("TCM_BUILTIN_ADMIN_EMAIL") or "admin@localhost").strip().lower()
            password = (os.getenv("TCM_BUILTIN_ADMIN_PASSWORD") or "ChangeMe123!").strip()
            if len(password) < 6:
                _log.warning("TCM_BUILTIN_ADMIN_PASSWORD 短于 6 位，跳过内置管理员创建")
                return

            existing = db.query(User).filter(User.email == email).first()
            if existing is not None:
                existing.role = ROLE_PLATFORM_ADMIN
                db.commit()
                return

            comp_name = (os.getenv("TCM_BUILTIN_ADMIN_COMPANY") or "内置平台").strip()[:128] or "内置平台"
            company = db.query(Company).filter(Company.name == comp_name).first()
            if company is None:
                company = Company(name=comp_name, share_projects_cases_internally=False)
                db.add(company)
                db.flush()

            base_uname = (os.getenv("TCM_BUILTIN_ADMIN_USERNAME") or "platform_admin").strip()[:64] or "platform_admin"
            username = base_uname
            if db.query(User).filter(User.username == username).first() is not None:
                username = f"{base_uname[:40]}_{uuid.uuid4().hex[:8]}"[:64]

            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(password),
                role=ROLE_PLATFORM_ADMIN,
                company_id=company.id,
                company=company.name,
            )
            db.add(user)
            db.flush()
            db.add(PersonalSpace(user_id=user.id, name="个人空间"))
            db.add(
                Project(
                    owner_id=user.id,
                    name="默认项目空间",
                    tested_app_name="未指定",
                    test_objective="",
                )
            )
            db.commit()
            _log.info(
                "已创建内置平台管理员：邮箱=%s 用户名=%s（登录账号可填邮箱；请尽快修改默认密码）",
                email,
                username,
            )
        finally:
            db.close()
    except Exception:
        _log.exception("ensure_builtin_platform_admin 执行失败")


def bootstrap_rbac() -> None:
    """将指定邮箱/手机号用户提升为平台管理员（环境变量，便于首次运维）。"""
    try:
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
        _log.exception("bootstrap_rbac 执行失败")


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
        _log.exception("ensure_projects_bootstrap 执行失败")


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
        _log.exception("ensure_personal_spaces 执行失败")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

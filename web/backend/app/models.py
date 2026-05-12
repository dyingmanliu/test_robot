from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Company(Base):
    """企业租户：注册用户归属同一公司后可共享租用机器人；管理员可开关「项目与用例公司内部共享」。"""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    share_projects_cases_internally: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship(back_populates="company_rel")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True, index=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="enterprise", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company_rel: Mapped[Optional["Company"]] = relationship(back_populates="users")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="owner")
    personal_space: Mapped[Optional["PersonalSpace"]] = relationship(back_populates="owner", uselist=False)
    projects: Mapped[list["Project"]] = relationship(back_populates="owner")


class PersonalSpace(Base):
    __tablename__ = "personal_spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="个人空间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="personal_space")


class Project(Base):
    """项目空间：绑定被测应用与测试目标，聚合用例、执行与报告（多租户隔离）。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    tested_app_name: Mapped[str] = mapped_column(String(256))
    test_objective: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="projects")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="project")
    defects: Mapped[list["Defect"]] = relationship(back_populates="project")
    reports: Mapped[list["ProjectReport"]] = relationship(back_populates="project")


class ProjectReport(Base):
    """项目测试报告摘要（数据服务写入最新一条供看板展示）。"""

    __tablename__ = "project_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="reports")


class Defect(Base):
    """缺陷记录（用于未处理缺陷趋势；可与缺陷跟踪模块同步）。"""

    __tablename__ = "defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="defects")


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    task_text: Mapped[str] = mapped_column(Text)
    preconditions: Mapped[str] = mapped_column(Text, default="")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[str] = mapped_column(String(16), default="P2")
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship(back_populates="test_cases")
    project: Mapped[Optional["Project"]] = relationship(back_populates="test_cases")
    runs: Mapped[list["TestRun"]] = relationship(back_populates="test_case")


class TestCaseRevision(Base):
    """用例版本快照（每次保存递增 revision_no）。"""

    __tablename__ = "test_case_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(256))
    task_text: Mapped[str] = mapped_column(Text)
    preconditions: Mapped[str] = mapped_column(Text, default="")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    priority: Mapped[str] = mapped_column(String(16), default="P2")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CaseKbDocument(Base):
    """知识库检索层：扁平文本，可与向量库/Agent 工具链对接。"""

    __tablename__ = "case_kb_documents"

    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), primary_key=True)
    search_text: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProjectAppArtifact(Base):
    """项目内上传的安装包（APK/AAB 等），供功能测试下发引用。"""

    __tablename__ = "project_app_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    storage_key: Mapped[str] = mapped_column(String(1024))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestCaseSet(Base):
    """测试用例集：归属项目空间，关联多条用例。"""

    __tablename__ = "test_case_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    ai_assisted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TestCaseSetItem(Base):
    __tablename__ = "test_case_set_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("test_case_sets.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class FunctionalDispatchTask(Base):
    """功能测试下发任务：调度层写入 Kafka，由 Agent 管理拉取并分配给数字机器人。"""

    __tablename__ = "functional_dispatch_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    app_artifact_id: Mapped[int] = mapped_column(ForeignKey("project_app_artifacts.id", ondelete="RESTRICT"), index=True)
    case_set_id: Mapped[int] = mapped_column(ForeignKey("test_case_sets.id", ondelete="RESTRICT"), index=True)
    device_pool_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    kafka_topic: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    kafka_offset: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    broker_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BillingPreorder(Base):
    """计费模块预订单：用户点击「立即租用」后生成，支付网关对接前保持 pending_payment。"""

    __tablename__ = "billing_preorders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    robot_name: Mapped[str] = mapped_column(String(128))
    billing_mode: Mapped[str] = mapped_column(String(16))
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(32), default="pending_payment", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RobotRentalOrder(Base):
    """租用申请单：含数量与账单金额；待管理员审批后实例化机器人（暂不经过支付）。"""

    __tablename__ = "robot_rental_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    robot_id: Mapped[str] = mapped_column(String(64), index=True)
    robot_name: Mapped[str] = mapped_column(String(128))
    billing_mode: Mapped[str] = mapped_column(String(16))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(8), default="CNY")
    status: Mapped[str] = mapped_column(String(32), default="pending_approval", index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewer_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)

    instances: Mapped[list["RobotInstance"]] = relationship(back_populates="rental_order")


class RobotInstance(Base):
    """已审批实例化的数字机器人：用户可改展示名与简介；执行用例与监控均关联此表。"""

    __tablename__ = "robot_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rental_order_id: Mapped[int] = mapped_column(ForeignKey("robot_rental_orders.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_robot_id: Mapped[str] = mapped_column(String(64), index=True)
    instance_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    display_bio: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)

    rental_order: Mapped["RobotRentalOrder"] = relationship(back_populates="instances")
    runs: Mapped[list["TestRun"]] = relationship(back_populates="robot_instance")

    @property
    def leasing_user_id(self) -> int:
        """与 API 中 leasing_user_id 一致（提交租用申请的用户）。"""
        return int(self.user_id)


class TestRun(Base):
    __tablename__ = "test_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    robot_instance_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("robot_instances.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="pending")
    step_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    test_case: Mapped["TestCase"] = relationship(back_populates="runs")
    robot_instance: Mapped[Optional["RobotInstance"]] = relationship(back_populates="runs")


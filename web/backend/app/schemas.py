from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.rbac import ROLES


class PersonalSpaceOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterBody(BaseModel):
    """手机号与邮箱二选一注册；密码由服务端 bcrypt 哈希存储。"""

    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_as_none(cls, v: object) -> object:
        if v is None or v == "":
            return None
        return v

    @model_validator(mode="after")
    def phone_xor_email(self) -> RegisterBody:
        has_phone = bool(self.phone and str(self.phone).strip())
        has_email = self.email is not None and str(self.email).strip() != ""
        if has_phone == has_email:
            raise ValueError("请填写手机号或邮箱其中之一")
        return self

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone_input(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        digits = "".join(c for c in str(v) if c.isdigit())
        return digits or None

    @field_validator("phone")
    @classmethod
    def validate_cn_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if len(v) != 11 or not v.startswith("1"):
            raise ValueError("请输入有效的中国大陆手机号")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    company: Optional[str] = None
    personal_space: Optional[PersonalSpaceOut] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None
    nickname: Optional[str] = None
    company: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminRolePatch(BaseModel):
    role: str = Field(..., description="platform_admin | tse | enterprise")

    @field_validator("role")
    @classmethod
    def role_known(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("无效的角色")
        return v


class ProfileUpdate(BaseModel):
    """个人资料 PATCH：仅提交需要修改的字段。"""

    nickname: Optional[str] = Field(None, max_length=64)
    avatar_url: Optional[str] = Field(None, max_length=512)
    company: Optional[str] = Field(None, max_length=128)

    @field_validator("nickname", "company", mode="before")
    @classmethod
    def strip_optional(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v

    @field_validator("avatar_url", mode="before")
    @classmethod
    def strip_avatar(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return v


class ChangePasswordBody(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)
    new_password_confirm: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def passwords_match(self) -> ChangePasswordBody:
        if self.new_password != self.new_password_confirm:
            raise ValueError("两次输入的新密码不一致")
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与当前密码相同")
        return self


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginBody(BaseModel):
    """支持手机号、邮箱或历史用户名登录。"""

    account: str = Field(..., min_length=1, max_length=255)
    password: str


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    tested_app_name: str = Field(..., min_length=1, max_length=256, description="被测应用名称或标识")
    test_objective: str = Field(default="", max_length=8000, description="测试目标与范围")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    tested_app_name: Optional[str] = Field(None, min_length=1, max_length=256)
    test_objective: Optional[str] = Field(None, max_length=8000)


class ProjectOut(BaseModel):
    id: int
    owner_id: int
    name: str
    tested_app_name: str
    test_objective: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectWithStatsOut(ProjectOut):
    """项目列表附聚合字段。"""

    test_case_count: int = 0


class CaseStepJson(BaseModel):
    """单步说明与预期。"""

    order: int = Field(default=1, ge=1)
    description: str = ""
    expected: str = ""


class TestCaseCreate(BaseModel):
    project_id: int = Field(..., description="所属项目空间 ID")
    title: str = Field(..., min_length=1, max_length=256)
    task_text: str = Field(default="", max_length=32000, description="自动化执行补充说明（可与步骤合并）")
    preconditions: str = Field(default="", max_length=16000)
    steps: list[CaseStepJson] = Field(default_factory=list)
    priority: str = Field(default="P2", max_length=16)

    @model_validator(mode="after")
    def need_instruction_or_steps(self) -> TestCaseCreate:
        if not self.task_text.strip() and not self.steps:
            raise ValueError("请填写「执行说明」或至少一条「测试步骤」")
        return self


class TestCaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    task_text: Optional[str] = Field(None, max_length=32000)
    preconditions: Optional[str] = Field(None, max_length=16000)
    steps: Optional[list[CaseStepJson]] = None
    priority: Optional[str] = Field(None, max_length=16)


class TestCaseOut(BaseModel):
    id: int
    owner_id: int
    project_id: Optional[int] = None
    title: str
    task_text: str
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    priority: str = "P2"
    revision_no: int = 1
    created_at: datetime
    updated_at: datetime


class TestCaseRevisionOut(BaseModel):
    id: int
    case_id: int
    revision_no: int
    title: str
    task_text: str
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    priority: str = "P2"
    created_at: datetime


class CaseImportResultOut(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class TestRunOut(BaseModel):
    id: int
    case_id: int
    owner_id: int
    status: str
    step_log: Optional[str] = None
    output_message: Optional[str]
    error_trace: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TestRunListItemOut(BaseModel):
    """执行历史列表（日志已持久化在 step_log）。"""

    id: int
    case_id: int
    case_title: str
    project_id: Optional[int] = None
    status: str
    recognition_steps: int = 0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class BillingModePriceOut(BaseModel):
    label: str
    unit_label: str
    price_cents: int
    description: str


class RobotCatalogItemOut(BaseModel):
    id: str
    name: str
    category: str
    profile: str
    capabilities: list[str]
    billing_modes: dict[str, BillingModePriceOut]


class RobotCatalogResponse(BaseModel):
    robots: list[RobotCatalogItemOut]


class PreorderCreate(BaseModel):
    robot_id: str = Field(..., min_length=1, max_length=64)
    billing_mode: str = Field(..., description="duration | count")

    @field_validator("billing_mode")
    @classmethod
    def billing_mode_known(cls, v: str) -> str:
        if v not in ("duration", "count"):
            raise ValueError("billing_mode 须为 duration 或 count")
        return v


class PreorderCreatedOut(BaseModel):
    preorder_id: int
    status: str
    payment_path: str
    amount_cents: int
    currency: str


class PreorderDetailOut(BaseModel):
    id: int
    robot_id: str
    robot_name: str
    billing_mode: str
    amount_cents: int
    currency: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectAppArtifactOut(BaseModel):
    id: int
    project_id: int
    filename: str
    size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseSetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    case_ids: list[int] = Field(..., min_length=1)


class CaseSetOut(BaseModel):
    id: int
    project_id: int
    name: str
    description: str
    ai_assisted: bool
    case_ids: list[int]
    created_at: datetime


class CaseSetAiDraftOut(BaseModel):
    suggested_name: str
    description: str
    message: str


class FunctionalDispatchCreate(BaseModel):
    app_artifact_id: int
    case_set_id: int
    device_pool_id: str = Field(..., min_length=1, max_length=64)


class FunctionalDispatchCreatedOut(BaseModel):
    id: int
    project_id: int
    status: str
    kafka_delivered: bool
    kafka_topic: Optional[str] = None
    kafka_offset: Optional[str] = None
    broker_error: Optional[str] = None
    message: str
    created_at: datetime


class FunctionalDispatchListOut(BaseModel):
    id: int
    status: str
    device_pool_id: str
    kafka_topic: Optional[str] = None
    kafka_offset: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

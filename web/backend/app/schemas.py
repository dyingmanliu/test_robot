from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.rbac import ROLES


class PersonalSpaceOut(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanyPublicOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CompanyAdminOut(BaseModel):
    id: int
    name: str
    share_projects_cases_internally: bool
    user_count: int = 0


class CompanySharePatch(BaseModel):
    share_projects_cases_internally: bool


class RegisterBody(BaseModel):
    """手机号与邮箱二选一注册；须选择已有公司或创建新公司。"""

    password: str = Field(..., min_length=6, max_length=128)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    company_id: Optional[int] = Field(None, description="选择已有公司时填写其 ID")
    new_company_name: Optional[str] = Field(None, max_length=128, description="新公司全称，与 company_id 二选一")

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

    @model_validator(mode="after")
    def company_pick_one(self) -> RegisterBody:
        has_id = self.company_id is not None and int(self.company_id) >= 1
        nm = (self.new_company_name or "").strip()
        has_new = bool(nm)
        if has_id == has_new:
            raise ValueError("请选择已有公司或填写新公司全称（二选一）")
        if has_new and len(nm) > 128:
            raise ValueError("公司名称不能超过 128 字")
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
    company_id: Optional[int] = None
    company_internal_share: bool = False
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
    company_id: Optional[int] = None
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


class TestCaseGenerateIn(BaseModel):
    """一句话生成用例草稿（不写库）。"""

    project_id: int = Field(..., ge=1, description="所属项目空间 ID")
    prompt: str = Field(..., min_length=1, max_length=2000, description="用户一句话描述")
    case_format: Literal["structured", "yaml"] = Field(
        default="structured",
        description="生成结果格式：structured 表单；yaml 在 LLM 生成 structured 后自动转换",
    )


class CaseGenerateMetaOut(BaseModel):
    model: str = ""
    similar_case_ids: list[int] = Field(default_factory=list)


class TestCaseGenerateOut(BaseModel):
    """生成草稿，字段与 TestCaseCreate 对齐（无 id）。"""

    title: str
    task_text: str = ""
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    priority: str = "P2"
    case_format: Literal["structured", "yaml"] = "structured"
    case_yaml: str = ""
    generation_meta: CaseGenerateMetaOut = Field(default_factory=CaseGenerateMetaOut)


class CaseFormatConvertIn(BaseModel):
    """编辑弹窗内 structured ↔ yaml 互转。"""

    target_format: Literal["structured", "yaml"]
    title: str = ""
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    task_text: str = ""
    case_yaml: str = ""


class CaseFormatConvertOut(BaseModel):
    title: str
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    task_text: str = ""
    case_format: Literal["structured", "yaml"]
    case_yaml: str = ""


class TestCaseCreate(BaseModel):
    project_id: int = Field(..., description="所属项目空间 ID")
    title: str = Field(..., min_length=1, max_length=256)
    task_text: str = Field(default="", max_length=32000, description="自动化执行补充说明（可与步骤合并）")
    preconditions: str = Field(default="", max_length=16000)
    steps: list[CaseStepJson] = Field(default_factory=list)
    priority: str = Field(default="P2", max_length=16)
    case_format: Literal["structured", "yaml"] = Field(
        default="structured",
        description="structured=表单步骤；yaml=Midscene YAML（绑定 Midscene 机器人执行）",
    )
    case_yaml: str = Field(default="", max_length=200000, description="Midscene YAML 脚本（case_format=yaml 时必填）")

    @model_validator(mode="after")
    def validate_case_body(self) -> TestCaseCreate:
        if self.case_format == "yaml":
            from app.services.case_yaml import validate_case_yaml

            self.case_yaml = validate_case_yaml(self.case_yaml)
            return self
        if not self.task_text.strip() and not self.steps:
            raise ValueError("请填写「执行说明」或至少一条「测试步骤」")
        return self


class TestCaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=256)
    task_text: Optional[str] = Field(None, max_length=32000)
    preconditions: Optional[str] = Field(None, max_length=16000)
    steps: Optional[list[CaseStepJson]] = None
    priority: Optional[str] = Field(None, max_length=16)
    case_format: Optional[Literal["structured", "yaml"]] = None
    case_yaml: Optional[str] = Field(None, max_length=200000)


class TestCaseOut(BaseModel):
    id: int
    owner_id: int
    project_id: Optional[int] = None
    title: str
    task_text: str
    preconditions: str = ""
    steps: list[CaseStepJson] = Field(default_factory=list)
    case_format: str = "structured"
    case_yaml: str = ""
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
    case_format: str = "structured"
    case_yaml: str = ""
    priority: str = "P2"
    created_at: datetime


class CaseImportResultOut(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class TestRunOut(BaseModel):
    id: int
    case_id: int
    project_id: Optional[int] = Field(
        default=None,
        description="所属项目空间（来自 test_cases.project_id）",
    )
    owner_id: int
    robot_instance_id: Optional[int] = None
    device_platform: Optional[str] = None
    device_id: Optional[str] = None
    status: str
    step_log: Optional[str] = None
    output_message: Optional[str]
    error_trace: Optional[str]
    has_report: bool = False
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    model_config = {"from_attributes": True}


class TestRunListItemOut(BaseModel):
    """执行历史列表（日志已持久化在 step_log）。"""

    id: int
    case_id: int
    case_title: str
    project_id: Optional[int] = None
    robot_instance_id: Optional[int] = None
    robot_instance_code: Optional[str] = None
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


# --- 租用申请与机器人实例 ---


class RentalOrderCreate(BaseModel):
    robot_id: str = Field(..., min_length=1, max_length=64)
    billing_mode: str = Field(..., description="duration | count")
    quantity: int = Field(1, ge=1, le=99)

    @field_validator("billing_mode")
    @classmethod
    def billing_mode_known(cls, v: str) -> str:
        if v not in ("duration", "count"):
            raise ValueError("billing_mode 须为 duration 或 count")
        return v


class RentalOrderCreatedOut(BaseModel):
    id: int
    status: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    currency: str
    robot_id: str
    robot_name: str
    billing_mode: str
    message: str = "已生成账单，待管理员审批；审批通过后将自动实例化并分配编号。"


class RentalApproveBody(BaseModel):
    """管理员审批通过并实例化机器人时，选择执行引擎与目标设备平台。"""

    test_agent_backend: Literal["autoglm", "midscene"] = Field(
        default="autoglm",
        description="autoglm：AutoGLM-Phone；midscene：Midscene.js 视觉自动化",
    )
    device_platform: Literal["android", "harmonyos"] = Field(
        default="android",
        description="实例默认执行设备；用例执行前可在页面临时切换",
    )


class RentalOrderOut(BaseModel):
    id: int
    user_id: int
    company_id: Optional[int] = None
    robot_id: str
    robot_name: str
    billing_mode: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    currency: str
    status: str
    reviewed_at: Optional[datetime] = None
    reviewer_user_id: Optional[int] = None
    reject_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RobotInstanceOut(BaseModel):
    id: int
    rental_order_id: int
    company_id: Optional[int] = None
    leasing_user_id: int = Field(..., description="提交租用申请的用户 ID")
    catalog_robot_id: str
    instance_code: str
    display_name: str
    display_bio: str
    status: str
    runtime_status: Literal["executing", "idle", "abnormal"] = Field(
        default="idle",
        description="运行态：executing=执行中，idle=空闲，abnormal=异常",
    )
    active_run_id: Optional[int] = Field(
        default=None,
        description="当前 pending/running 的 test_run.id；无则 null",
    )
    test_agent_backend: str = Field(
        default="autoglm",
        description="执行用例时使用的引擎：autoglm 或 midscene",
    )
    device_platform: str = Field(
        default="android",
        description="默认执行设备平台：android 或 harmonyos；用例执行前可临时切换",
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class RobotInstanceStatusPatch(BaseModel):
    status: Literal["active", "suspended"] = Field(
        ...,
        description="active=启动；suspended=停用",
    )


class RobotInstancePatch(BaseModel):
    display_name: Optional[str] = Field(None, max_length=128)
    display_bio: Optional[str] = Field(None, max_length=2000)
    test_agent_backend: Optional[Literal["autoglm", "midscene"]] = None
    device_platform: Optional[Literal["android", "harmonyos"]] = None

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_name(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip()[:128]
        return v

    @field_validator("display_bio", mode="before")
    @classmethod
    def strip_bio(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, str):
            return v.strip()[:2000]
        return v


class ConnectedDeviceOut(BaseModel):
    device_id: str
    label: str
    state: str = "device"


class ConnectedDevicesOut(BaseModel):
    platform: Literal["android", "harmonyos"]
    devices: list[ConnectedDeviceOut] = Field(default_factory=list)


class DeviceScreenOut(BaseModel):
    """设备当前画面（Base64 PNG），供 Web 投屏轮询。"""

    image_base64: str
    width: int
    height: int
    backend: str
    mime_type: str = "image/png"


class RunCaseBody(BaseModel):
    """执行用例时绑定已租用的机器人实例。"""

    robot_instance_id: int = Field(..., ge=1)
    device_platform: Optional[Literal["android", "harmonyos"]] = Field(
        default=None,
        description="本次执行目标设备；不传则使用实例默认平台",
    )
    device_id: Optional[str] = Field(
        default=None,
        max_length=256,
        description="ADB 序列号或 HDC target ID；不传则使用环境变量或第一台在线设备",
    )


class RentalRejectBody(BaseModel):
    reason: str = Field(default="", max_length=500)

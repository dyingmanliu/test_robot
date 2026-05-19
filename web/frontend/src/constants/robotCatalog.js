/** 商城目录 robot id → 机器人类型（中文分类） */
export const ROBOT_TYPE_LABELS = {
  test_analysis: "测试分析",
  functional_execution: "功能执行",
  specialized_execution: "专项执行",
  quality_assessment: "质量评估",
};

export function robotTypeLabel(catalogRobotId) {
  const id = String(catalogRobotId || "").trim();
  return ROBOT_TYPE_LABELS[id] || id || "—";
}

/** 实例运行态 API 值 → 中文 */
export const RUNTIME_STATUS_LABELS = {
  executing: "执行中",
  idle: "空闲",
  abnormal: "异常",
};

export function runtimeStatusLabel(code) {
  const k = String(code || "").trim().toLowerCase();
  return RUNTIME_STATUS_LABELS[k] || k || "—";
}

/** 实例生命周期 status → 中文（启动 / 停用） */
export const INSTANCE_STATUS_LABELS = {
  active: "启动",
  suspended: "停用",
  disabled: "停用",
  inactive: "停用",
};

export function instanceStatusLabel(status) {
  const s = String(status || "").trim().toLowerCase();
  return INSTANCE_STATUS_LABELS[s] || (s ? status : "—");
}

/** 用于样式 class：active → started，其余 → stopped */
export function instanceStatusClass(status) {
  const s = String(status || "").trim().toLowerCase();
  return s === "active" ? "started" : "stopped";
}

export function isInstanceStarted(status) {
  return String(status || "").trim().toLowerCase() === "active";
}

/** 是否可在测试用例页选中执行：已启动 + 运行空闲 + 可选 YAML 引擎约束 */
export function isRobotRunnableForCase(ins, needsMidscene = false) {
  if (!ins) return false;
  if (!isInstanceStarted(ins.status)) return false;
  if (String(ins.runtime_status || "").toLowerCase() !== "idle") return false;
  if (needsMidscene) {
    const b = String(ins.test_agent_backend || "autoglm").toLowerCase();
    if (b !== "midscene") return false;
  }
  return true;
}

export function robotUnselectableHint(ins, needsMidscene = false) {
  if (!ins) return "";
  if (!isInstanceStarted(ins.status)) return "（已停用）";
  const rt = String(ins.runtime_status || "").toLowerCase();
  if (rt === "executing") return "（执行中）";
  if (rt === "abnormal") return "（异常）";
  if (needsMidscene) {
    const b = String(ins.test_agent_backend || "autoglm").toLowerCase();
    if (b !== "midscene") return "（不可用于 YAML）";
  }
  return "";
}

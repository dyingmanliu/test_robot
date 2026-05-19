export function statusLabel(s) {
  const m = {
    pending: "排队",
    running: "执行中",
    success: "成功",
    failed: "失败",
    cancelled: "已终止",
  };
  return m[s] || s;
}

export function parseStepLog(raw) {
  if (!raw || typeof raw !== "string") return [];
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return { step: "?", thinking: line, action: null, message: "无法解析本行日志" };
      }
    });
}

export function formatJson(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export function stepCount(run) {
  return parseStepLog(run?.step_log).length;
}

/** 根据状态与 step_log 条数估算进度（执行中最高约 95%，结束后 100%） */
export function estimateRunProgress(run) {
  if (!run) return 0;
  const status = run.status;
  if (status === "success" || status === "failed" || status === "cancelled") {
    return 100;
  }
  if (status === "pending") return 8;
  const n = stepCount(run);
  if (n <= 0) return 12;
  const base = 12;
  const span = 83;
  const estimated = base + span * (1 - Math.exp(-n / 10));
  return Math.min(95, Math.round(estimated));
}

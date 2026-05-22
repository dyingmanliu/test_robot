/** 功能点分析 step_log（Midscene explore JSONL）解析与展示辅助 */

export function parseFeatureStepLog(raw) {
  if (!raw || typeof raw !== "string") return [];
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line, index) => {
      try {
        const obj = JSON.parse(line);
        return { ...formatExploreEvent(obj), _idx: index };
      } catch {
        return {
          kind: "raw",
          title: "日志",
          body: line,
          tone: "muted",
          _idx: index,
        };
      }
    })
    .filter((e) => e.kind !== "skip");
}

function formatExploreEvent(obj) {
  const kind = obj?.kind;
  if (kind === "explore_scope") {
    return {
      kind,
      title: obj.in_target ? "仍在被测应用" : "已离开被测应用",
      body: obj.message || "",
      meta: obj.foreground_bundle ? `前台 ${obj.foreground_bundle}` : "",
      tone: obj.in_target ? "page" : "error",
    };
  }
  if (kind === "explore_page") {
    const path = Array.isArray(obj.path) ? obj.path.join(" > ") : "主界面";
    const off = obj.in_target === false;
    const fg = obj.foreground_bundle ? `前台 ${obj.foreground_bundle}` : "";
    return {
      kind,
      title: off ? "界面遍历（已离站）" : `界面遍历 · 深度 ${obj.depth ?? 0}`,
      body: `${obj.screen_title || "（未识别标题）"} · ${path}`,
      meta: [obj.screen_id ? `界面 ${obj.screen_id}` : "", fg].filter(Boolean).join(" · "),
      tone: off ? "error" : "page",
    };
  }
  if (kind === "explore_feature") {
    const f = obj.feature || {};
    const path = Array.isArray(f.path) ? f.path.join(" > ") : f.name || "";
    return {
      kind,
      title: "发现功能项",
      body: path,
      meta: f.region ? `区域 ${f.region}` : "",
      tone: "feature",
    };
  }
  if (kind === "step") {
    const phase = obj.phase || "start";
    const task = obj.task || "";
    if (phase === "start") {
      return { kind, title: "操作", body: task, meta: `步骤 ${obj.step ?? ""}`, tone: "step" };
    }
    if (phase === "error") {
      return {
        kind,
        title: "操作失败",
        body: task,
        meta: obj.error || "",
        tone: "error",
      };
    }
    return {
      kind: "skip",
    };
  }
  if (kind === "done") {
    const n = obj.feature_count ?? obj.tree?.features?.length ?? 0;
    return {
      kind,
      title: "遍历结束",
      body: obj.message || `共 ${n} 个功能项`,
      tone: "done",
    };
  }
  if (kind === "model_usage") {
    return { kind: "skip" };
  }
  return {
    kind: kind || "event",
    title: kind || "事件",
    body: JSON.stringify(obj),
    tone: "muted",
  };
}

/** 从 step_log 提取「当前在哪」供顶栏展示（与投屏对照） */
export function summarizeFeatureAnalysisLocation(stepLogRaw) {
  if (!stepLogRaw || typeof stepLogRaw !== "string") return null;
  let lastPage = null;
  let lastScope = null;
  let lastStepStart = null;
  for (const line of stepLogRaw.trim().split("\n")) {
    if (!line) continue;
    try {
      const o = JSON.parse(line);
      if (o.kind === "explore_page") lastPage = o;
      if (o.kind === "explore_scope") lastScope = o;
      if (o.kind === "step" && o.phase === "start") lastStepStart = o;
    } catch {
      /* ignore */
    }
  }
  const path = Array.isArray(lastPage?.path) ? lastPage.path.join(" > ") : "";
  return {
    inTarget: lastScope ? lastScope.in_target !== false : true,
    screenTitle: lastPage?.screen_title || "",
    path: path || "主界面",
    foreground: lastScope?.foreground_bundle || lastPage?.foreground_bundle || "",
    targetBundle: lastScope?.target_bundle || lastPage?.target_bundle || "",
    lastAction: lastStepStart?.task || "",
  };
}

/** 根据功能项数与页面数估算进度 */
export function estimateFeatureProgress(run) {
  if (!run) return 0;
  const status = run.status;
  if (status === "success" || status === "failed" || status === "cancelled") return 100;
  if (status === "pending") return 6;
  const feats = Number(run.feature_count) || 0;
  const screens = Number(run.screens_visited) || 0;
  const lines = parseFeatureStepLog(run.step_log).length;
  const signal = feats * 2 + screens * 5 + lines;
  if (signal <= 0) return 12;
  const estimated = 12 + 83 * (1 - Math.exp(-signal / 25));
  return Math.min(95, Math.round(estimated));
}

/** 用例生成 step_log（JSONL）解析与展示 */

const PHASE_LABELS = {
  submit: "提交",
  kb_local: "知识库",
  kb_http: "KB请求",
  agent: "调度",
  start: "开始",
  load_context: "配置",
  retrieve: "检索",
  retrieve_query: "检索",
  retrieve_done: "检索",
  llm: "模型",
  llm_request: "模型请求",
  llm_response: "模型输出",
  llm_retry: "模型重试",
  llm_error: "模型失败",
  parse: "解析",
  done: "完成",
  error: "失败",
  cancelled: "取消",
};

export function parseCaseGenStepLog(raw) {
  if (!raw || typeof raw !== "string") return [];
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line, index) => {
      try {
        const obj = JSON.parse(line);
        return formatCaseGenEvent(obj, index);
      } catch {
        return {
          kind: "raw",
          title: "日志",
          body: line,
          tone: "muted",
          detail: "",
          _idx: index,
        };
      }
    });
}

function formatCaseGenEvent(obj, index) {
  const phase = obj?.phase || "";
  const label = PHASE_LABELS[phase] || phase || "进度";
  const metaParts = [];
  if (typeof obj.hits === "number") metaParts.push(`命中 ${obj.hits} 条`);
  if (obj.doc_types) metaParts.push(String(obj.doc_types));
  if (obj.latency_ms != null) metaParts.push(`${obj.latency_ms}ms`);
  if (obj.elapsed_ms != null) metaParts.push(`${obj.elapsed_ms}ms`);
  if (obj.token_usage?.total_tokens != null) {
    metaParts.push(`tokens ${obj.token_usage.total_tokens}`);
  } else if (
    obj.token_usage?.prompt_tokens != null ||
    obj.token_usage?.completion_tokens != null
  ) {
    metaParts.push(
      `tokens ${obj.token_usage.prompt_tokens ?? "?"}+${
        obj.token_usage.completion_tokens ?? "?"
      }`,
    );
  }
  if (obj.model) metaParts.push(obj.model);

  let detail = "";
  if (obj.output_preview) {
    detail = obj.output_preview;
  } else if (obj.request_preview) {
    detail = obj.request_preview;
  } else if (obj.detail_preview) {
    detail = obj.detail_preview;
  } else if (obj.query) {
    detail = `query: ${obj.query}`;
  }

  let tone = "step";
  if (phase === "error" || phase === "llm_error") tone = "error";
  else if (phase === "done" || phase === "parse") tone = "feature";
  else if (phase === "llm_response") tone = "llm";

  return {
    kind: obj?.kind || "case_gen_log",
    title: label,
    body: obj?.message || "",
    meta: metaParts.join(" · "),
    detail,
    tone,
    _idx: index,
  };
}

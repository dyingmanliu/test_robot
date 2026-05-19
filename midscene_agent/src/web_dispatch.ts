/**
 * Web 测试平台通过 stdin 下发的任务载荷。
 */

export const WEB_DISPATCH_VERSION = 1;

export type WebExecutionMode = 'natural' | 'yaml';

export interface WebTestDispatch {
  version: number;
  run_id?: number;
  case_id?: number;
  robot_instance_id?: number | null;
  /** autoglm | midscene — 决定模型环境（AutoGLM 走智谱） */
  agent_backend?: string;
  /** android | harmonyos — 决定 ADB / HDC 设备层 */
  device_platform?: string;
  /** ADB serial 或 HDC target ID */
  device_id?: string;
  /** natural：自然语言 agent_task；yaml：执行 yaml_script */
  execution_mode?: WebExecutionMode;
  /** structured 模式下的可执行全文 */
  agent_task?: string;
  /** 结构化用例拆步后逐步 aiAct（优先于单段 agent_task） */
  agent_steps?: string[];
  /** Midscene YAML 脚本（须含 tasks:） */
  yaml_script?: string;
  task_text?: string;
  preconditions?: string;
  steps_json?: string | unknown[];
  case_format?: string;
}

function optUInt(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

function parseExecutionMode(v: unknown): WebExecutionMode {
  const m = String(v ?? 'natural').toLowerCase();
  if (m === 'yaml') return 'yaml';
  return 'natural';
}

export function parseWebDispatchJson(raw: string): WebTestDispatch {
  const trimmed = raw.trim();
  if (!trimmed) {
    throw new Error('Web 下发任务为空：stdin 无内容');
  }
  let data: unknown;
  try {
    data = JSON.parse(trimmed);
  } catch {
    throw new Error('Web 下发任务不是合法 JSON');
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw new Error('Web 下发任务 JSON 须为对象');
  }
  const o = data as Record<string, unknown>;
  const version = Number(o.version ?? WEB_DISPATCH_VERSION);
  if (!Number.isFinite(version) || version < 1) {
    throw new Error('Web 下发任务 version 无效');
  }

  const execution_mode = parseExecutionMode(
    o.execution_mode ?? (o.case_format === 'yaml' ? 'yaml' : 'natural'),
  );

  const agent_task =
    o.agent_task !== undefined ? String(o.agent_task).trim() : undefined;
  const agent_steps = Array.isArray(o.agent_steps)
    ? o.agent_steps
        .map((s) => String(s ?? '').trim())
        .filter((s) => s.length > 0)
    : undefined;
  const yaml_script =
    o.yaml_script !== undefined ? String(o.yaml_script).trim() : undefined;

  if (execution_mode === 'yaml') {
    if (!yaml_script) {
      throw new Error('YAML 模式缺少 yaml_script');
    }
  } else if (!agent_task && !(agent_steps && agent_steps.length)) {
    throw new Error('自然语言模式缺少 agent_task / agent_steps 或内容为空');
  }

  const rid = o.robot_instance_id;
  let robot_instance_id: number | null | undefined;
  if (rid === undefined) {
    robot_instance_id = undefined;
  } else if (rid === null) {
    robot_instance_id = null;
  } else {
    const n = Number(rid);
    robot_instance_id = Number.isFinite(n) ? n : undefined;
  }

  return {
    version,
    run_id: optUInt(o.run_id),
    case_id: optUInt(o.case_id),
    robot_instance_id,
    agent_backend:
      o.agent_backend !== undefined ? String(o.agent_backend) : undefined,
    device_platform:
      o.device_platform !== undefined ? String(o.device_platform) : undefined,
    device_id: o.device_id !== undefined ? String(o.device_id).trim() : undefined,
    execution_mode,
    agent_task,
    agent_steps: agent_steps?.length ? agent_steps : undefined,
    yaml_script,
    task_text: o.task_text !== undefined ? String(o.task_text) : undefined,
    preconditions:
      o.preconditions !== undefined ? String(o.preconditions) : undefined,
    steps_json: o.steps_json as string | unknown[] | undefined,
    case_format:
      o.case_format !== undefined ? String(o.case_format) : undefined,
  };
}

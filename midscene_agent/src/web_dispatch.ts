/**
 * Web 测试平台通过 stdin 下发的任务载荷（与 Python build_agent_task_text 对齐字段）。
 */

export const WEB_DISPATCH_VERSION = 1;

export interface WebTestDispatch {
  version: number;
  run_id?: number;
  case_id?: number;
  robot_instance_id?: number | null;
  /** 与后端 build_agent_task_text 一致的可执行全文 */
  agent_task: string;
  task_text?: string;
  preconditions?: string;
  /** 原始 JSON 字符串或已解析数组 */
  steps_json?: string | unknown[];
}

function optUInt(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
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
  const agent_task = String(o.agent_task ?? '').trim();
  if (!agent_task) {
    throw new Error('Web 下发任务缺少 agent_task 或内容为空');
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
    agent_task,
    task_text: o.task_text !== undefined ? String(o.task_text) : undefined,
    preconditions:
      o.preconditions !== undefined ? String(o.preconditions) : undefined,
    steps_json: o.steps_json as string | unknown[] | undefined,
  };
}

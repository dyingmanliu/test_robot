/**
 * Midscene 模型调用日志（stderr + 可选 JSONL model_usage 供 Web 后端解析）。
 */

import type { ExploreMetrics } from './explore_metrics.js';

export interface ModelUsagePayload {
  kind: 'model_usage';
  op: 'aiQuery' | 'aiAct';
  label: string;
  duration_ms: number;
  model?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  estimated?: boolean;
}

/** 粗略估算 token（中英混合，用于 SDK 未返回 usage 时） */
export function estimateTokens(text: string): number {
  const s = (text || '').trim();
  if (!s) return 0;
  let n = 0;
  for (const ch of s) {
    n += ch.charCodeAt(0) > 127 ? 1.2 : 0.25;
  }
  return Math.max(1, Math.round(n));
}

function logStderr(payload: ModelUsagePayload): void {
  const est = payload.estimated ? ' (估算)' : '';
  const tok =
    payload.total_tokens != null
      ? ` tokens=${payload.total_tokens}${est} (prompt=${payload.prompt_tokens ?? '?'}, completion=${payload.completion_tokens ?? '?'})`
      : '';
  process.stderr.write(
    `[midscene-llm] ${payload.op} "${payload.label}" ${payload.duration_ms}ms${tok} model=${payload.model ?? process.env.MIDSCENE_MODEL_NAME ?? 'unknown'}\n`,
  );
}

export async function logModelCall<T>(
  op: 'aiQuery' | 'aiAct',
  label: string,
  fn: () => Promise<T>,
  options: {
    machineOut?: boolean;
    /** 用于估算 prompt token 的文本摘要 */
    promptHint?: string;
    /** 从结果提取 completion 文本以估算 token */
    resultToText?: (result: T) => string;
    /** 功能遍历观测 */
    metrics?: ExploreMetrics;
  } = {},
): Promise<T> {
  const t0 = Date.now();
  try {
    const result = await fn();
    options.metrics?.onLlm(op);
    const duration_ms = Date.now() - t0;
    const completionText = options.resultToText
      ? options.resultToText(result)
      : typeof result === 'string'
        ? result
        : JSON.stringify(result ?? '');
    const prompt_tokens = estimateTokens(options.promptHint ?? label);
    const completion_tokens = estimateTokens(completionText);
    const payload: ModelUsagePayload = {
      kind: 'model_usage',
      op,
      label,
      duration_ms,
      model: process.env.MIDSCENE_MODEL_NAME,
      prompt_tokens,
      completion_tokens,
      total_tokens: prompt_tokens + completion_tokens,
      estimated: true,
    };
    logStderr(payload);
    if (options.machineOut) {
      process.stdout.write(`${JSON.stringify(payload)}\n`);
    }
    return result;
  } catch (err) {
    const duration_ms = Date.now() - t0;
    process.stderr.write(
      `[midscene-llm] ${op} "${label}" FAILED after ${duration_ms}ms: ${err instanceof Error ? err.message : String(err)}\n`,
    );
    throw err;
  }
}

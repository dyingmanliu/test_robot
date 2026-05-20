/**
 * 执行 Midscene YAML 脚本（Android / HarmonyOS）。
 */

import {
  assertMidsceneModelEnv,
  applyAgentBackendModelEnv,
  loadAgentConfig,
  type MidsceneAgentConfig,
} from './config.js';
import { createMidsceneRuntime } from './device_runtime.js';
import type { AgentRunOutcome, StepCallback } from './agent.js';

export async function runMidsceneYamlScript(
  yamlScript: string,
  config: Partial<MidsceneAgentConfig> = {},
  options: { onStep?: StepCallback } = {},
): Promise<AgentRunOutcome> {
  const trimmed = yamlScript.trim();
  if (!trimmed) {
    return { ok: false, message: 'YAML 脚本为空' };
  }

  const cfg = loadAgentConfig(config);
  applyAgentBackendModelEnv(cfg.agentBackend ?? 'midscene');
  assertMidsceneModelEnv();

  const platform = cfg.devicePlatform ?? 'harmonyos';
  let currentStep = 0;
  let currentTask = '';

  const finishCurrent = (phase: 'done' | 'error', error?: string) => {
    if (currentStep <= 0 || !currentTask) return;
    options.onStep?.({
      step: currentStep,
      phase,
      task: currentTask,
      error,
    });
  };

  try {
    const runtime = await createMidsceneRuntime(platform, cfg);
    await runtime.runYaml(trimmed, (tip) => {
      finishCurrent('done');
      currentStep += 1;
      currentTask = tip;
      options.onStep?.({ step: currentStep, phase: 'start', task: tip });
    });
    finishCurrent('done');

    return {
      ok: true,
      message: 'YAML 脚本执行完成',
      reportFile: runtime.reportFile,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    finishCurrent('error', message);
    return { ok: false, message };
  }
}

/** @deprecated */
export const runHarmonyYamlScript = runMidsceneYamlScript;

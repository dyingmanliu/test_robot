/**
 * 跨平台 Midscene 测试 Agent（Android + HarmonyOS）。
 * 兼容导出 HarmonyTestAgent 别名。
 */

import {
  applyAgentBackendModelEnv,
  assertMidsceneModelEnv,
  loadAgentConfig,
  type MidsceneAgentConfig,
} from './config.js';
import { createMidsceneRuntime } from './device_runtime.js';
import type { DevicePlatform } from './platform.js';

export interface AgentRunOutcome {
  ok: boolean;
  message: string;
  reportFile?: string;
}

export type StepCallback = (info: {
  step: number;
  phase: 'start' | 'done' | 'error';
  task: string;
  error?: string;
}) => void;

export class MidsceneTestAgent {
  private readonly cfg: MidsceneAgentConfig;

  constructor(config: Partial<MidsceneAgentConfig> = {}) {
    this.cfg = loadAgentConfig(config);
    applyAgentBackendModelEnv(this.cfg.agentBackend ?? 'midscene');
  }

  get devicePlatform(): DevicePlatform {
    return this.cfg.devicePlatform ?? 'harmonyos';
  }

  async run(
    task: string,
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    const trimmed = task.trim();
    if (!trimmed) {
      return { ok: false, message: '未提供任务描述' };
    }

    assertMidsceneModelEnv();

    try {
      options.onStep?.({ step: 1, phase: 'start', task: trimmed });
      const runtime = await createMidsceneRuntime(this.devicePlatform, this.cfg);
      await runtime.connect();
      await runtime.aiAct(trimmed);

      if (this.cfg.verbose && runtime.reportFile) {
        console.log(`Midscene 报告: ${runtime.reportFile}`);
      }

      options.onStep?.({ step: 1, phase: 'done', task: trimmed });
      return {
        ok: true,
        message: '任务执行完成',
        reportFile: runtime.reportFile,
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      options.onStep?.({
        step: 1,
        phase: 'error',
        task: trimmed,
        error: message,
      });
      return { ok: false, message };
    }
  }

  async runSteps(
    steps: string[],
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    assertMidsceneModelEnv();

    const list = steps.map((s) => s.trim()).filter(Boolean);
    if (!list.length) {
      return { ok: false, message: '步骤列表为空' };
    }

    try {
      const runtime = await createMidsceneRuntime(this.devicePlatform, this.cfg);
      await runtime.connect();

      for (let i = 0; i < list.length; i += 1) {
        const stepNo = i + 1;
        const stepTask = list[i];
        options.onStep?.({ step: stepNo, phase: 'start', task: stepTask });
        try {
          await runtime.aiAct(stepTask);
          options.onStep?.({ step: stepNo, phase: 'done', task: stepTask });
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : String(err);
          options.onStep?.({
            step: stepNo,
            phase: 'error',
            task: stepTask,
            error: message,
          });
          return {
            ok: false,
            message: `第 ${stepNo} 步失败: ${message}`,
            reportFile: runtime.reportFile,
          };
        }
      }

      return {
        ok: true,
        message: '全部步骤执行完成',
        reportFile: runtime.reportFile,
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, message };
    }
  }

  async runYamlScript(
    yamlScript: string,
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    const { runMidsceneYamlScript } = await import('./yaml_runner.js');
    return runMidsceneYamlScript(yamlScript, this.cfg, options);
  }
}

/** @deprecated 使用 MidsceneTestAgent；保留别名兼容旧脚本 */
export const HarmonyTestAgent = MidsceneTestAgent;

/**
 * HarmonyOS APP 自动化测试 Agent — 基于字节跳动 Midscene.js (@midscene/harmony)。
 *
 * 适用于 HarmonyOS NEXT / 6.x：通过 HDC 连接设备，视觉大模型驱动 UI 操作。
 */

import {
  HarmonyAgent,
  HarmonyDevice,
  getConnectedDevices,
} from '@midscene/harmony';

import {
  assertMidsceneModelEnv,
  loadAgentConfig,
  type MidsceneAgentConfig,
} from './config.js';
import { resolveDeviceId, resolveHdcExecutablePath } from './hdc.js';

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

export class HarmonyTestAgent {
  private readonly cfg: MidsceneAgentConfig;

  constructor(config: Partial<MidsceneAgentConfig> = {}) {
    this.cfg = loadAgentConfig(config);
  }

  /**
   * 执行单条自然语言测试任务（Midscene Auto Planning / aiAct）。
   */
  async run(
    task: string,
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    const trimmed = task.trim();
    if (!trimmed) {
      return { ok: false, message: '未提供任务描述' };
    }

    assertMidsceneModelEnv();

    let device: HarmonyDevice | undefined;
    let agent: HarmonyAgent | undefined;

    try {
      options.onStep?.({ step: 1, phase: 'start', task: trimmed });

      const deviceId = await this.resolveDeviceId();
      const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
        autoDismissKeyboard: this.cfg.autoDismissKeyboard,
      };
      deviceOpts.hdcPath = resolveHdcExecutablePath(this.cfg.hdcHome);

      device = new HarmonyDevice(deviceId, deviceOpts);
      agent = new HarmonyAgent(device, {
        aiActionContext: this.cfg.aiActionContext,
      });

      await device.connect();
      await agent.aiAct(trimmed);

      const reportFile =
        typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
      if (this.cfg.verbose && reportFile) {
        console.log(`Midscene 报告: ${reportFile}`);
      }

      options.onStep?.({ step: 1, phase: 'done', task: trimmed });
      return {
        ok: true,
        message: '任务执行完成',
        reportFile,
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

  /**
   * 按顺序执行多条步骤（每步一次 aiAct），任一步失败则中止。
   */
  async runSteps(
    steps: string[],
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    assertMidsceneModelEnv();

    const list = steps.map((s) => s.trim()).filter(Boolean);
    if (!list.length) {
      return { ok: false, message: '步骤列表为空' };
    }

    let device: HarmonyDevice | undefined;
    let agent: HarmonyAgent | undefined;

    try {
      const deviceId = await this.resolveDeviceId();
      const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
        autoDismissKeyboard: this.cfg.autoDismissKeyboard,
      };
      deviceOpts.hdcPath = resolveHdcExecutablePath(this.cfg.hdcHome);

      device = new HarmonyDevice(deviceId, deviceOpts);
      agent = new HarmonyAgent(device, {
        aiActionContext: this.cfg.aiActionContext,
      });
      await device.connect();

      for (let i = 0; i < list.length; i += 1) {
        const stepNo = i + 1;
        const stepTask = list[i];
        options.onStep?.({ step: stepNo, phase: 'start', task: stepTask });
        try {
          await agent.aiAct(stepTask);
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
            reportFile:
              typeof agent.reportFile === 'string'
                ? agent.reportFile
                : undefined,
          };
        }
      }

      const reportFile =
        typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
      return { ok: true, message: '全部步骤执行完成', reportFile };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      return { ok: false, message };
    }
  }

  /**
   * 执行 Midscene YAML 脚本（仅 tasks 段；设备由当前 Agent 连接）。
   */
  async runYamlScript(
    yamlScript: string,
    options: { onStep?: StepCallback } = {},
  ): Promise<AgentRunOutcome> {
    const { runHarmonyYamlScript } = await import('./yaml_runner.js');
    return runHarmonyYamlScript(yamlScript, this.cfg, options);
  }

  private async resolveDeviceId(): Promise<string> {
    if (this.cfg.deviceId) {
      return resolveDeviceId(this.cfg.deviceId, this.cfg.hdcHome);
    }
    const devices = await getConnectedDevices(
      resolveHdcExecutablePath(this.cfg.hdcHome),
    );
    if (devices.length) {
      return devices[0].deviceId;
    }
    return resolveDeviceId(undefined, this.cfg.hdcHome);
  }
}

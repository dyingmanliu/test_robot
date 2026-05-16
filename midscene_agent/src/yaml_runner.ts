/**
 * 执行 Midscene YAML 脚本（HarmonyAgent.runYaml，仅解析 tasks 段）。
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
import type { AgentRunOutcome, StepCallback } from './agent.js';

export async function runHarmonyYamlScript(
  yamlScript: string,
  config: Partial<MidsceneAgentConfig> = {},
  options: { onStep?: StepCallback } = {},
): Promise<AgentRunOutcome> {
  const trimmed = yamlScript.trim();
  if (!trimmed) {
    return { ok: false, message: 'YAML 脚本为空' };
  }

  assertMidsceneModelEnv();
  const cfg = loadAgentConfig(config);

  let device: HarmonyDevice | undefined;
  let agent: HarmonyAgent | undefined;
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
    const deviceId = await resolveDeviceIdForConfig(cfg);
    const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
      autoDismissKeyboard: cfg.autoDismissKeyboard,
    };
    deviceOpts.hdcPath = resolveHdcExecutablePath(cfg.hdcHome);

    device = new HarmonyDevice(deviceId, deviceOpts);
    agent = new HarmonyAgent(device, {
      aiActionContext: cfg.aiActionContext,
      onTaskStartTip: async (tip: string) => {
        finishCurrent('done');
        currentStep += 1;
        currentTask = tip;
        options.onStep?.({ step: currentStep, phase: 'start', task: tip });
      },
    });

    await device.connect();
    await agent.runYaml(trimmed);
    finishCurrent('done');

    const reportFile =
      typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
    return {
      ok: true,
      message: 'YAML 脚本执行完成',
      reportFile,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    finishCurrent('error', message);
    return {
      ok: false,
      message,
      reportFile:
        agent && typeof agent.reportFile === 'string'
          ? agent.reportFile
          : undefined,
    };
  }
}

async function resolveDeviceIdForConfig(
  cfg: MidsceneAgentConfig,
): Promise<string> {
  if (cfg.deviceId) {
    return resolveDeviceId(cfg.deviceId, cfg.hdcHome);
  }
  const devices = await getConnectedDevices(resolveHdcExecutablePath(cfg.hdcHome));
  if (devices.length) {
    return devices[0].deviceId;
  }
  return resolveDeviceId(undefined, cfg.hdcHome);
}

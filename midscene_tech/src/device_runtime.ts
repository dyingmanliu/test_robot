/**
 * 按设备平台创建 Midscene Device/Agent（Android @midscene/android、鸿蒙 @midscene/harmony）。
 */

import type { DevicePlatform } from './platform.js';
import type { MidsceneAgentConfig } from './config.js';
import { resolveDeviceId as resolveHdcDeviceId, resolveHdcExecutablePath } from './hdc.js';

export interface MidsceneRuntime {
  platform: DevicePlatform;
  connect(): Promise<void>;
  aiAct(task: string): Promise<void>;
  runYaml(yamlScript: string, onTaskStart?: (tip: string) => void): Promise<void>;
  readonly reportFile?: string;
}

export async function createMidsceneRuntime(
  platform: DevicePlatform,
  cfg: MidsceneAgentConfig,
): Promise<MidsceneRuntime> {
  if (platform === 'android') {
    const { AndroidAgent, AndroidDevice, getConnectedDevices } = await import(
      '@midscene/android'
    );
    let udid = cfg.deviceId?.trim();
    if (!udid) {
      const devices = await getConnectedDevices();
      if (!devices.length) {
        throw new Error(
          '未检测到 Android 设备：请连接真机并开启 USB 调试（adb devices）',
        );
      }
      udid = devices[0].udid;
    }
    const device = new AndroidDevice(udid, {
      autoDismissKeyboard: cfg.autoDismissKeyboard,
    });
    let agent = new AndroidAgent(device, {
      aiActionContext: cfg.aiActionContext,
    });
    return {
      platform,
      async connect() {
        await device.connect();
      },
      async aiAct(task: string) {
        await agent.aiAct(task);
      },
      async runYaml(yamlScript, onTaskStart) {
        agent = new AndroidAgent(device, {
          aiActionContext: cfg.aiActionContext,
          onTaskStartTip: onTaskStart
            ? async (tip: string) => {
                onTaskStart(tip);
              }
            : undefined,
        });
        await agent.runYaml(yamlScript);
      },
      get reportFile() {
        return typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
      },
    };
  }

  const { HarmonyAgent, HarmonyDevice, getConnectedDevices } = await import(
    '@midscene/harmony'
  );
  const deviceId = await resolveHdcDeviceIdForConfig(cfg);
  const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
    autoDismissKeyboard: cfg.autoDismissKeyboard,
    hdcPath: resolveHdcExecutablePath(cfg.hdcHome),
  };
  const device = new HarmonyDevice(deviceId, deviceOpts);
  let agent = new HarmonyAgent(device, {
    aiActionContext: cfg.aiActionContext,
  });

  return {
    platform,
    async connect() {
      await device.connect();
    },
    async aiAct(task: string) {
      await agent.aiAct(task);
    },
    async runYaml(yamlScript, onTaskStart) {
      agent = new HarmonyAgent(device, {
        aiActionContext: cfg.aiActionContext,
        onTaskStartTip: onTaskStart
          ? async (tip: string) => {
              onTaskStart(tip);
            }
          : undefined,
      });
      await agent.runYaml(yamlScript);
    },
    get reportFile() {
      return typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
    },
  };
}

async function resolveHdcDeviceIdForConfig(
  cfg: MidsceneAgentConfig,
): Promise<string> {
  const { getConnectedDevices } = await import('@midscene/harmony');
  if (cfg.deviceId) {
    return resolveHdcDeviceId(cfg.deviceId, cfg.hdcHome);
  }
  const devices = await getConnectedDevices(resolveHdcExecutablePath(cfg.hdcHome));
  if (devices.length) {
    return devices[0].deviceId;
  }
  return resolveHdcDeviceId(undefined, cfg.hdcHome);
}

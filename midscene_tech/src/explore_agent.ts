/**
 * 功能遍历用 Agent 门面：按平台创建 Midscene Android / Harmony 实例。
 */

import type { DevicePlatform } from './platform.js';
import { parseDevicePlatform } from './platform.js';
import type { MidsceneAgentConfig } from './config.js';
import { resolveDeviceId, resolveHdcExecutablePath } from './hdc.js';

export interface ExploreAgentHandle {
  platform: DevicePlatform;
  aiAct: (task: string) => Promise<void>;
  aiQuery: <T>(prompt: string) => Promise<T>;
  reportFile?: string;
  /** 鸿蒙启动应用时保留原生 device/agent */
  harmonyDevice?: import('@midscene/harmony').HarmonyDevice;
  harmonyAgent?: import('@midscene/harmony').HarmonyAgent;
}

export async function createExploreAgent(
  cfg: MidsceneAgentConfig,
  platformRaw?: string,
): Promise<ExploreAgentHandle> {
  const platform = parseDevicePlatform(
    platformRaw ?? process.env.MIDSCENE_DEVICE_PLATFORM,
  );

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
    const agent = new AndroidAgent(device, {
      aiActionContext: cfg.aiActionContext,
    });
    await device.connect();
    return {
      platform,
      async aiAct(task: string) {
        await agent.aiAct(task);
      },
      async aiQuery<T>(prompt: string) {
        return agent.aiQuery<T>(prompt);
      },
      get reportFile() {
        return typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
      },
    };
  }

  const { HarmonyAgent, HarmonyDevice, getConnectedDevices } = await import(
    '@midscene/harmony'
  );
  const deviceId = cfg.deviceId
    ? await resolveDeviceId(cfg.deviceId, cfg.hdcHome)
    : (await getConnectedDevices(resolveHdcExecutablePath(cfg.hdcHome)))[0]
        ?.deviceId ?? (await resolveDeviceId(undefined, cfg.hdcHome));

  const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
    autoDismissKeyboard: cfg.autoDismissKeyboard,
    hdcPath: resolveHdcExecutablePath(cfg.hdcHome),
  };
  const device = new HarmonyDevice(deviceId, deviceOpts);
  const { applyAppNameMappingToDevice } = await import('./resolve_app_launch.js');
  applyAppNameMappingToDevice(device);
  const agent = new HarmonyAgent(device, {
    aiActionContext: cfg.aiActionContext,
  });
  await device.connect();

  return {
    platform,
    harmonyDevice: device,
    harmonyAgent: agent,
    async aiAct(task: string) {
      await agent.aiAct(task);
    },
    async aiQuery<T>(prompt: string) {
      return agent.aiQuery<T>(prompt);
    },
    get reportFile() {
      return typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
    },
  };
}

/**
 * 示例：HarmonyOS 6.x 设置应用 — 打开设置、滑动、aiQuery、aiAssert。
 * 参考 https://midscenejs.com/harmony-getting-started
 */

import {
  HarmonyAgent,
  HarmonyDevice,
  getConnectedDevices,
} from '@midscene/harmony';

import '../src/config.js';
import { assertMidsceneModelEnv, loadAgentConfig } from '../src/config.js';
import { resolveDeviceId } from '../src/hdc.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function main(): Promise<void> {
  assertMidsceneModelEnv();
  const cfg = loadAgentConfig();

  const deviceId =
    cfg.deviceId ??
    (await getConnectedDevices())[0]?.deviceId ??
    (await resolveDeviceId(undefined, cfg.hdcHome));

  const deviceOpts: ConstructorParameters<typeof HarmonyDevice>[1] = {
    autoDismissKeyboard: cfg.autoDismissKeyboard,
  };
  if (cfg.hdcHome) {
    deviceOpts.hdcPath = `${cfg.hdcHome.replace(/\/$/, '')}/hdc`;
  }

  const device = new HarmonyDevice(deviceId, deviceOpts);
  const agent = new HarmonyAgent(device, {
    aiActionContext: cfg.aiActionContext,
  });

  await device.connect();

  try {
    await agent.launch('com.huawei.hmos.settings');
    await sleep(2000);
    await agent.aiAct('向下滑动一屏');

    const items = await agent.aiQuery<string[]>(
      'string[], 列出当前可见的设置项名称',
    );
    console.log('设置项:', items);

    await agent.aiAssert('页面上存在设置项列表');

    const reportFile =
      typeof agent.reportFile === 'string' ? agent.reportFile : undefined;
    if (reportFile) {
      console.log('Midscene 报告:', reportFile);
    }
    process.exit(0);
  } catch (err) {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  }
}

main();

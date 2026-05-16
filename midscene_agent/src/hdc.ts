/** HDC (HarmonyOS Device Connector) helpers — 连接 HarmonyOS 6.x 设备。 */

import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);

export interface HdcTarget {
  deviceId: string;
}

function hdcBin(hdcHome?: string): string {
  if (hdcHome?.trim()) {
    return `${hdcHome.replace(/\/$/, '')}/hdc`;
  }
  return 'hdc';
}

async function runHdc(args: string[], hdcHome?: string): Promise<string> {
  const bin = hdcBin(hdcHome);
  try {
    const { stdout } = await execFileAsync(bin, args, {
      timeout: 20_000,
      env: hdcHome ? { ...process.env, HDC_HOME: hdcHome } : process.env,
    });
    return stdout.trim();
  } catch (err: unknown) {
    const e = err as NodeJS.ErrnoException & { stderr?: string };
    if (e.code === 'ENOENT') {
      throw new Error(
        `未找到 HDC 命令 (${bin})。请安装 DevEco Studio / HarmonyOS 命令行工具，` +
          '并将 hdc 加入 PATH，或设置 HDC_HOME 指向 hdc 所在目录。',
      );
    }
    throw new Error(
      `hdc ${args.join(' ')} 失败: ${e.stderr?.trim() || e.message || String(err)}`,
    );
  }
}

export async function checkHdcVersion(hdcHome?: string): Promise<string> {
  return runHdc(['version'], hdcHome);
}

/** 解析 `hdc list targets` 输出，取在线设备 ID 列表。 */
export async function listHdcTargets(hdcHome?: string): Promise<HdcTarget[]> {
  const out = await runHdc(['list', 'targets'], hdcHome);
  return out
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('[Empty]'))
    .map((deviceId) => ({ deviceId }));
}

export async function resolveDeviceId(
  preferred?: string,
  hdcHome?: string,
): Promise<string> {
  const targets = await listHdcTargets(hdcHome);
  if (!targets.length) {
    throw new Error(
      '未检测到 HarmonyOS 设备。请开启开发者模式与 USB 调试后执行: hdc list targets',
    );
  }
  if (preferred) {
    const hit = targets.find((t) => t.deviceId === preferred);
    if (!hit) {
      throw new Error(
        `未找到设备 ${preferred}。当前在线: ${targets.map((t) => t.deviceId).join(', ')}`,
      );
    }
    return preferred;
  }
  return targets[0].deviceId;
}

/**
 * 功能点遍历：校验前台是否仍在被测应用内，避免 DFS 误入其他 App。
 */

import { hdcShell } from './hdc.js';

export function normalizeBundleId(bundle: string): string {
  return bundle.trim().split('/')[0]!.toLowerCase();
}

export function bundleMatches(foreground: string, target: string): boolean {
  const f = normalizeBundleId(foreground);
  const t = normalizeBundleId(target);
  if (!f || !t) return true;
  if (f === t) return true;
  return f.startsWith(`${t}.`) || t.startsWith(`${f}.`);
}

/** 解析 `aa dump -l` 前台应用 bundleName */
export async function getHarmonyForegroundBundle(
  hdcHome?: string,
  deviceId?: string,
): Promise<string | null> {
  try {
    const output = await hdcShell('aa dump -l', hdcHome, deviceId);
    if (!output) return null;
    let currentBundle: string | null = null;
    for (const line of output.split('\n')) {
      if (line.includes('app name [')) {
        const m = line.match(/\[([^\]]+)\]/);
        if (m) currentBundle = m[1]!.trim();
      }
      if (
        currentBundle &&
        (line.includes('state #FOREGROUND') ||
          line.toLowerCase().includes('state #foreground'))
      ) {
        return currentBundle;
      }
      if (line.includes('Mission ID')) {
        currentBundle = null;
      }
    }
  } catch {
    return null;
  }
  return null;
}

export function buildExploreActionContext(
  appName: string,
  bundleId: string,
  devicePlatform: string,
): string {
  const base =
    devicePlatform === 'android'
      ? 'Android 真机。系统语言可能为中文。'
      : 'HarmonyOS 真机。系统语言可能为中文。';
  const scope = bundleId
    ? `【硬性约束】全程只在被测应用内操作，目标包名 ${bundleId}（${appName}）。禁止打开华为商城、应用市场、浏览器或其他无关 App；禁止回到桌面后随意点开别的应用。返回时只能在应用内逐级返回，不要退出到桌面。若误跳到其他应用，不要继续探索，应停止点击无关控件。`
    : `【硬性约束】全程只在被测应用「${appName}」内操作，禁止打开其他 App 或回到桌面后乱点。`;
  return `${base} ${scope} 权限/协议弹窗仅在当前应用流程内处理。`;
}

export function scopedTapTask(
  itemName: string,
  appName: string,
  bundleId: string,
): string {
  const scope = bundleId
    ? `【仅包名 ${bundleId} 的「${appName}」内】`
    : `【仅在「${appName}」内】`;
  return `${scope}点击「${itemName}」进入对应页面；不要启动或切换到其他应用`;
}

export function scopedBackTask(appName: string, bundleId: string): string {
  const scope = bundleId ? `应用 ${bundleId}（${appName}）` : `「${appName}」`;
  return `在${scope}内返回上一级页面；不要退出到桌面，不要打开其他应用`;
}

/** 标题/界面文案疑似已离开被测应用（系统钱包、商城、桌面等） */
export function isOffAppScreenTitle(title: string): boolean {
  const t = title.trim();
  if (!t) return false;
  return /站外|华为商城|应用市场|桌面|launcher|钱包|华为钱包|系统设置|权限|协议|欢迎|同意与|服务条款|应用商店/i.test(
    t,
  );
}

export async function harmonyPressBack(
  hdcHome?: string,
  deviceId?: string,
): Promise<void> {
  await hdcShell('uitest uiInput keyEvent Back', hdcHome, deviceId);
}

export async function readForegroundBundle(
  devicePlatform: string,
  hdcHome?: string,
  deviceId?: string,
): Promise<string | null> {
  if (devicePlatform !== 'harmonyos') return null;
  return getHarmonyForegroundBundle(hdcHome, deviceId);
}

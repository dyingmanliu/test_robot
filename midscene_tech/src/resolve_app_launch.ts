/**
 * 根据 APP 显示名称解析并启动应用（无需用户填写 Bundle ID）。
 */

import type { HarmonyAgent, HarmonyDevice } from '@midscene/harmony';

import { hdcShell, queryMainAbility } from './hdc.js';
import { logModelCall } from './model_log.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function normalizeName(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, '');
}

/** 环境变量 MIDSCENE_APP_NAME_MAP：JSON，如 {"设置":"com.huawei.hmos.settings","懂车帝":"com.ss.dcar.auto/DcarAbility"} */
export function loadAppNameMapping(): Record<string, string> {
  const raw = process.env.MIDSCENE_APP_NAME_MAP?.trim();
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return {};
    }
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(parsed)) {
      if (typeof v === 'string' && v.trim()) {
        out[normalizeName(k)] = v.trim();
      }
    }
    return out;
  } catch {
    return {};
  }
}

function mappingLookup(
  appName: string,
  mapping: Record<string, string>,
): string | undefined {
  const key = normalizeName(appName);
  if (mapping[key]) return mapping[key];
  for (const [k, v] of Object.entries(mapping)) {
    if (key.includes(k) || k.includes(key)) return v;
  }
  return undefined;
}

function looksLikeBundleId(s: string): boolean {
  return /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)+$/i.test(s.trim());
}

async function startBundleWithMainAbility(
  launchTarget: string,
  hdcHome?: string,
): Promise<void> {
  const trimmed = launchTarget.trim();
  if (trimmed.includes('/')) {
    const [bundle, ability] = trimmed.split('/', 2);
    const out = await hdcShell(
      `aa start -a ${ability} -b ${bundle}`,
      hdcHome,
    );
    if (out.includes('error:')) {
      throw new Error(`启动失败: ${out.trim()}`);
    }
    return;
  }

  const bundle = trimmed;
  try {
    const out = await hdcShell(`aa start -a EntryAbility -b ${bundle}`, hdcHome);
    if (!out.includes('error:')) return;
  } catch {
    /* try main ability */
  }

  const main = await queryMainAbility(bundle, hdcHome);
  if (!main) {
    throw new Error(`无法解析 ${bundle} 的主 Ability，请在 MIDSCENE_APP_NAME_MAP 中配置 bundle/Ability`);
  }
  const out = await hdcShell(`aa start -a ${main} -b ${bundle}`, hdcHome);
  if (out.includes('error:')) {
    throw new Error(`启动 ${bundle}/${main} 失败: ${out.trim()}`);
  }
}

export interface LaunchAppByNameOptions {
  hdcHome?: string;
  machineOut?: boolean;
}

export interface LaunchAppByNameResult {
  /** 实际用于启动的 URI（可能为 bundle/Ability 或仅记录为 aiAct） */
  launch_uri: string;
  bundle_id: string;
}

/**
 * 按 APP 名称启动：环境映射 → 包名直启 → 视觉 aiAct 打开。
 */
export async function launchAppByName(
  agent: HarmonyAgent,
  device: HarmonyDevice,
  appName: string,
  options: LaunchAppByNameOptions = {},
): Promise<LaunchAppByNameResult> {
  const name = appName.trim();
  if (!name) {
    throw new Error('APP 名称不能为空');
  }

  const mapping = loadAppNameMapping();
  if (Object.keys(mapping).length) {
    device.setAppNameMapping?.(mapping);
  }

  const mapped = mappingLookup(name, mapping);
  if (mapped) {
    await startBundleWithMainAbility(mapped, options.hdcHome);
    const bundle = mapped.includes('/') ? mapped.split('/')[0]! : mapped;
    return { launch_uri: mapped, bundle_id: bundle };
  }

  if (looksLikeBundleId(name) || name.includes('/')) {
    await startBundleWithMainAbility(name, options.hdcHome);
    const bundle = name.includes('/') ? name.split('/')[0]! : name;
    return { launch_uri: name, bundle_id: bundle };
  }

  try {
    await agent.launch(name);
    return { launch_uri: name, bundle_id: '' };
  } catch {
    /* Midscene 无法按名称解析时走视觉打开 */
  }

  const openTask = `在设备上打开名为「${name}」的应用，从桌面或应用列表进入其主界面`;
  await logModelCall('aiAct', openTask, () => agent.aiAct(openTask), {
    machineOut: options.machineOut,
    promptHint: openTask,
  });
  await sleep(2500);
  return { launch_uri: `aiAct:${name}`, bundle_id: '' };
}

/** 使用 bm dump -a 中的 bundleName（APP ID）启动。 */
export async function launchAppByBundleId(
  bundleId: string,
  hdcHome?: string,
): Promise<{ bundle_id: string; launch_uri: string }> {
  const id = bundleId.trim();
  if (!id || !looksLikeBundleId(id.split('/')[0] ?? id)) {
    throw new Error(`无效的 APP ID（bundleName）: ${bundleId}`);
  }
  await startBundleWithMainAbility(id, hdcHome);
  const bundle = id.includes('/') ? id.split('/')[0]! : id;
  return { bundle_id: bundle, launch_uri: id };
}

export function applyAppNameMappingToDevice(device: HarmonyDevice): void {
  const mapping = loadAppNameMapping();
  if (Object.keys(mapping).length && device.setAppNameMapping) {
    device.setAppNameMapping(mapping);
  }
}

/** 设备平台：与执行引擎（autoglm / midscene）解耦。 */

export type DevicePlatform = 'android' | 'harmonyos';

export type AgentBackend = 'autoglm' | 'midscene';

export function parseDevicePlatform(raw: unknown): DevicePlatform {
  const p = String(raw ?? 'harmonyos').trim().toLowerCase();
  if (p === 'android' || p === 'adb') return 'android';
  return 'harmonyos';
}

export function parseAgentBackend(raw: unknown): AgentBackend {
  const b = String(raw ?? 'midscene').trim().toLowerCase();
  return b === 'autoglm' ? 'autoglm' : 'midscene';
}

export function platformLabel(platform: DevicePlatform): string {
  return platform === 'android' ? 'Android / ADB' : 'HarmonyOS / HDC';
}

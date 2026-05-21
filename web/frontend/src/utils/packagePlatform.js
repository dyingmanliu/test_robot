/** 根据安装包扩展名或包名后缀推断设备平台 */

const HARMONY_SUFFIXES = [".hap", ".app"];
const ANDROID_SUFFIXES = [".apk", ".aab"];

export function inferDevicePlatform({ bundleId = "", filename = "" } = {}) {
  for (const raw of [filename, bundleId]) {
    const low = String(raw || "").trim().toLowerCase();
    if (!low) continue;
    if (HARMONY_SUFFIXES.some((s) => low.endsWith(s))) return "harmonyos";
    if (ANDROID_SUFFIXES.some((s) => low.endsWith(s))) return "android";
  }
  return "harmonyos";
}

export function platformLabel(platform) {
  return platform === "android" ? "Android / ADB" : "鸿蒙 / HDC";
}

const HARMONY_PREFIXES = ["鸿蒙", "harmony", "harmonyos", "hdc", "ohos"];
const ANDROID_PREFIXES = ["android", "安卓", "adb"];

/**
 * 解析「平台+应用名」输入，如 鸿蒙京东app、Android京东
 * @returns {{ platform: string, appName: string, error: string }}
 */
export function parsePlatformAppText(text) {
  const raw = String(text || "").trim();
  if (!raw) {
    return { platform: "", appName: "", error: "请填写平台与应用名" };
  }
  const lower = raw.toLowerCase();
  let platform = "";
  let rest = raw;

  for (const p of HARMONY_PREFIXES) {
    if (lower.startsWith(p.toLowerCase())) {
      platform = "harmonyos";
      rest = raw.slice(p.length).trim();
      break;
    }
  }
  if (!platform) {
    for (const p of ANDROID_PREFIXES) {
      if (lower.startsWith(p.toLowerCase())) {
        platform = "android";
        rest = raw.slice(p.length).trim();
        break;
      }
    }
  }
  if (!platform) {
    return {
      platform: "",
      appName: "",
      error: "请在开头标明平台：鸿蒙 或 Android（安卓）",
    };
  }
  let appName = rest;
  if (appName.toLowerCase().endsWith("app")) {
    appName = appName.slice(0, -3).trim();
  }
  if (!appName) {
    return { platform: "", appName: "", error: "请填写应用名称" };
  }
  return { platform, appName, error: "" };
}

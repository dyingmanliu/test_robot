/** Load Midscene / 设备平台 / 模型配置（优先仓库根目录 `.env`）。 */

import { config as loadDotenv } from 'dotenv';
import {
  type AgentBackend,
  type DevicePlatform,
  parseAgentBackend,
  parseDevicePlatform,
} from './platform.js';
import { existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, '../..');
const localEnv = resolve(here, '../.env');
const rootEnv = resolve(repoRoot, '.env');

if (existsSync(rootEnv)) {
  loadDotenv({ path: rootEnv });
} else if (existsSync(localEnv)) {
  loadDotenv({ path: localEnv });
} else {
  loadDotenv();
}

export interface MidsceneAgentConfig {
  /** 目标设备平台 */
  devicePlatform?: DevicePlatform;
  /** 执行引擎（Web 下发 autoglm 时在鸿蒙/Android 上复用智谱模型） */
  agentBackend?: AgentBackend;
  /** 设备 ID：鸿蒙为 HDC serial，Android 为 adb udid */
  deviceId?: string;
  /** HDC 可执行文件所在目录（鸿蒙） */
  hdcHome?: string;
  autoDismissKeyboard?: boolean;
  aiActionContext?: string;
  verbose?: boolean;
}

export function loadAgentConfig(
  overrides: Partial<MidsceneAgentConfig> = {},
): MidsceneAgentConfig {
  const truthy = (v: string | undefined) =>
    v !== undefined && ['1', 'true', 'yes', 'on'].includes(v.toLowerCase());

  const devicePlatform =
    overrides.devicePlatform ??
    parseDevicePlatform(process.env.MIDSCENE_DEVICE_PLATFORM);

  const defaultContext =
    devicePlatform === 'android'
      ? 'Android 真机/模拟器。系统语言可能为中文。若出现权限或协议弹窗，按任务需要同意或关闭。'
      : 'HarmonyOS 6.0 真机/模拟器。系统语言可能为中文。若出现权限或协议弹窗，按任务需要同意或关闭。';

  const deviceId =
    overrides.deviceId ??
    (devicePlatform === 'android'
      ? process.env.ADB_DEVICE_ID
      : process.env.HDC_DEVICE_ID) ??
    undefined;

  return {
    devicePlatform,
    agentBackend:
      overrides.agentBackend ??
      parseAgentBackend(process.env.MIDSCENE_AGENT_BACKEND),
    deviceId,
    hdcHome: overrides.hdcHome ?? process.env.HDC_HOME ?? undefined,
    autoDismissKeyboard:
      overrides.autoDismissKeyboard ??
      (process.env.MIDSCENE_AUTO_DISMISS_KEYBOARD !== undefined
        ? truthy(process.env.MIDSCENE_AUTO_DISMISS_KEYBOARD)
        : true),
    aiActionContext:
      overrides.aiActionContext ??
      process.env.MIDSCENE_AI_ACTION_CONTEXT ??
      defaultContext,
    verbose: overrides.verbose ?? !truthy(process.env.MIDSCENE_QUIET),
  };
}

/** AutoGLM 引擎走 Midscene 设备层时，强制使用智谱等 AutoGLM 模型配置 */
export function applyAgentBackendModelEnv(backend: AgentBackend): void {
  if (backend !== 'autoglm') return;
  const apiKey =
    process.env.BIGMODEL_API_KEY?.trim() || process.env.ZHIPU_API_KEY?.trim();
  if (!apiKey) return;
  process.env.MIDSCENE_MODEL_API_KEY = apiKey;
  process.env.MIDSCENE_MODEL_BASE_URL =
    process.env.OPENAI_BASE_URL?.trim() ||
    'https://open.bigmodel.cn/api/paas/v4';
  if (!process.env.MIDSCENE_MODEL_NAME?.trim()) {
    process.env.MIDSCENE_MODEL_NAME = 'glm-4.6v';
  }
  if (!process.env.MIDSCENE_MODEL_FAMILY?.trim()) {
    process.env.MIDSCENE_MODEL_FAMILY = 'glm-v';
  }
}

/** 若未单独配置 Midscene，则从 Web/AutoGLM 共用的智谱等变量推导（见 model-common-config） */
export function applySharedModelEnvFallbacks(): void {
  const setIfEmpty = (key: string, value: string | undefined) => {
    if (value?.trim() && !process.env[key]?.trim()) {
      process.env[key] = value.trim();
    }
  };

  const baseUrl =
    process.env.MIDSCENE_MODEL_BASE_URL?.trim() ||
    process.env.OPENAI_BASE_URL?.trim() ||
    'https://open.bigmodel.cn/api/paas/v4';
  setIfEmpty('MIDSCENE_MODEL_BASE_URL', baseUrl);

  const isDashScope = (process.env.MIDSCENE_MODEL_BASE_URL || baseUrl)
    .toLowerCase()
    .includes('dashscope');
  const apiKey =
    process.env.MIDSCENE_MODEL_API_KEY?.trim() ||
    (isDashScope ? process.env.DASHSCOPE_API_KEY?.trim() : undefined) ||
    (!isDashScope
      ? process.env.BIGMODEL_API_KEY?.trim() ||
        process.env.ZHIPU_API_KEY?.trim()
      : undefined) ||
    process.env.OPENAI_API_KEY?.trim();
  setIfEmpty('MIDSCENE_MODEL_API_KEY', apiKey);

  const phoneModel = (process.env.PHONE_AGENT_MODEL || 'autoglm-phone').trim();
  const modelName = process.env.MIDSCENE_MODEL_NAME?.trim() || phoneModel;
  setIfEmpty('MIDSCENE_MODEL_NAME', modelName);

  if (!process.env.MIDSCENE_MODEL_FAMILY?.trim()) {
    const name = (process.env.MIDSCENE_MODEL_NAME || modelName).toLowerCase();
    let family = 'glm-v';
    if (name.includes('autoglm')) {
      family = 'auto-glm';
    } else if (name.includes('glm-5v')) {
      family = 'glm-v';
    } else if (name.includes('qwen3.6')) {
      family = 'qwen3.6';
    } else if (name.includes('qwen3.5') || name.includes('qwen3')) {
      family = 'qwen3.5';
    } else if (name.includes('qwen')) {
      family = 'qwen3-vl';
    } else if (name.includes('doubao')) {
      family = 'doubao-seed';
    } else if (name.includes('gemini')) {
      family = 'gemini';
    } else if (name.includes('gpt-5')) {
      family = 'gpt-5';
    }
    process.env.MIDSCENE_MODEL_FAMILY = family;
  }

  // auto-glm 仅负责操作规划；aiAssert/aiQuery 需 Insight 模型（见 model-common-config）
  const family = (process.env.MIDSCENE_MODEL_FAMILY || '').toLowerCase();
  if (family.includes('auto-glm') || family === 'auto-glm-multilingual') {
    const insightKey =
      process.env.MIDSCENE_INSIGHT_MODEL_API_KEY?.trim() || apiKey;
    setIfEmpty('MIDSCENE_INSIGHT_MODEL_API_KEY', insightKey);
    setIfEmpty(
      'MIDSCENE_INSIGHT_MODEL_BASE_URL',
      process.env.MIDSCENE_MODEL_BASE_URL?.trim() || baseUrl,
    );
    setIfEmpty('MIDSCENE_INSIGHT_MODEL_NAME', 'glm-4.6v');
    setIfEmpty('MIDSCENE_INSIGHT_MODEL_FAMILY', 'glm-v');
  }
}

applySharedModelEnvFallbacks();

/** Midscene 模型相关变量见 https://midscenejs.com/model-config */
export function assertMidsceneModelEnv(): void {
  const missing: string[] = [];
  if (!process.env.MIDSCENE_MODEL_API_KEY?.trim()) {
    missing.push('MIDSCENE_MODEL_API_KEY');
  }
  if (!process.env.MIDSCENE_MODEL_BASE_URL?.trim()) {
    missing.push('MIDSCENE_MODEL_BASE_URL');
  }
  if (!process.env.MIDSCENE_MODEL_NAME?.trim()) {
    missing.push('MIDSCENE_MODEL_NAME');
  }
  if (!process.env.MIDSCENE_MODEL_FAMILY?.trim()) {
    missing.push('MIDSCENE_MODEL_FAMILY');
  }
  if (missing.length) {
    throw new Error(
      `缺少 Midscene 模型环境变量: ${missing.join(', ')}。` +
        '请在仓库根目录 .env 中配置，参考 midscene_agent/.env.example 与 https://midscenejs.com/model-strategy',
    );
  }
}

/** Load Midscene / HDC config from environment (repo root `.env` preferred). */

import { config as loadDotenv } from 'dotenv';
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
  /** HDC 设备 serial；不设则使用 `hdc list targets` 第一台 */
  deviceId?: string;
  /** HDC 可执行文件所在目录（对应 HDC_HOME 或 HarmonyDevice hdcPath） */
  hdcHome?: string;
  /** 输入完成后是否自动收起键盘（部分输入框监听 BACK 会清空内容时可设为 false） */
  autoDismissKeyboard?: boolean;
  /** 传给 HarmonyAgent 的 aiActionContext，帮助模型理解鸿蒙场景 */
  aiActionContext?: string;
  /** 是否在控制台打印 Midscene 报告路径等 */
  verbose?: boolean;
}

export function loadAgentConfig(
  overrides: Partial<MidsceneAgentConfig> = {},
): MidsceneAgentConfig {
  const truthy = (v: string | undefined) =>
    v !== undefined && ['1', 'true', 'yes', 'on'].includes(v.toLowerCase());

  return {
    deviceId: overrides.deviceId ?? process.env.HDC_DEVICE_ID ?? undefined,
    hdcHome: overrides.hdcHome ?? process.env.HDC_HOME ?? undefined,
    autoDismissKeyboard:
      overrides.autoDismissKeyboard ??
      (process.env.MIDSCENE_AUTO_DISMISS_KEYBOARD !== undefined
        ? truthy(process.env.MIDSCENE_AUTO_DISMISS_KEYBOARD)
        : true),
    aiActionContext:
      overrides.aiActionContext ??
      process.env.MIDSCENE_AI_ACTION_CONTEXT ??
      'HarmonyOS 6.0 真机/模拟器。系统语言可能为中文。若出现权限或协议弹窗，按任务需要同意或关闭。',
    verbose: overrides.verbose ?? !truthy(process.env.MIDSCENE_QUIET),
  };
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

/** 合并界面快照查询与点击后稳定等待 */

import type { ExploreAgentHandle } from './explore_agent.js';
import { logModelCall } from './model_log.js';
import { normalizeNavItems, sortNavItems } from './explore_common.js';
import type { NavItem } from './explore_types.js';
import type { ExploreMetrics } from './explore_metrics.js';
import { withStepTimeout } from './step_timeout.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export interface ScreenSnapshot {
  screen_title: string;
  nav_items: NavItem[];
  has_sub_pages: boolean;
}

function buildSnapshotPrompt(appName: string): string {
  return (
    `{screen_title: string, nav_items: {name: string, region: string, clickable: boolean}[], has_sub_pages: boolean}, ` +
    `仅在「${appName}」应用当前界面扫描（GIIC）：` +
    'screen_title 为简短中文页面标题（不超过20字）；' +
    'nav_items 列出顶部/底部 Tab、侧栏、工具栏、页面内可点按钮，以及顶部/标题栏的搜索框（含占位文案）；' +
    'has_sub_pages 表示除主 Tab 切换外是否还有可进入的子页面/子菜单；' +
    '若不在该应用内返回 nav_items=[]、has_sub_pages=false。' +
    '不要编造；region 取 top_tab|bottom_tab|side|search_bar|button|tab|list_item|other；' +
    '搜索框 name 固定为「搜索框」（禁止用框内占位文案/热搜词），region 必须为 search_bar；' +
    '不要包含关闭/取消/跳过或纯展示正文。'
  );
}

function parseSnapshotRaw(raw: unknown, appName: string): ScreenSnapshot {
  if (typeof raw === 'object' && raw !== null && !Array.isArray(raw)) {
    const o = raw as Record<string, unknown>;
    const title = String(o.screen_title ?? o.title ?? '').trim() || '未知页面';
    const items = sortNavItems(normalizeNavItems(o.nav_items ?? o.items ?? []));
    const hasSub =
      o.has_sub_pages === true ||
      (o.has_sub_pages !== false && items.some((i) => i.clickable !== false));
    return { screen_title: title, nav_items: items, has_sub_pages: hasSub };
  }
  return { screen_title: '未知页面', nav_items: [], has_sub_pages: false };
}

export async function queryScreenSnapshot(
  handle: ExploreAgentHandle,
  appName: string,
  machineOut: boolean,
  metrics?: ExploreMetrics,
): Promise<ScreenSnapshot> {
  const prompt = buildSnapshotPrompt(appName);
  try {
    const raw = await logModelCall(
      'aiQuery',
      '界面快照',
      () =>
        withStepTimeout(handle.aiQuery<unknown>(prompt), '界面快照'),
      {
        machineOut,
        metrics,
        promptHint: prompt,
        resultToText: (r) => JSON.stringify(r ?? {}),
      },
    );
    return parseSnapshotRaw(raw, appName);
  } catch {
    return queryScreenSnapshotFallback(handle, appName, machineOut, metrics);
  }
}

async function queryScreenSnapshotFallback(
  handle: ExploreAgentHandle,
  appName: string,
  machineOut: boolean,
  metrics?: ExploreMetrics,
): Promise<ScreenSnapshot> {
  const titlePrompt = 'string, 用简短中文描述当前页面标题或所在位置（不超过20字）';
  let screen_title = '未知页面';
  try {
    const t = await logModelCall(
      'aiQuery',
      '页面标题',
      () => withStepTimeout(handle.aiQuery<string>(titlePrompt), '页面标题'),
      { machineOut, metrics, promptHint: titlePrompt },
    );
    screen_title = String(t ?? '').trim() || screen_title;
  } catch {
    /* ignore */
  }

  const navPrompt =
    `{name: string, region: string, clickable: boolean}[], 仅在「${appName}」列出功能入口；` +
    '含顶部搜索框（region=search_bar）；region 取 top_tab|bottom_tab|side|search_bar|button|tab|list_item|other';
  let nav_items: NavItem[] = [];
  try {
    const raw = await logModelCall(
      'aiQuery',
      '导航菜单',
      () => withStepTimeout(handle.aiQuery<unknown>(navPrompt), '导航菜单'),
      { machineOut, metrics, promptHint: navPrompt },
    );
    nav_items = sortNavItems(normalizeNavItems(raw));
  } catch {
    nav_items = [];
  }

  return {
    screen_title,
    nav_items,
    has_sub_pages: nav_items.length > 0,
  };
}

/** 点击后等待界面稳定（替代固定 1800ms） */
export async function waitAfterTap(
  handle: ExploreAgentHandle,
  appName: string,
  machineOut: boolean,
  opts: { maxMs?: number; pollMs?: number; metrics?: ExploreMetrics } = {},
): Promise<ScreenSnapshot> {
  const maxMs = opts.maxMs ?? 1800;
  const pollMs = opts.pollMs ?? 400;
  const deadline = Date.now() + maxMs;
  let prev = '';
  const metrics = opts.metrics;
  let last = await queryScreenSnapshot(handle, appName, machineOut, metrics);

  while (Date.now() < deadline) {
    await sleep(pollMs);
    const snap = await queryScreenSnapshot(handle, appName, machineOut, metrics);
    const fp = `${snap.screen_title}|${snap.nav_items.length}`;
    if (prev && fp === prev) return snap;
    prev = fp;
    last = snap;
  }
  return last;
}

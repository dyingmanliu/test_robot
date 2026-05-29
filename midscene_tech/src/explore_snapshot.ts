/** 合并界面快照查询与点击后稳定等待 */

import type { ExploreAgentHandle } from './explore_agent.js';
import { logModelCall } from './model_log.js';
import { normalizeNavItems, sortNavItems } from './explore_common.js';
import type { NavItem } from './explore_types.js';
import type { ExploreMetrics } from './explore_metrics.js';
import { withStepTimeout } from './step_timeout.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export const DEFAULT_SCROLL_MAX_PASSES = 5;

export interface ScreenSnapshot {
  screen_title: string;
  nav_items: NavItem[];
  has_sub_pages: boolean;
  /** 是否存在需横向滑动才能看全的入口（图标宫格分页、顶部分类 Tab 截断等） */
  has_horizontal_scroll?: boolean;
  /** 可横向滑动的区域：icon_grid | top_category_tab | bottom_tab | list */
  horizontal_scroll_areas?: string[];
  /** 当前选中的底部 Tab 名称（如 推荐/小团）；主界面 Tab 内控件归属用 */
  active_bottom_tab?: string;
}

export interface SnapshotQueryOptions {
  /** 滑动 Tab/列表以露出首屏不可见的菜单项 */
  scrollRevealMenus?: boolean;
  /** 最多执行几次滑动+重扫（默认 3） */
  scrollMaxPasses?: number;
  emitStep?: (
    phase: 'start' | 'done' | 'error',
    task: string,
    error?: string,
  ) => void;
}

function buildSnapshotPrompt(appName: string): string {
  return (
    `{screen_title: string, nav_items: {name: string, region: string, clickable: boolean}[], has_sub_pages: boolean, has_horizontal_scroll?: boolean, horizontal_scroll_areas?: string[], active_bottom_tab?: string}, ` +
    `仅在「${appName}」应用当前界面扫描（GIIC）：` +
    'screen_title 为简短中文页面标题（不超过20字）；' +
    'nav_items 列出当前可见的全部功能入口：顶部/底部分类 Tab、图标宫格（金刚位）、侧栏、工具栏按钮、搜索框；' +
    'active_bottom_tab 为当前高亮/选中的底部 Tab 名称（如 推荐、小团）；无底部 Tab 可省略；' +
    '若图标宫格下方有横条分页指示点，或顶部分类 Tab 右侧被截断，说明还有隐藏入口；' +
    'has_horizontal_scroll 仅在「横滑后才能看到更多入口」时为 true，并填写 horizontal_scroll_areas；' +
    '以下情况 has_horizontal_scroll 必须为 false：底部 2~5 个固定 Tab（点击切换、不可横滑）；' +
    '首页功能卡片/按钮平铺且无分页圆点；普通垂直列表。' +
    'horizontal_scroll_areas 列出需横滑区域：icon_grid（首页金刚位且有多页分页点）、top_category_tab（顶部分类 Tab 右侧被截断）、bottom_tab（极少数可横滑底栏）、list；' +
    'has_sub_pages 表示除主 Tab 切换外是否还有可进入的子页面/子菜单；' +
    '若不在该应用内返回 nav_items=[]、has_sub_pages=false。' +
    '不要编造；region 取 top_tab|bottom_tab|icon_grid|side|search_bar|button|tab|list_item|other；' +
    '图标宫格单项（如外卖、团购、酒店）region=icon_grid；顶部分类 Tab region=top_tab；' +
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
    const modelAreas = Array.isArray(o.horizontal_scroll_areas)
      ? o.horizontal_scroll_areas
          .map((a) => String(a).trim().toLowerCase())
          .filter(Boolean)
      : [];
    const modelSaysScroll = o.has_horizontal_scroll === true;
    const modelSaysNoScroll = o.has_horizontal_scroll === false;
    const heuristicAreas = modelSaysNoScroll
      ? []
      : inferHorizontalScrollAreasStrong(items);
    const scrollAreas =
      modelAreas.length > 0 ? modelAreas : heuristicAreas;
    const hasHorizontalScroll =
      (modelSaysScroll && scrollAreas.length > 0) ||
      (!modelSaysNoScroll && !modelSaysScroll && heuristicAreas.length > 0);
    const activeBottomTab = String(o.active_bottom_tab ?? o.active_tab ?? '').trim();
    return {
      screen_title: title,
      nav_items: items,
      has_sub_pages: hasSub,
      has_horizontal_scroll: hasHorizontalScroll,
      horizontal_scroll_areas: scrollAreas.length ? scrollAreas : undefined,
      active_bottom_tab: activeBottomTab || undefined,
    };
  }
  return { screen_title: '未知页面', nav_items: [], has_sub_pages: false };
}

/** 强信号启发式：仅在模型未明确否定时作兜底，避免普通首页/固定 Tab 误判 */
function inferHorizontalScrollAreasStrong(items: NavItem[]): string[] {
  const areas = new Set<string>();
  const iconGridCount = items.filter(
    (i) => (i.region || 'other').toLowerCase() === 'icon_grid',
  ).length;

  // 仅统计 region=icon_grid，不把 button/other 当作宫格
  if (iconGridCount >= 8) areas.add('icon_grid');
  if (items.some((i) => /更多服务|全部服务|^更多$/.test(i.name.trim()))) {
    areas.add('icon_grid');
  }

  return [...areas];
}

/** 当前快照是否值得做横滑发现 */
function shouldRevealHiddenMenus(snapshot: ScreenSnapshot): boolean {
  return (
    snapshot.has_horizontal_scroll === true &&
    (snapshot.horizontal_scroll_areas?.length ?? 0) > 0
  );
}

function navItemDedupeKey(item: NavItem): string {
  const region = (item.region || 'other').toLowerCase();
  return `${region}@@${item.name.trim().toLowerCase()}`;
}

function mergeSnapshots(base: ScreenSnapshot, extra: ScreenSnapshot): ScreenSnapshot {
  const merged = new Map<string, NavItem>();
  for (const item of [...base.nav_items, ...extra.nav_items]) {
    merged.set(navItemDedupeKey(item), item);
  }
  const nav_items = sortNavItems([...merged.values()]);
  const has_sub_pages =
    base.has_sub_pages ||
    extra.has_sub_pages ||
    nav_items.some((i) => i.clickable !== false);
  return {
    screen_title: base.screen_title || extra.screen_title,
    nav_items,
    has_sub_pages,
  };
}

function buildScrollRevealTasks(appName: string, snapshot: ScreenSnapshot): string[] {
  const areas = new Set(
    (snapshot.horizontal_scroll_areas || []).map((a) => a.toLowerCase()),
  );
  if (!areas.size) return [];

  const tasks: string[] = [];
  const wantIconGrid = areas.has('icon_grid');
  const wantTopCategory = areas.has('top_category_tab');
  const wantBottomTab = areas.has('bottom_tab');
  const wantList = areas.has('list');

  // 美团式：首页图标宫格横向分页（金刚位）
  if (wantIconGrid) {
    tasks.push(
      `在「${appName}」应用内，在首页图标宫格区域（如外卖、团购等圆形/方形功能图标区，下方可能有横条分页指示点）向左滑动，露出下一页隐藏的功能入口`,
    );
    tasks.push(
      `在「${appName}」应用内，继续在图标宫格区域向左滑动，直到露出所有分页中的功能图标`,
    );
    tasks.push(
      `在「${appName}」应用内，在图标宫格区域向右滑动，回到第一页并确认是否还有左侧隐藏页`,
    );
  }

  // 京东式：顶部分类 Tab 横向滚动
  if (wantTopCategory) {
    tasks.push(
      `在「${appName}」应用内，在顶部横向分类 Tab 栏（如关注/推荐/手机/家电等，右侧可能被截断）向左滑动，露出右侧隐藏的分类 Tab`,
    );
    tasks.push(
      `在「${appName}」应用内，继续在顶部分类 Tab 栏向左滑动，露出更多隐藏分类`,
    );
    tasks.push(
      `在「${appName}」应用内，在顶部分类 Tab 栏向右滑动，露出左侧隐藏的分类 Tab`,
    );
  }

  if (wantBottomTab) {
    tasks.push(
      `在「${appName}」应用内，在底部 Tab 栏上向左滑动，露出右侧尚未显示的功能 Tab`,
    );
    tasks.push(
      `在「${appName}」应用内，在底部 Tab 栏上向右滑动，露出左侧尚未显示的功能 Tab`,
    );
  }

  if (wantList) {
    tasks.push(
      `在「${appName}」应用内，在功能列表或侧栏菜单区域向下滑动一屏，露出下方隐藏的功能入口`,
    );
  }

  return tasks;
}

async function queryScreenSnapshotOnce(
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

async function revealHiddenMenuItems(
  handle: ExploreAgentHandle,
  appName: string,
  machineOut: boolean,
  metrics: ExploreMetrics | undefined,
  base: ScreenSnapshot,
  opts: {
    scrollMaxPasses: number;
    emitStep?: SnapshotQueryOptions['emitStep'];
  },
): Promise<ScreenSnapshot> {
  if (!shouldRevealHiddenMenus(base)) {
    opts.emitStep?.('done', '当前页面无横滑隐藏菜单，跳过滑动发现');
    return base;
  }

  const tasks = buildScrollRevealTasks(appName, base);
  if (tasks.length === 0) {
    return base;
  }

  let merged = base;
  let noProgressStreak = 0;
  const maxPasses = Math.min(Math.max(1, opts.scrollMaxPasses), tasks.length);

  for (let i = 0; i < maxPasses; i += 1) {
    const task = tasks[i];
    try {
      opts.emitStep?.('start', task);
      await logModelCall(
        'aiAct',
        task,
        () => withStepTimeout(handle.aiAct(task), task),
        { machineOut, metrics, promptHint: task },
      );
      metrics?.onTap();
      await sleep(450);
      opts.emitStep?.('done', task);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      opts.emitStep?.('error', task, msg);
      continue;
    }

    const snap = await queryScreenSnapshotOnce(handle, appName, machineOut, metrics);
    const beforeCount = merged.nav_items.length;
    merged = mergeSnapshots(merged, snap);
    if (merged.nav_items.length > beforeCount) {
      noProgressStreak = 0;
    } else {
      noProgressStreak += 1;
      if (noProgressStreak >= 2) {
        break;
      }
    }
  }

  return merged;
}

export async function queryScreenSnapshot(
  handle: ExploreAgentHandle,
  appName: string,
  machineOut: boolean,
  metrics?: ExploreMetrics,
  opts?: SnapshotQueryOptions,
): Promise<ScreenSnapshot> {
  const base = await queryScreenSnapshotOnce(handle, appName, machineOut, metrics);
  if (!opts?.scrollRevealMenus) {
    return base;
  }

  const scrollMaxPasses = opts.scrollMaxPasses ?? DEFAULT_SCROLL_MAX_PASSES;
  return revealHiddenMenuItems(handle, appName, machineOut, metrics, base, {
    scrollMaxPasses,
    emitStep: opts.emitStep,
  });
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
    '含图标宫格(icon_grid)、顶部分类 Tab(top_tab)、搜索框(search_bar)；' +
    'region 取 top_tab|bottom_tab|icon_grid|side|search_bar|button|tab|list_item|other';
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
  let last = await queryScreenSnapshot(handle, appName, machineOut, metrics, {
    scrollRevealMenus: false,
  });

  while (Date.now() < deadline) {
    await sleep(pollMs);
    const snap = await queryScreenSnapshot(handle, appName, machineOut, metrics, {
      scrollRevealMenus: false,
    });
    const fp = `${snap.screen_title}|${snap.nav_items.length}`;
    if (prev && fp === prev) return snap;
    prev = fp;
    last = snap;
  }
  return last;
}

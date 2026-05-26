/** APP 功能遍历 — 共享工具与区域优先级 */

import type { NavItem, TraverseMode } from './explore_types.js';

export const DEFAULT_MAX_SCREENS = 1000;
export const DEFAULT_MAX_DEPTH = 5;
export const DEFAULT_MAX_TAPS = 8;
export const DEFAULT_BFS_MAX_DEPTH = 1;

const NAV_REGIONS = new Set([
  'top_tab',
  'bottom_tab',
  'top',
  'bottom',
  'icon_grid',
  'category_tab',
  'side',
  'left',
  'right',
  'search_bar',
  'search',
  'search_box',
  'button',
  'tab',
  'list_item',
]);

const SEARCH_REGIONS = new Set(['search_bar', 'search', 'search_box', 'search_input']);

/** 搜索框功能点固定展示名（不用占位文案/热搜词） */
export const SEARCH_FEATURE_LABEL = '搜索框';

export const REGION_RANK: Record<string, number> = {
  bottom_tab: 0,
  bottom: 0,
  top_tab: 1,
  top: 1,
  category_tab: 1,
  icon_grid: 2,
  search_bar: 3,
  search: 3,
  search_box: 3,
  side: 4,
  left: 5,
  right: 5,
  button: 6,
  tab: 6,
  list_item: 7,
  other: 8,
};

const TAB_REGIONS = new Set([
  'bottom_tab',
  'bottom',
  'top_tab',
  'top',
  'side',
  'tab',
  'category_tab',
]);

/** hybrid 浅层广度扫描：Tab + 首页图标宫格（美团金刚位等） */
const SHALLOW_BREADTH_REGIONS = new Set([...TAB_REGIONS, 'icon_grid']);

const AUTO_TAP_BLOCKLIST = new Set(
  [
    '关闭',
    '取消',
    '跳过',
    '知道了',
    '以后再说',
    '不再提示',
    '同意',
    '拒绝',
    '允许',
    '返回',
    '×',
    'x',
  ].map((s) => s.toLowerCase()),
);

export function isSearchItem(item: NavItem): boolean {
  const r = (item.region || 'other').toLowerCase();
  if (SEARCH_REGIONS.has(r)) return true;
  const name = item.name.trim();
  if (!name) return false;
  if (name === SEARCH_FEATURE_LABEL) return true;
  if (/搜索框|搜一搜|^搜索$|search\s*box/i.test(name)) return true;
  return false;
}

/** 搜索框统一名称与 region，避免占位/热搜文案进入功能树 */
export function canonicalizeSearchNavItem(item: NavItem): NavItem {
  if (!isSearchItem(item)) return item;
  return {
    ...item,
    name: SEARCH_FEATURE_LABEL,
    region: 'search_bar',
  };
}

function isNavigationItem(item: NavItem): boolean {
  const r = (item.region || 'other').toLowerCase();
  if (r === 'list' || r === 'content' || r === 'row') return false;
  if (NAV_REGIONS.has(r)) return true;
  if (r === 'other' && item.name.length <= 12) return true;
  return false;
}

/** 可记入功能树的功能入口（含搜索框，搜索框不参与自动点击遍历） */
export function isFeatureItem(item: NavItem): boolean {
  return isNavigationItem(item) || isSearchItem(item);
}

const ICON_GRID_CANDIDATE_REGIONS = new Set(['button', 'other', 'list_item', 'tab']);

const PROTECTED_NAV_REGIONS = new Set([
  'bottom_tab',
  'bottom',
  'top_tab',
  'top',
  'category_tab',
  'search_bar',
  'search',
  'search_box',
  'icon_grid',
  'side',
  'left',
  'right',
]);

function normalizeRegionAlias(region: string): string {
  const r = region.trim().toLowerCase();
  if (r === 'category_tab') return 'category_tab';
  if (r === 'grid' || r === 'icon' || r === 'icons') return 'icon_grid';
  return region.trim() || 'other';
}

function isIconGridCandidate(item: NavItem): boolean {
  const r = (item.region || 'other').toLowerCase();
  if (PROTECTED_NAV_REGIONS.has(r)) return false;
  if (ICON_GRID_CANDIDATE_REGIONS.has(r)) return true;
  return r === 'other' && item.name.trim().length > 0 && item.name.trim().length <= 12;
}

/** 首页图标宫格（美团金刚位等）：将密集的 button/other/list_item 提升为 icon_grid */
export function applyIconGridRegionHeuristic(items: NavItem[]): NavItem[] {
  if (!items.length) return items;
  const candidates = items.filter(isIconGridCandidate);
  const hasMoreServices = items.some((i) =>
    /更多服务|全部服务|^更多$/.test(i.name.trim()),
  );
  const shouldApply =
    candidates.length >= 5 || (candidates.length >= 3 && hasMoreServices);
  if (!shouldApply) return items;

  return items.map((item) => {
    if (!isIconGridCandidate(item)) return item;
    return { ...item, region: 'icon_grid' };
  });
}

export function normalizeNavItems(raw: unknown): NavItem[] {
  if (!raw) return [];
  const list = Array.isArray(raw) ? raw : [raw];
  const out: NavItem[] = [];
  for (const item of list) {
    if (typeof item === 'string') {
      const name = item.trim();
      if (name) out.push({ name, clickable: true, region: 'other' });
      continue;
    }
    if (typeof item === 'object' && item !== null) {
      const o = item as Record<string, unknown>;
      const name = String(o.name ?? o.title ?? o.label ?? '').trim();
      if (!name) continue;
      const region = normalizeRegionAlias(
        o.region != null ? String(o.region).trim() : 'other',
      );
      const clickable =
        o.clickable === undefined ? true : Boolean(o.clickable);
      out.push(canonicalizeSearchNavItem({ name, region, clickable }));
    }
  }
  const seen = new Set<string>();
  const filtered = out.filter((n) => {
    const k = n.name.toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return isFeatureItem(n);
  });
  return applyIconGridRegionHeuristic(filtered);
}

export function sortNavItems(items: NavItem[]): NavItem[] {
  return [...items].sort((a, b) => {
    const ra = REGION_RANK[(a.region || 'other').toLowerCase()] ?? 8;
    const rb = REGION_RANK[(b.region || 'other').toLowerCase()] ?? 8;
    if (ra !== rb) return ra - rb;
    return a.name.localeCompare(b.name, 'zh');
  });
}

export function pathKey(path: string[]): string {
  return path.join(' > ') || '(root)';
}

export function tapKey(path: string[], name: string): string {
  return `${pathKey(path)}|${name}`;
}

export function fullPathKey(path: string[], name: string): string {
  const parts = [...path, name].map((s) => s.trim()).filter(Boolean);
  return parts.join(' > ');
}

export function screenFingerprint(screenTitle: string, path: string[]): string {
  return `${pathKey(path)}@@${screenTitle.trim()}`;
}

export function longestCommonPrefix(a: string[], b: string[]): number {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  return i;
}

export function isBottomTabRegion(region?: string): boolean {
  const r = (region || '').toLowerCase();
  return r === 'bottom_tab' || r === 'bottom';
}

export function isTopTabRegion(region?: string): boolean {
  const r = (region || '').toLowerCase();
  return r === 'top_tab' || r === 'top' || r === 'category_tab';
}

/** 小团 / AI 助手页等内容信号 → 归属底部 Tab */
const TAB_CONTENT_SIGNALS: Record<string, RegExp[]> = {
  小团: [/深度思考/, /一键领券/, /找优惠/, /问小团/, /AI小团/],
};

export function inferActiveBottomTab(
  items: NavItem[],
  screenTitle?: string,
  explicit?: string,
): string | undefined {
  const tab = (explicit || '').trim();
  if (tab) return tab;

  const tabs = items
    .filter((i) => isBottomTabRegion(i.region))
    .map((i) => i.name.trim())
    .filter(Boolean);
  if (!tabs.length) return undefined;

  const title = (screenTitle || '').trim();
  for (const t of tabs) {
    if (title && title.includes(t)) return t;
  }

  for (const t of tabs) {
    const patterns = TAB_CONTENT_SIGNALS[t] || [];
    if (patterns.some((re) => items.some((i) => re.test(i.name)))) return t;
  }
  for (const [tabName, patterns] of Object.entries(TAB_CONTENT_SIGNALS)) {
    if (!tabs.includes(tabName)) continue;
    if (patterns.some((re) => items.some((i) => re.test(i.name)))) return tabName;
  }

  const iconGridish = items.filter((i) => {
    const r = (i.region || 'other').toLowerCase();
    return (
      r === 'icon_grid' ||
      r === 'button' ||
      r === 'other' ||
      r === 'list_item'
    );
  }).length;
  if (iconGridish >= 5) {
    return tabs.find((t) => /推荐|首页|home/i.test(t)) || tabs[0];
  }

  return undefined;
}

export interface TabContextSnapshot {
  nav_items: NavItem[];
  screen_title?: string;
  active_bottom_tab?: string;
}

/** 主界面快照：Tab 内控件应挂在当前选中的底部 Tab 下 */
export function listingPathForItem(
  item: NavItem,
  navPath: string[],
  depth: number,
  snapshot: TabContextSnapshot,
): string[] {
  if (navPath.length > 0 || depth > 0) return navPath;
  if (isBottomTabRegion(item.region) || isTopTabRegion(item.region)) {
    return navPath;
  }

  const active = inferActiveBottomTab(
    snapshot.nav_items,
    snapshot.screen_title,
    snapshot.active_bottom_tab,
  );
  if (!active) return navPath;
  return [active];
}

function isBlockedTapName(name: string): boolean {
  const n = name.trim().toLowerCase();
  if (AUTO_TAP_BLOCKLIST.has(n)) return true;
  if (/^关闭|^取消|^跳过/.test(name.trim())) return true;
  return false;
}

export function filterNavItemsForScreen(
  items: NavItem[],
  path: string[],
  depth: number,
): NavItem[] {
  const inPath = new Set(path.map((p) => p.trim().toLowerCase()));
  return items.filter((item) => {
    if (!isFeatureItem(item)) return false;
    const name = item.name.trim();
    if (!name) return false;
    if (isBlockedTapName(name)) return false;
    if (inPath.has(name.toLowerCase())) return false;
    if (depth > 0) {
      const r = (item.region || 'other').toLowerCase();
      if (r === 'bottom_tab' || r === 'bottom' || r === 'top_tab' || r === 'top') {
        return false;
      }
    }
    return true;
  });
}

/** 参与自动点击/队列的入口（排除搜索框，避免误入搜索页） */
export function filterNavItemsForTap(
  items: NavItem[],
  path: string[],
  depth: number,
): NavItem[] {
  return filterNavItemsForScreen(items, path, depth).filter(
    (item) => !isSearchItem(item),
  );
}

export function regionRank(item: NavItem): number {
  return REGION_RANK[(item.region || 'other').toLowerCase()] ?? 8;
}

export function frontierPriority(depth: number, item: NavItem): number {
  return depth * 1000 + regionRank(item) * 10;
}

export function parseTraverseMode(raw?: string): TraverseMode {
  const env = (process.env.EXPLORE_TRAVERSE_MODE || '').trim().toLowerCase();
  const v = (raw || env || 'hybrid').toLowerCase();
  if (v === 'dfs' || v === 'bfs' || v === 'hybrid') return v;
  return 'hybrid';
}

/** 是否将入口加入 frontier（待点击队列） */
export function shouldEnqueueTap(
  mode: TraverseMode,
  screenDepth: number,
  item: NavItem,
  bfsMaxDepth: number,
): boolean {
  if (item.clickable === false) return false;
  if (isSearchItem(item)) return false;
  const r = (item.region || 'other').toLowerCase();

  if (mode === 'bfs') return true;

  if (mode === 'hybrid') {
    if (screenDepth < bfsMaxDepth) {
      return SHALLOW_BREADTH_REGIONS.has(r);
    }
    return !TAB_REGIONS.has(r) || r === 'tab' || r === 'icon_grid';
  }

  return true;
}

/** 推断是否值得继续深入（替代多数 queryHasNextLevel 调用） */
export function inferHasSubPages(
  navItems: NavItem[],
  childPath: string[],
): boolean {
  const filtered = filterNavItemsForScreen(navItems, childPath, childPath.length);
  const clickable = filtered.filter((i) => i.clickable !== false);
  if (clickable.length === 0) return false;
  return clickable.some((i) => {
    const r = (i.region || 'other').toLowerCase();
    return r !== 'bottom_tab' && r !== 'bottom' && r !== 'top_tab' && r !== 'top';
  });
}

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
  search_bar: 2,
  search: 2,
  search_box: 2,
  side: 3,
  left: 4,
  right: 4,
  button: 5,
  tab: 5,
  list_item: 6,
  other: 7,
};

const TAB_REGIONS = new Set(['bottom_tab', 'bottom', 'top_tab', 'top', 'side', 'tab']);

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
      const region = o.region != null ? String(o.region).trim() : 'other';
      const clickable =
        o.clickable === undefined ? true : Boolean(o.clickable);
      out.push(canonicalizeSearchNavItem({ name, region, clickable }));
    }
  }
  const seen = new Set<string>();
  return out.filter((n) => {
    const k = n.name.toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return isFeatureItem(n);
  });
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
      return TAB_REGIONS.has(r);
    }
    return !TAB_REGIONS.has(r) || r === 'tab';
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

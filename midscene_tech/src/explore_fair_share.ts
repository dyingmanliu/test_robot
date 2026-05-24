/** Phase 5：按一级 Tab/分支公平分配界面访问预算 */

import { shouldEnqueueTap } from './explore_common.js';
import type { NavItem, TraverseMode } from './explore_types.js';

export const FAIR_SHARE_OFF = 0;
/** 自动：max_screens / 一级入口数 */
export const FAIR_SHARE_AUTO = -1;

export function rootBranchKey(path: string[]): string {
  return path.length > 0 ? path[0] : '__root__';
}

export function resolveQuotaPerRoot(
  fairSharePerRoot: number,
  maxScreens: number,
  rootTabCount: number,
): number {
  if (fairSharePerRoot === FAIR_SHARE_OFF) {
    return Number.POSITIVE_INFINITY;
  }
  if (fairSharePerRoot === FAIR_SHARE_AUTO) {
    const n = Math.max(1, rootTabCount);
    return Math.max(2, Math.floor(maxScreens / n));
  }
  return Math.max(1, fairSharePerRoot);
}

export function countRootTabs(
  items: NavItem[],
  mode: TraverseMode,
  bfsMaxDepth: number,
): number {
  return items.filter((item) =>
    shouldEnqueueTap(mode, 0, item, bfsMaxDepth),
  ).length;
}

export function createFairShareBudget(
  fairSharePerRoot: number,
  maxScreens: number,
  rootItems: NavItem[],
  mode: TraverseMode,
  bfsMaxDepth: number,
): FairShareBudget | null {
  if (fairSharePerRoot === FAIR_SHARE_OFF) {
    return null;
  }
  const rootTabCount = countRootTabs(rootItems, mode, bfsMaxDepth);
  const quota = resolveQuotaPerRoot(
    fairSharePerRoot,
    maxScreens,
    rootTabCount,
  );
  return new FairShareBudget(quota);
}

export class FairShareBudget {
  private readonly screensByRoot = new Map<string, number>();

  constructor(private readonly quotaPerRoot: number) {}

  get quota(): number {
    return this.quotaPerRoot;
  }

  /** 记录界面前检查（path 为即将记录的界面路径） */
  canRecordScreen(path: string[]): boolean {
    if (!Number.isFinite(this.quotaPerRoot)) return true;
    if (path.length === 0) return true;
    const key = rootBranchKey(path);
    return (this.screensByRoot.get(key) ?? 0) < this.quotaPerRoot;
  }

  onScreenRecorded(path: string[]): void {
    if (path.length === 0) return;
    const key = rootBranchKey(path);
    this.screensByRoot.set(key, (this.screensByRoot.get(key) ?? 0) + 1);
  }

  screensForRoot(path: string[]): number {
    if (path.length === 0) return 0;
    return this.screensByRoot.get(rootBranchKey(path)) ?? 0;
  }
}

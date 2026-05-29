/**
 * 功能遍历引擎：dfs（递归）与 bfs/hybrid（frontier 队列）。
 */

import { scopedTapTask } from './app_scope.js';
import { isOffAppScreenTitle } from './app_scope.js';
import {
  filterNavItemsForScreen,
  filterNavItemsForTap,
  frontierPriority,
  inferHasSubPages,
  listingPathForItem,
  pathKey,
  regionRank,
  screenFingerprint,
  shouldEnqueueTap,
  tapKey,
} from './explore_common.js';
import type { ExploreNavigation } from './explore_nav.js';
import {
  queryScreenSnapshot,
  waitAfterTap,
  type ScreenSnapshot,
  type SnapshotQueryOptions,
} from './explore_snapshot.js';
import type { ExploreAgentHandle } from './explore_agent.js';
import { logModelCall } from './model_log.js';
import {
  createFairShareBudget,
  FairShareBudget,
  FAIR_SHARE_OFF,
} from './explore_fair_share.js';
import type { ExploreMetrics } from './explore_metrics.js';
import type {
  ExploreMachineEvent,
  FeatureEntry,
  NavItem,
  TraverseMode,
} from './explore_types.js';
import { withStepTimeout } from './step_timeout.js';

export interface FrontierNode {
  path: string[];
  item: NavItem;
  depth: number;
  priority: number;
  parentId?: string;
}

export interface TraverseEngineCtx {
  appName: string;
  traverseMode: TraverseMode;
  bfsMaxDepth: number;
  maxScreens: number;
  maxDepth: number;
  maxTaps: number;
  fairSharePerRoot: number;
  metrics: ExploreMetrics;
  fairShareState: { budget: FairShareBudget | null };
  handle: ExploreAgentHandle;
  machineOut: boolean;
  targetBundle: () => string;
  navigation: ExploreNavigation;
  shouldCancel?: () => boolean;
  emit: (ev: ExploreMachineEvent) => void;
  emitStep: (
    phase: 'start' | 'done' | 'error',
    task: string,
    error?: string,
  ) => void;
  ensureInTargetApp: (
    context: string,
    opts?: { relaunch?: boolean },
  ) => Promise<boolean>;
  tryNavigateBack: (context?: string) => Promise<void>;
  scopeOffAppStreak: { value: number };
  tappedKeys: Set<string>;
  visitedScreens: Set<string>;
  screensVisited: { value: number };
  upsertFeature: (
    item: NavItem,
    path: string[],
    depth: number,
    screenTitle: string,
    status: FeatureEntry['status'],
    parentId?: string,
  ) => FeatureEntry;
  recordScreen: (
    path: string[],
    depth: number,
    snapshot: ScreenSnapshot,
  ) => Promise<boolean>;
  emitQueue: (pending: number) => void;
  snapshotQueryOpts: SnapshotQueryOptions;
}

function emitQueueEvent(ctx: TraverseEngineCtx, frontier: FrontierNode[]): void {
  const next = frontier[0];
  ctx.emit({
    kind: 'explore_queue',
    pending: frontier.length,
    mode: ctx.traverseMode,
    next: next ? [...next.path, next.item.name].join(' > ') : undefined,
  });
  ctx.emit(
    ctx.metrics.asEvent(
      ctx.traverseMode,
      ctx.screensVisited.value,
      frontier.length,
    ),
  );
}

function sortFrontier(frontier: FrontierNode[]): void {
  frontier.sort((a, b) => {
    if (a.priority !== b.priority) return a.priority - b.priority;
    return a.item.name.localeCompare(b.item.name, 'zh');
  });
}

function enqueueTap(
  frontier: FrontierNode[],
  path: string[],
  item: NavItem,
  depth: number,
  parentId: string | undefined,
  ctx: TraverseEngineCtx,
): void {
  const tKey = tapKey(path, item.name);
  if (ctx.tappedKeys.has(tKey)) return;
  if (!shouldEnqueueTap(ctx.traverseMode, path.length, item, ctx.bfsMaxDepth)) {
    return;
  }
  frontier.push({
    path: [...path],
    item,
    depth,
    priority: frontierPriority(depth, item),
    parentId,
  });
}

async function tapNavItem(
  ctx: TraverseEngineCtx,
  path: string[],
  item: NavItem,
): Promise<boolean> {
  const tapTask = scopedTapTask(item.name, ctx.appName, ctx.targetBundle());
  ctx.emitStep('start', tapTask);
  try {
    await logModelCall(
      'aiAct',
      tapTask,
      () => withStepTimeout(ctx.handle.aiAct(tapTask), tapTask),
      { machineOut: ctx.machineOut, metrics: ctx.metrics, promptHint: tapTask },
    );
    ctx.metrics.onTap();
    await waitAfterTap(ctx.handle, ctx.appName, ctx.machineOut, {
      metrics: ctx.metrics,
    });
    ctx.emitStep('done', tapTask);
    ctx.tappedKeys.add(tapKey(path, item.name));
    return true;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    ctx.emitStep('error', tapTask, msg);
    await ctx.tryNavigateBack(`点击「${item.name}」失败后恢复`);
    return false;
  }
}

function scheduleChildrenOnFrontier(
  frontier: FrontierNode[],
  parentPath: string[],
  parentDepth: number,
  items: NavItem[],
  parentId: string | undefined,
  ctx: TraverseEngineCtx,
): void {
  const clickable = filterNavItemsForTap(items, parentPath, parentDepth)
    .filter((i) => i.clickable !== false)
    .sort((a, b) => regionRank(a) - regionRank(b));

  const limit =
    ctx.traverseMode === 'dfs' ? ctx.maxTaps : ctx.maxTaps * 2;
  for (const item of clickable.slice(0, limit)) {
    enqueueTap(frontier, parentPath, item, parentDepth + 1, parentId, ctx);
  }
}

/** bfs / hybrid：frontier 主循环 */
export async function runFrontierTraverse(
  ctx: TraverseEngineCtx,
): Promise<void> {
  const frontier: FrontierNode[] = [];

  const rootSnap = await queryScreenSnapshot(
    ctx.handle,
    ctx.appName,
    ctx.machineOut,
    ctx.metrics,
    ctx.snapshotQueryOpts,
  );
  const rootOk = await ctx.recordScreen([], 0, rootSnap);
  if (!rootOk) return;

  const rootItems = filterNavItemsForScreen(rootSnap.nav_items, [], 0);
  ctx.fairShareState.budget = createFairShareBudget(
    ctx.fairSharePerRoot,
    ctx.maxScreens,
    filterNavItemsForTap(rootSnap.nav_items, [], 0),
    ctx.traverseMode,
    ctx.bfsMaxDepth,
  );
  if (ctx.fairShareState.budget) {
    ctx.emitStep(
      'done',
      `公平预算：每级入口约 ${ctx.fairShareState.budget.quota} 屏`,
    );
  }
  for (const item of rootItems) {
    if (ctx.shouldCancel?.()) throw new Error('探索已取消');
    const listPath = listingPathForItem(item, [], 0, rootSnap);
    ctx.upsertFeature(
      item,
      listPath,
      listPath.length,
      rootSnap.screen_title,
      'listed',
    );
  }
  scheduleChildrenOnFrontier(frontier, [], 0, rootItems, undefined, ctx);
  ctx.navigation.setPath([]);
  emitQueueEvent(ctx, frontier);

  while (frontier.length > 0) {
    if (ctx.shouldCancel?.()) throw new Error('探索已取消');
    if (ctx.screensVisited.value >= ctx.maxScreens) break;

    sortFrontier(frontier);
    const node = frontier.shift()!;
    emitQueueEvent(ctx, frontier);

    if (node.depth > ctx.maxDepth) continue;

    const tKey = tapKey(node.path, node.item.name);
    if (ctx.tappedKeys.has(tKey)) continue;

    const childPathPreview = [...node.path, node.item.name];
    if (
      ctx.fairShareState.budget &&
      !ctx.fairShareState.budget.canRecordScreen(childPathPreview)
    ) {
      ctx.emitStep(
        'done',
        `「${node.item.name}」分支已达界面预算，跳过`,
      );
      continue;
    }

    if (!(await ctx.navigation.navigateTo(node.path))) {
      ctx.emitStep('error', '导航失败', pathKey(node.path));
      continue;
    }

    if (!(await ctx.ensureInTargetApp(`队列·深度 ${node.depth}`))) {
      continue;
    }

    const parentEntry = ctx.upsertFeature(
      node.item,
      node.path,
      node.path.length,
      '',
      'visited',
      node.parentId,
    );

    const ok = await tapNavItem(ctx, node.path, node.item);
    if (!ok) continue;

    const childPath = [...node.path, node.item.name];
    ctx.navigation.afterTap(childPath);

    if (!(await ctx.ensureInTargetApp(`点击「${node.item.name}」后`))) {
      await ctx.tryNavigateBack(`离站恢复·${node.item.name}`);
      continue;
    }

    const snap = await queryScreenSnapshot(
      ctx.handle,
      ctx.appName,
      ctx.machineOut,
      ctx.metrics,
      { scrollRevealMenus: false },
    );
    if (isOffAppScreenTitle(snap.screen_title)) {
      ctx.emitStep('error', '点击后进入站外', snap.screen_title);
      await ctx.tryNavigateBack(`站外恢复·${node.item.name}`);
      continue;
    }

    const afterFp = screenFingerprint(snap.screen_title, childPath);
    if (afterFp === screenFingerprint(snap.screen_title, node.path)) {
      ctx.emitStep('done', `「${node.item.name}」无下级页面，跳过深入`);
      continue;
    }

    const hasChild =
      snap.has_sub_pages ||
      inferHasSubPages(snap.nav_items, childPath);
    if (!hasChild) {
      ctx.emitStep('done', `「${node.item.name}」无子菜单，停止下级遍历`);
      await ctx.tryNavigateBack(`「${node.item.name}」无子菜单`);
      continue;
    }

    const childOk = await ctx.recordScreen(childPath, node.depth, snap);
    if (!childOk) {
      await ctx.tryNavigateBack(`已访问·${node.item.name}`);
      continue;
    }

    const childItems = filterNavItemsForScreen(
      snap.nav_items,
      childPath,
      node.depth,
    );
    for (const item of childItems) {
      if (ctx.shouldCancel?.()) throw new Error('探索已取消');
      ctx.upsertFeature(
        item,
        childPath,
        node.depth,
        snap.screen_title,
        'listed',
        parentEntry.id,
      );
    }
    scheduleChildrenOnFrontier(
      frontier,
      childPath,
      node.depth,
      childItems,
      parentEntry.id,
      ctx,
    );
  }
}

/** dfs：由 explore.ts 内 exploreScreen 递归入口调用 */
export async function runDfsTraverse(
  exploreScreen: (path: string[], depth: number, parentId?: string) => Promise<void>,
): Promise<void> {
  await exploreScreen([], 0);
}

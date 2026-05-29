/**
 * 通过 Midscene + HDC 遍历鸿蒙 APP，采集功能菜单树。
 */

import { assertMidsceneModelEnv, loadAgentConfig } from './config.js';
import { parseDevicePlatform } from './platform.js';
import { createExploreAgent, type ExploreAgentHandle } from './explore_agent.js';
import type {
  ExploreMachineEvent,
  ExploreOptions,
  ExploreRunOutcome,
  ExploreTreeResult,
  FeatureEntry,
  NavItem,
  ScreenRecord,
  TraverseMode,
} from './explore_types.js';
import {
  DEFAULT_MAX_DEPTH,
  DEFAULT_MAX_SCREENS,
  DEFAULT_MAX_TAPS,
  DEFAULT_BFS_MAX_DEPTH,
  canonicalizeSearchNavItem,
  filterNavItemsForScreen,
  filterNavItemsForTap,
  inferHasSubPages,
  listingPathForItem,
  parseTraverseMode,
  regionRank,
  screenFingerprint,
  tapKey,
} from './explore_common.js';
import { ExploreNavigation } from './explore_nav.js';
import {
  queryScreenSnapshot,
  waitAfterTap,
  type ScreenSnapshot,
  type SnapshotQueryOptions,
} from './explore_snapshot.js';
import {
  runDfsTraverse,
  runFrontierTraverse,
  type TraverseEngineCtx,
} from './explore_traverse.js';
import {
  attachTreesToResult,
  enrichFeatureGiicFields,
} from './feature_tree_build.js';
import { logModelCall } from './model_log.js';
import { launchAppByBundleId, launchAppByName } from './resolve_app_launch.js';
import {
  buildExploreActionContext,
  bundleMatches,
  harmonyPressBack,
  isOffAppScreenTitle,
  readForegroundBundle,
  scopedBackTask,
  scopedTapTask,
} from './app_scope.js';
import { withStepTimeout } from './step_timeout.js';
import { ExploreMetrics } from './explore_metrics.js';
import {
  createFairShareBudget,
  type FairShareBudget,
  FAIR_SHARE_OFF,
} from './explore_fair_share.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function parseScrollRevealMenus(value?: boolean): boolean {
  if (value !== undefined) return value;
  const env = (process.env.EXPLORE_SCROLL_REVEAL_MENUS || '').trim().toLowerCase();
  if (env === '0' || env === 'false' || env === 'no') return false;
  return true;
}

function parseScrollMaxPasses(value?: number): number {
  if (value !== undefined && value > 0) {
    return Math.min(Math.floor(value), 6);
  }
  const env = Number(process.env.EXPLORE_SCROLL_MAX_PASSES);
  if (Number.isFinite(env) && env > 0) {
    return Math.min(Math.floor(env), 6);
  }
  return 5;
}

function fullPathKey(path: string[], name: string): string {
  const parts = [...path, name].map((s) => s.trim()).filter(Boolean);
  return parts.join(' > ');
}

export async function runAppFeatureExplore(
  options: ExploreOptions,
): Promise<ExploreRunOutcome> {
  const appName = options.appName?.trim();
  if (!appName) {
    return failOutcome('未提供 APP 名称', options);
  }

  assertMidsceneModelEnv();
  const bundleIdOptEarly = options.bundleId?.trim() || '';
  const explorePlatform = parseDevicePlatform(options.devicePlatform);
  const scopeContext =
    options.aiActionContext ??
    buildExploreActionContext(
      appName,
      bundleIdOptEarly,
      explorePlatform,
    );
  const cfg = loadAgentConfig({
    deviceId: options.deviceId,
    hdcHome: options.hdcHome,
    devicePlatform: explorePlatform,
    aiActionContext: scopeContext,
  });

  const maxScreens = options.maxScreens ?? DEFAULT_MAX_SCREENS;
  const maxDepth = options.maxDepth ?? DEFAULT_MAX_DEPTH;
  const maxTaps = options.maxTapsPerScreen ?? DEFAULT_MAX_TAPS;
  const traverseMode: TraverseMode = parseTraverseMode(options.traverseMode);
  const bfsMaxDepth = options.bfsMaxDepth ?? DEFAULT_BFS_MAX_DEPTH;
  const fairSharePerRoot = options.fairSharePerRoot ?? FAIR_SHARE_OFF;
  const scrollRevealMenus = parseScrollRevealMenus(options.scrollRevealMenus);
  const scrollMaxPasses = parseScrollMaxPasses(options.scrollMaxPasses);
  const metrics = new ExploreMetrics();
  const fairShareState: { budget: FairShareBudget | null } = { budget: null };
  let resolvedBundleId = '';

  const startedAt = new Date().toISOString();
  const features: FeatureEntry[] = [];
  const featureByKey = new Map<string, FeatureEntry>();
  const tappedKeys = new Set<string>();
  const visitedScreens = new Set<string>();
  const screens: ScreenRecord[] = [];
  let screensVisited = 0;
  let screenSeq = 0;
  let featureSeq = 0;
  let stepSeq = 0;
  let currentScreenId: string | undefined;

  const emit = (ev: ExploreMachineEvent) => options.onEvent?.(ev);

  const emitStep = (
    phase: 'start' | 'done' | 'error',
    task: string,
    error?: string,
  ) => {
    stepSeq += 1;
    emit({ kind: 'step', step: stepSeq, phase, task, error });
  };

  const snapshotQueryOpts: SnapshotQueryOptions = {
    scrollRevealMenus,
    scrollMaxPasses,
    emitStep,
  };

  const upsertFeature = (
    item: NavItem,
    path: string[],
    depth: number,
    screenTitle: string,
    status: FeatureEntry['status'],
    parentId?: string,
  ): FeatureEntry => {
    const nav = canonicalizeSearchNavItem(item);
    const key = fullPathKey(path, nav.name);
    const existing = featureByKey.get(key);
    if (existing) {
      if (status === 'visited') {
        existing.status = 'visited';
        existing.screen_title = screenTitle;
      }
      return existing;
    }
    featureSeq += 1;
    const entry: FeatureEntry = {
      id: String(featureSeq),
      name: nav.name,
      path: [...path, nav.name],
      depth: path.length + 1,
      region: nav.region,
      screen_title: screenTitle,
      status,
      parent_id: parentId,
    };
    if (currentScreenId) entry.screen_id = currentScreenId;
    const enriched = enrichFeatureGiicFields(entry);
    featureByKey.set(key, enriched);
    features.push(enriched);
    const scr = screens.find((s) => s.id === currentScreenId);
    if (scr && !scr.feature_ids.includes(enriched.id)) {
      scr.feature_ids.push(enriched.id);
    }
    emit({ kind: 'explore_feature', feature: enriched });
    return enriched;
  };

  let handle: ExploreAgentHandle | undefined;

  try {
    handle = await createExploreAgent(cfg, options.devicePlatform);
    const machineOut = Boolean(options.machineOut);

    const bundleIdOpt = options.bundleId?.trim();
    emitStep('start', `启动应用 ${bundleIdOpt || `「${appName}」`}`);
    if (handle.platform === 'harmonyos' && handle.harmonyAgent && handle.harmonyDevice) {
      if (bundleIdOpt) {
        const launchInfo = await launchAppByBundleId(bundleIdOpt, cfg.hdcHome);
        resolvedBundleId = launchInfo.bundle_id;
        emitStep('done', `启动 APP ID ${launchInfo.launch_uri}`);
      } else {
        const launchInfo = await launchAppByName(
          handle.harmonyAgent,
          handle.harmonyDevice,
          appName,
          { hdcHome: cfg.hdcHome, machineOut },
        );
        resolvedBundleId = launchInfo.bundle_id;
        emitStep('done', `启动应用「${appName}」(${launchInfo.launch_uri})`);
      }
    } else {
      const pkg = bundleIdOpt || appName;
      const launchTask = bundleIdOpt
        ? `打开已安装的应用，应用包名为 ${bundleIdOpt}`
        : `打开应用「${appName}」`;
      await logModelCall(
        'aiAct',
        launchTask,
        () => withStepTimeout(handle!.aiAct(launchTask), launchTask),
        { machineOut, metrics, promptHint: launchTask },
      );
      resolvedBundleId = pkg;
      emitStep('done', launchTask);
    }
    await sleep(2500);

    const targetBundle = () =>
      (resolvedBundleId || bundleIdOpt || '').trim();

    const scopeOffAppStreakRef = { value: 0 };

    async function relaunchTargetApp(reason: string): Promise<void> {
      const bundle = targetBundle();
      emitStep('start', `拉回被测应用：${reason}`);
      try {
        if (
          handle!.platform === 'harmonyos' &&
          handle!.harmonyAgent &&
          handle!.harmonyDevice &&
          bundle
        ) {
          const launchInfo = await launchAppByBundleId(bundle, cfg.hdcHome);
          resolvedBundleId = launchInfo.bundle_id;
        } else if (bundle) {
          const launchTask = `打开已安装的应用，应用包名为 ${bundle}，不要打开其他应用`;
          await logModelCall(
            'aiAct',
            launchTask,
            () => withStepTimeout(handle!.aiAct(launchTask), launchTask),
            { machineOut, metrics, promptHint: launchTask },
          );
        } else {
          const launchTask = `打开应用「${appName}」，不要打开其他应用`;
          await logModelCall(
            'aiAct',
            launchTask,
            () => withStepTimeout(handle!.aiAct(launchTask), launchTask),
            { machineOut, metrics, promptHint: launchTask },
          );
        }
        await sleep(2200);
        emitStep('done', '已重新拉起被测应用');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        emitStep('error', '拉回被测应用失败', msg);
      }
    }

    async function readForeground(): Promise<string | null> {
      return readForegroundBundle(
        handle!.platform,
        cfg.hdcHome,
        cfg.deviceId,
      );
    }

    async function visionSaysInTargetApp(): Promise<boolean | null> {
      const target = targetBundle();
      if (!target) return null;
      const prompt =
        `boolean, 当前屏幕是否属于被测应用「${appName}」（包名 ${target}）的主流程界面，` +
        '而不是华为钱包、华为商城、应用市场、系统桌面、浏览器或其他无关 App';
      try {
        return await logModelCall(
          'aiQuery',
          '是否在目标应用',
          () =>
            withStepTimeout(handle!.aiQuery<boolean>(prompt), '是否在目标应用'),
          { machineOut, metrics, promptHint: prompt },
        );
      } catch {
        return null;
      }
    }

    async function ensureInTargetApp(
      context: string,
      opts: { relaunch?: boolean } = {},
    ): Promise<boolean> {
      const target = targetBundle();
      if (!target) return true;

      const relaunch = opts.relaunch !== false;
      let foreground = await readForeground();

      const offByBundle =
        foreground != null && !bundleMatches(foreground, target);

      // shell 已确认在目标应用内，直接信任，不再额外调用视觉验证
      if (!offByBundle) {
        scopeOffAppStreakRef.value = 0;
        emit({
          kind: 'explore_scope',
          in_target: true,
          foreground_bundle: foreground || undefined,
          target_bundle: target,
          message: `[shell] ${context}`,
        });
        return true;
      }

      // shell 显示不在目标应用，再用视觉验证作为辅助判断
      const vision = await visionSaysInTargetApp();
      const offByVision = vision === false;

      if (!offByVision) {
        scopeOffAppStreakRef.value = 0;
        emit({
          kind: 'explore_scope',
          in_target: true,
          foreground_bundle: foreground || undefined,
          target_bundle: target,
          message: `视觉确认在目标应用内（${context}）`,
        });
        return true;
      }

      scopeOffAppStreakRef.value += 1;
      const msg = `前台 ${foreground} ≠ 目标 ${target}（${context}）`;
      emit({
        kind: 'explore_scope',
        in_target: false,
        foreground_bundle: foreground || undefined,
        target_bundle: target,
        message: msg,
      });
      emitStep('error', '已离开被测应用', msg);

      if (!relaunch) return false;

      for (let attempt = 0; attempt < 2; attempt += 1) {
        await relaunchTargetApp(msg);
        await sleep(1500);
        foreground = await readForeground();
        if (foreground && bundleMatches(foreground, target)) {
          scopeOffAppStreakRef.value = 0;
          emit({
            kind: 'explore_scope',
            in_target: true,
            foreground_bundle: foreground,
            target_bundle: target,
            message: `已拉回被测应用（${context}）`,
          });
          return true;
        }
        const vision = await visionSaysInTargetApp();
        if (vision === true) {
          scopeOffAppStreakRef.value = 0;
          emit({
            kind: 'explore_scope',
            in_target: true,
            target_bundle: target,
            message: `视觉确认已回到「${appName}」（${context}）`,
          });
          return true;
        }
      }
      return false;
    }

    async function tryNavigateBack(context?: string): Promise<void> {
      metrics.onBack();
      const suffix = context ? `（${context}）` : '';
      if (handle!.platform === 'harmonyos') {
        for (let i = 0; i < 2; i += 1) {
          emitStep('start', `系统返回键${suffix}`);
          try {
            await harmonyPressBack(cfg.hdcHome, cfg.deviceId);
            await sleep(900);
            emitStep('done', '系统返回键');
            if (await ensureInTargetApp(`返回后${suffix}`, { relaunch: false })) {
              return;
            }
          } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            emitStep('error', '系统返回键', msg);
          }
        }
      }
      const bundle = targetBundle();
      const task = scopedBackTask(appName, bundle);
      emitStep('start', `${task}${suffix}`);
      try {
        await logModelCall(
          'aiAct',
          task,
          () => withStepTimeout(handle!.aiAct(task), task),
          { machineOut, metrics, promptHint: task },
        );
        emitStep('done', task);
        await sleep(1000);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        emitStep('error', task, msg);
      }
      await ensureInTargetApp(`应用内返回${suffix}`);
    }

    if (!(await ensureInTargetApp('启动应用后'))) {
      throw new Error('设备未进入被测应用，已中止探索');
    }

    const dismissTask =
      `仅在「${appName}」内：若出现本应用权限/协议弹窗，处理至主界面；` +
      '不要点击会打开华为钱包、华为商城或其他应用的按钮';
    emitStep('start', dismissTask);
    try {
      if (await ensureInTargetApp('处理弹窗前', { relaunch: false })) {
        await logModelCall(
          'aiAct',
          dismissTask,
          () => withStepTimeout(handle!.aiAct(dismissTask), dismissTask),
          { machineOut, metrics, promptHint: dismissTask },
        );
      }
    } catch {
      /* 无弹窗时忽略 */
    }
    emitStep('done', dismissTask);
    await ensureInTargetApp('处理弹窗后');

    const navigation = new ExploreNavigation({
      handle: handle!,
      appName,
      targetBundle,
      machineOut,
      metrics,
      emitStep,
      tryNavigateBack,
      ensureInTargetApp,
      tappedKeys,
    });

    const screensVisitedRef = { value: screensVisited };

    async function recordScreen(
      path: string[],
      depth: number,
      snapshot: ScreenSnapshot,
    ): Promise<boolean> {
      metrics.beginScreen();
      try {
      if (options.shouldCancel?.()) {
        throw new Error('探索已取消');
      }
      if (screensVisitedRef.value >= maxScreens || depth > maxDepth) {
        return false;
      }
      if (
        fairShareState.budget &&
        !fairShareState.budget.canRecordScreen(path)
      ) {
        const branch = path[0] || '分支';
        emitStep('done', `「${branch}」已达公平界面预算，跳过`);
        return false;
      }

      const screenTitle = snapshot.screen_title;
      if (isOffAppScreenTitle(screenTitle)) {
        emitStep('error', '界面疑似站外', screenTitle);
        await ensureInTargetApp(`站外界面：${screenTitle}`);
        return false;
      }
      if (scopeOffAppStreakRef.value >= 3) {
        emitStep('error', '连续离站', '多次无法回到被测应用，停止本分支遍历');
        return false;
      }

      const fp = screenFingerprint(screenTitle, path);
      if (visitedScreens.has(fp)) {
        return false;
      }
      visitedScreens.add(fp);
      screensVisitedRef.value += 1;
      screensVisited = screensVisitedRef.value;
      screenSeq += 1;
      const screenId = `screen-${screenSeq}`;
      const screenRec: ScreenRecord = {
        id: screenId,
        screen_title: screenTitle,
        path: [...path],
        depth,
        visit_order: screenSeq,
        feature_ids: [],
      };
      screens.push(screenRec);
      currentScreenId = screenId;

      const fgAtPage = await readForeground();
      const inTargetAtPage = await ensureInTargetApp(
        `记录界面：${screenTitle}`,
        { relaunch: false },
      );

      emit({
        kind: 'explore_page',
        screen_title: screenTitle,
        depth,
        path: [...path],
        screen_id: screenId,
        in_target: inTargetAtPage,
        foreground_bundle: fgAtPage || undefined,
        target_bundle: targetBundle() || undefined,
      });

      if (!inTargetAtPage) {
        await ensureInTargetApp(`离站界面 ${screenTitle}`);
        return false;
      }
      fairShareState.budget?.onScreenRecorded(path);
      return true;
      } finally {
        metrics.endScreen();
      }
    }

    async function exploreScreen(
      path: string[],
      depth: number,
      parentId?: string,
    ): Promise<void> {
      if (options.shouldCancel?.()) {
        throw new Error('探索已取消');
      }
      if (screensVisitedRef.value >= maxScreens || depth > maxDepth) {
        return;
      }

      if (!(await ensureInTargetApp(`深度 ${depth} 进入页面前`))) {
        return;
      }

      const snapshot = await queryScreenSnapshot(
        handle!,
        appName,
        machineOut,
        metrics,
        depth === 0
          ? snapshotQueryOpts
          : { ...snapshotQueryOpts, scrollRevealMenus: false },
      );
      const recorded = await recordScreen(path, depth, snapshot);
      if (!recorded) return;

      const screenTitle = snapshot.screen_title;
      const fp = screenFingerprint(screenTitle, path);
      const items = filterNavItemsForScreen(snapshot.nav_items, path, depth);

      if (
        depth === 0 &&
        fairSharePerRoot !== FAIR_SHARE_OFF &&
        !fairShareState.budget
      ) {
        fairShareState.budget = createFairShareBudget(
          fairSharePerRoot,
          maxScreens,
          filterNavItemsForTap(snapshot.nav_items, path, depth),
          traverseMode,
          bfsMaxDepth,
        );
        if (fairShareState.budget) {
          emitStep(
            'done',
            `公平预算：每级入口约 ${fairShareState.budget.quota} 屏`,
          );
        }
      }

      for (const item of items) {
        if (options.shouldCancel?.()) throw new Error('探索已取消');
        const listPath = listingPathForItem(item, path, depth, snapshot);
        upsertFeature(
          item,
          listPath,
          listPath.length,
          screenTitle,
          'listed',
          parentId,
        );
      }

      const clickable = filterNavItemsForTap(snapshot.nav_items, path, depth).filter(
        (i) => i.clickable !== false,
      );
      const dfsOrder = [...clickable].sort(
        (a, b) => regionRank(a) - regionRank(b) || a.name.localeCompare(b.name, 'zh'),
      );
      const toVisit = dfsOrder.slice(0, maxTaps);

      for (const item of toVisit) {
        if (options.shouldCancel?.()) throw new Error('探索已取消');
        if (screensVisitedRef.value >= maxScreens || depth >= maxDepth) break;

        const tKey = tapKey(path, item.name);
        if (tappedKeys.has(tKey)) continue;
        tappedKeys.add(tKey);

        const parentEntry = upsertFeature(
          item,
          path,
          depth,
          screenTitle,
          'visited',
          parentId,
        );
        const childPath = [...path, item.name];
        if (
          fairShareState.budget &&
          !fairShareState.budget.canRecordScreen(childPath)
        ) {
          emitStep('done', `「${item.name}」分支已达界面预算，跳过`);
          continue;
        }
        const tapTask = scopedTapTask(item.name, appName, targetBundle());
        emitStep('start', tapTask);
        try {
          await logModelCall(
            'aiAct',
            tapTask,
            () => withStepTimeout(handle!.aiAct(tapTask), tapTask),
            { machineOut, metrics, promptHint: tapTask },
          );
          metrics.onTap();
          await waitAfterTap(handle!, appName, machineOut, { metrics });
          emitStep('done', tapTask);
          tappedKeys.add(tapKey(path, item.name));
          navigation.afterTap(childPath);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          emitStep('error', tapTask, msg);
          await tryNavigateBack(`点击「${item.name}」失败后恢复`);
          continue;
        }

        if (!(await ensureInTargetApp(`点击「${item.name}」后`))) {
          await tryNavigateBack(`离站恢复·${item.name}`);
          continue;
        }

        const afterSnap = await queryScreenSnapshot(
          handle!,
          appName,
          machineOut,
          metrics,
          { scrollRevealMenus: false },
        );
        if (isOffAppScreenTitle(afterSnap.screen_title)) {
          emitStep('error', '点击后进入站外', afterSnap.screen_title);
          await ensureInTargetApp(`点击「${item.name}」后站外`);
          await tryNavigateBack(`站外恢复·${item.name}`);
          continue;
        }
        const afterFp = screenFingerprint(afterSnap.screen_title, childPath);
        if (
          afterFp === fp ||
          afterFp === screenFingerprint(afterSnap.screen_title, path)
        ) {
          emitStep('done', `「${item.name}」无下级页面，跳过深入`);
          await tryNavigateBack(`「${item.name}」无下级`);
          continue;
        }

        const hasChild =
          afterSnap.has_sub_pages ||
          inferHasSubPages(afterSnap.nav_items, childPath);
        if (!hasChild) {
          emitStep('done', `「${item.name}」无子菜单，停止下级遍历`);
          await tryNavigateBack(`「${item.name}」无子菜单`);
          continue;
        }

        try {
          await exploreScreen(childPath, depth + 1, parentEntry.id);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          emitStep('error', `子页面 ${childPath.join(' > ')}`, msg);
        } finally {
          await tryNavigateBack(`退出「${item.name}」`);
        }
      }
    }

    const traverseCtx: TraverseEngineCtx = {
      appName,
      traverseMode,
      bfsMaxDepth,
      maxScreens,
      maxDepth,
      maxTaps,
      fairSharePerRoot,
      metrics,
      fairShareState,
      handle: handle!,
      machineOut,
      targetBundle,
      navigation,
      shouldCancel: options.shouldCancel,
      emit,
      emitStep,
      ensureInTargetApp,
      tryNavigateBack,
      scopeOffAppStreak: scopeOffAppStreakRef,
      tappedKeys,
      visitedScreens,
      screensVisited: screensVisitedRef,
      upsertFeature,
      recordScreen,
      emitQueue: (pending) => {
        emit({
          kind: 'explore_queue',
          pending,
          mode: traverseMode,
        });
      },
      snapshotQueryOpts,
    };

    if (traverseMode === 'dfs') {
      await runDfsTraverse(exploreScreen);
    } else {
      await runFrontierTraverse(traverseCtx);
    }

    screensVisited = screensVisitedRef.value;
    emit(metrics.asEvent(traverseMode, screensVisited));

    const modeLabel =
      traverseMode === 'hybrid'
        ? '混合遍历'
        : traverseMode === 'bfs'
          ? '广度优先'
          : '深度优先';
    const attached = attachTreesToResult(appName, features, screens);
    const tree: ExploreTreeResult = {
      app_name: appName,
      bundle_id: resolvedBundleId,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      features: attached.features,
      function_tree: attached.function_tree,
      function_tree_by_path: attached.function_tree_by_path,
      screens: attached.screens,
      screens_visited: screensVisited,
    };

    const reportFile =
      typeof handle.reportFile === 'string' ? handle.reportFile : undefined;

    return {
      ok: true,
      message: `${modeLabel}完成，共发现 ${features.length} 项功能（访问 ${screensVisited} 个页面）`,
      tree,
      reportFile,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    const attached = attachTreesToResult(appName, features, screens);
    const tree: ExploreTreeResult = {
      app_name: appName,
      bundle_id: resolvedBundleId,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      features: attached.features,
      function_tree: attached.function_tree,
      function_tree_by_path: attached.function_tree_by_path,
      screens: attached.screens,
      screens_visited: screensVisited,
    };
    const partial =
      features.length > 0 ? `（已采集 ${features.length} 项）` : '';
    return {
      ok: false,
      message: `${message}${partial}`,
      tree,
      reportFile:
        handle && typeof handle.reportFile === 'string'
          ? handle.reportFile
          : undefined,
    };
  }
}

function failOutcome(message: string, options: ExploreOptions): ExploreRunOutcome {
  const attached = attachTreesToResult(options.appName || '', [], []);
  return {
    ok: false,
    message,
    tree: {
      app_name: options.appName || '',
      bundle_id: '',
      started_at: new Date().toISOString(),
      features: [],
      function_tree: attached.function_tree,
      function_tree_by_path: attached.function_tree_by_path,
      screens: [],
      screens_visited: 0,
    },
  };
}

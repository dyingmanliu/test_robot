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
} from './explore_types.js';
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

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

const DEFAULT_MAX_SCREENS = 30;
const DEFAULT_MAX_DEPTH = 4;
const DEFAULT_MAX_TAPS = 8;

/** 仅遍历导航类控件，不包含列表正文行 */
const NAV_REGIONS = new Set([
  'top_tab',
  'bottom_tab',
  'top',
  'bottom',
  'side',
  'left',
  'right',
  'button',
  'tab',
  'list_item',
]);

const REGION_RANK: Record<string, number> = {
  bottom_tab: 0,
  bottom: 0,
  top_tab: 1,
  top: 1,
  side: 2,
  left: 3,
  right: 3,
  button: 4,
  tab: 4,
  list_item: 5,
  other: 6,
};

function isNavigationItem(item: NavItem): boolean {
  const r = (item.region || 'other').toLowerCase();
  if (r === 'list' || r === 'content' || r === 'row') {
    return false;
  }
  if (NAV_REGIONS.has(r)) return true;
  // 未标注 region 时仅保留短标签（避免长列表文案）
  if (r === 'other' && item.name.length <= 12) return true;
  return false;
}

function normalizeNavItems(raw: unknown): NavItem[] {
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
        o.clickable === undefined
          ? true
          : Boolean(o.clickable);
      out.push({ name, region, clickable });
    }
  }
  const seen = new Set<string>();
  return out.filter((n) => {
    const k = n.name.toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return isNavigationItem(n);
  });
}

function sortNavItems(items: NavItem[]): NavItem[] {
  return [...items].sort((a, b) => {
    const ra = REGION_RANK[(a.region || 'other').toLowerCase()] ?? 8;
    const rb = REGION_RANK[(b.region || 'other').toLowerCase()] ?? 8;
    if (ra !== rb) return ra - rb;
    return a.name.localeCompare(b.name, 'zh');
  });
}

function pathKey(path: string[]): string {
  return path.join(' > ') || '(root)';
}

function tapKey(path: string[], name: string): string {
  return `${pathKey(path)}|${name}`;
}

/** 功能路径唯一键（用于去重） */
function fullPathKey(path: string[], name: string): string {
  const parts = [...path, name].map((s) => s.trim()).filter(Boolean);
  return parts.join(' > ');
}

function screenFingerprint(screenTitle: string, path: string[]): string {
  return `${pathKey(path)}@@${screenTitle.trim()}`;
}

/** 不参与自动点击的控件（易误入弹窗关闭或无法返回） */
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

function isBlockedTapName(name: string): boolean {
  const n = name.trim().toLowerCase();
  if (AUTO_TAP_BLOCKLIST.has(n)) return true;
  if (/^关闭|^取消|^跳过/.test(name.trim())) return true;
  return false;
}

function filterNavItemsForScreen(
  items: NavItem[],
  path: string[],
  depth: number,
): NavItem[] {
  const inPath = new Set(path.map((p) => p.trim().toLowerCase()));
  return items.filter((item) => {
    if (!isNavigationItem(item)) return false;
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

  const upsertFeature = (
    item: NavItem,
    path: string[],
    depth: number,
    screenTitle: string,
    status: FeatureEntry['status'],
    parentId?: string,
  ): FeatureEntry => {
    const key = fullPathKey(path, item.name);
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
      name: item.name,
      path: [...path, item.name],
      depth: path.length + 1,
      region: item.region,
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
        { machineOut, promptHint: launchTask },
      );
      resolvedBundleId = pkg;
      emitStep('done', launchTask);
    }
    await sleep(2500);

    const targetBundle = () =>
      (resolvedBundleId || bundleIdOpt || '').trim();

    let scopeOffAppStreak = 0;

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
            { machineOut, promptHint: launchTask },
          );
        } else {
          const launchTask = `打开应用「${appName}」，不要打开其他应用`;
          await logModelCall(
            'aiAct',
            launchTask,
            () => withStepTimeout(handle!.aiAct(launchTask), launchTask),
            { machineOut, promptHint: launchTask },
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
          { machineOut, promptHint: prompt },
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
      let offByVision = false;
      if (!offByBundle) {
        const vision = await visionSaysInTargetApp();
        offByVision = vision === false;
      }

      if (!offByBundle && !offByVision) {
        scopeOffAppStreak = 0;
        emit({
          kind: 'explore_scope',
          in_target: true,
          foreground_bundle: foreground || undefined,
          target_bundle: target,
          message: context,
        });
        return true;
      }

      scopeOffAppStreak += 1;
      const msg = offByBundle
        ? `前台 ${foreground} ≠ 目标 ${target}（${context}）`
        : `视觉判断已离开「${appName}」（${context}）`;
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
          scopeOffAppStreak = 0;
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
          scopeOffAppStreak = 0;
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
          { machineOut, promptHint: task },
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
          { machineOut, promptHint: dismissTask },
        );
      }
    } catch {
      /* 无弹窗时忽略 */
    }
    emitStep('done', dismissTask);
    await ensureInTargetApp('处理弹窗后');

    async function queryScreenTitle(): Promise<string> {
      const prompt =
        'string, 用简短中文描述当前页面标题或所在位置（不超过20字）';
      try {
        const t = await logModelCall(
          'aiQuery',
          '页面标题',
          () => withStepTimeout(handle!.aiQuery<string>(prompt), '页面标题'),
          { machineOut, promptHint: prompt },
        );
        return String(t ?? '').trim() || '未知页面';
      } catch {
        return '未知页面';
      }
    }

    const navQueryPrompt =
      `{name: string, region: string, clickable: boolean}[], 仅在「${appName}」应用当前界面列出功能入口（GIIC 扫描）：` +
      '包括顶部/底部 Tab、侧栏、工具栏按钮、页面内按钮。' +
      '若当前界面不属于该应用或是华为商城/应用市场/桌面，返回空数组 []。' +
      '不要包含纯展示正文、广告、头像昵称；不要单独列出「关闭」「取消」「跳过」。' +
      'region 取 top_tab|bottom_tab|side|button|tab|list_item|other；去重；不要编造。';

    async function queryNavItems(): Promise<NavItem[]> {
      try {
        const raw = await logModelCall(
          'aiQuery',
          '导航菜单',
          () => withStepTimeout(handle!.aiQuery<unknown>(navQueryPrompt), '导航菜单'),
          {
            machineOut,
            promptHint: navQueryPrompt,
            resultToText: (r) => JSON.stringify(r ?? ''),
          },
        );
        return sortNavItems(normalizeNavItems(raw));
      } catch {
        const fallbackPrompt =
          'string[], 仅列出底部Tab、顶部Tab、侧栏、工具栏按钮名称（中文），不要列表行内容';
        try {
          const names = await logModelCall(
            'aiQuery',
            '导航菜单(简)',
            () => withStepTimeout(handle!.aiQuery<string[]>(fallbackPrompt), '导航菜单(简)'),
            {
              machineOut,
              promptHint: fallbackPrompt,
              resultToText: (r) => JSON.stringify(r ?? []),
            },
          );
          return sortNavItems(
            normalizeNavItems(
              (names || []).map((n) => ({
                name: n,
                region: 'button',
                clickable: true,
              })),
            ),
          );
        } catch {
          return [];
        }
      }
    }

    async function queryHasNextLevel(
      menuName: string,
      childPath: string[],
    ): Promise<boolean> {
      const prompt =
        `boolean, 已进入「${menuName}」对应页面后，是否还存在可点击进入的下一级子菜单或子页面` +
        '（不包括仅切换底部/顶部主 Tab、不包括纯内容展示区域）';
      try {
        const r = await logModelCall(
          'aiQuery',
          '是否有下级',
          () => withStepTimeout(handle!.aiQuery<boolean>(prompt), '是否有下级'),
          { machineOut, promptHint: prompt },
        );
        return r === true;
      } catch {
        const subNav = filterNavItemsForScreen(
          await queryNavItems(),
          childPath,
          childPath.length,
        );
        return subNav.length > 0;
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
      if (screensVisited >= maxScreens || depth > maxDepth) {
        return;
      }

      if (!(await ensureInTargetApp(`深度 ${depth} 进入页面前`))) {
        return;
      }

      const screenTitle = await queryScreenTitle();
      if (isOffAppScreenTitle(screenTitle)) {
        emitStep('error', '界面疑似站外', screenTitle);
        await ensureInTargetApp(`站外界面：${screenTitle}`);
        return;
      }
      if (scopeOffAppStreak >= 3) {
        emitStep('error', '连续离站', '多次无法回到被测应用，停止本分支遍历');
        return;
      }
      const fp = screenFingerprint(screenTitle, path);
      if (visitedScreens.has(fp)) {
        return;
      }
      visitedScreens.add(fp);
      screensVisited += 1;
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
        return;
      }

      const items = filterNavItemsForScreen(
        await queryNavItems(),
        path,
        depth,
      );

      for (const item of items) {
        if (options.shouldCancel?.()) throw new Error('探索已取消');
        upsertFeature(item, path, depth, screenTitle, 'listed', parentId);
      }

      const clickable = items.filter((i) => i.clickable !== false);
      const dfsOrder = [...clickable].sort((a, b) => {
        const ra = REGION_RANK[(a.region || 'other').toLowerCase()] ?? 8;
        const rb = REGION_RANK[(b.region || 'other').toLowerCase()] ?? 8;
        if (ra !== rb) return ra - rb;
        return a.name.localeCompare(b.name, 'zh');
      });
      const toVisit = dfsOrder.slice(0, maxTaps);

      for (const item of toVisit) {
        if (options.shouldCancel?.()) throw new Error('探索已取消');
        if (screensVisited >= maxScreens || depth >= maxDepth) break;

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
        const tapTask = scopedTapTask(item.name, appName, targetBundle());
        emitStep('start', tapTask);
        try {
          await logModelCall(
            'aiAct',
            tapTask,
            () => withStepTimeout(handle!.aiAct(tapTask), tapTask),
            { machineOut, promptHint: tapTask },
          );
          await sleep(1800);
          emitStep('done', tapTask);
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

        const afterTitle = await queryScreenTitle();
        if (isOffAppScreenTitle(afterTitle)) {
          emitStep('error', '点击后进入站外', afterTitle);
          await ensureInTargetApp(`点击「${item.name}」后站外`);
          await tryNavigateBack(`站外恢复·${item.name}`);
          continue;
        }
        const afterFp = screenFingerprint(afterTitle, childPath);
        if (afterFp === fp || afterFp === screenFingerprint(afterTitle, path)) {
          emitStep('done', `「${item.name}」无下级页面，跳过深入`);
          await tryNavigateBack(`「${item.name}」无下级`);
          continue;
        }

        const hasChild = await queryHasNextLevel(item.name, childPath);
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

    await exploreScreen([], 0);

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
      message: `探索完成，共发现 ${features.length} 项功能（访问 ${screensVisited} 个页面）`,
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

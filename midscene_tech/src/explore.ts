/**
 * 通过 Midscene + HDC 遍历鸿蒙 APP，采集功能菜单树。
 */

import { assertMidsceneModelEnv, loadAgentConfig } from './config.js';
import { createExploreAgent, type ExploreAgentHandle } from './explore_agent.js';
import type {
  ExploreMachineEvent,
  ExploreOptions,
  ExploreRunOutcome,
  ExploreTreeResult,
  FeatureEntry,
  NavItem,
} from './explore_types.js';
import { logModelCall } from './model_log.js';
import { launchAppByBundleId, launchAppByName } from './resolve_app_launch.js';

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
  other: 5,
};

function isNavigationItem(item: NavItem): boolean {
  const r = (item.region || 'other').toLowerCase();
  if (r === 'list_item' || r === 'list' || r === 'content' || r === 'row') {
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
  const cfg = loadAgentConfig({
    deviceId: options.deviceId,
    hdcHome: options.hdcHome,
    aiActionContext: options.aiActionContext,
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
  let screensVisited = 0;
  let featureSeq = 0;
  let stepSeq = 0;

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
    featureByKey.set(key, entry);
    features.push(entry);
    emit({ kind: 'explore_feature', feature: entry });
    return entry;
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
      await logModelCall('aiAct', launchTask, () => handle!.aiAct(launchTask), {
        machineOut,
        promptHint: launchTask,
      });
      resolvedBundleId = pkg;
      emitStep('done', launchTask);
    }
    await sleep(2500);

    const dismissTask = '若出现权限、协议或引导弹窗，按任务需要点击同意或关闭，直到看到主界面';
    emitStep('start', dismissTask);
    try {
      await logModelCall('aiAct', dismissTask, () => handle!.aiAct(dismissTask), {
        machineOut,
        promptHint: dismissTask,
      });
    } catch {
      /* 无弹窗时忽略 */
    }
    emitStep('done', dismissTask);

    async function queryScreenTitle(): Promise<string> {
      const prompt =
        'string, 用简短中文描述当前页面标题或所在位置（不超过20字）';
      try {
        const t = await logModelCall(
          'aiQuery',
          '页面标题',
          () => handle!.aiQuery<string>(prompt),
          { machineOut, promptHint: prompt },
        );
        return String(t ?? '').trim() || '未知页面';
      } catch {
        return '未知页面';
      }
    }

    const navQueryPrompt =
      '{name: string, region: string, clickable: boolean}[], 仅列出当前屏幕上的导航控件：' +
      '顶部/底部 Tab、侧栏入口、明确的功能按钮（如「设置」「搜索」「我的」）。' +
      '不要包含列表中的正文行、新闻标题、商品名、聊天记录、设置项列表内容。' +
      'region 只能取 top_tab|bottom_tab|side|button|tab|other；禁止 list_item；' +
      '去重；不要编造。';

    async function queryNavItems(): Promise<NavItem[]> {
      try {
        const raw = await logModelCall(
          'aiQuery',
          '导航菜单',
          () => handle!.aiQuery<unknown>(navQueryPrompt),
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
            () => handle!.aiQuery<string[]>(fallbackPrompt),
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
          () => handle!.aiQuery<boolean>(prompt),
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

      const screenTitle = await queryScreenTitle();
      const fp = screenFingerprint(screenTitle, path);
      if (visitedScreens.has(fp)) {
        return;
      }
      visitedScreens.add(fp);
      screensVisited += 1;

      emit({
        kind: 'explore_page',
        screen_title: screenTitle,
        depth,
        path: [...path],
      });

      const items = filterNavItemsForScreen(
        await queryNavItems(),
        path,
        depth,
      );

      for (const item of items) {
        if (options.shouldCancel?.()) throw new Error('探索已取消');
        upsertFeature(item, path, depth, screenTitle, 'listed', parentId);
      }

      const clickable = items
        .filter((i) => i.clickable !== false)
        .slice(0, maxTaps);

      for (const item of clickable) {
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
        const tapTask = `点击「${item.name}」进入对应页面`;
        emitStep('start', tapTask);
        try {
          await logModelCall('aiAct', tapTask, () => handle!.aiAct(tapTask), {
            machineOut,
            promptHint: tapTask,
          });
          await sleep(1800);
          emitStep('done', tapTask);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          emitStep('error', tapTask, msg);
          continue;
        }

        const afterTitle = await queryScreenTitle();
        const afterFp = screenFingerprint(afterTitle, childPath);
        if (afterFp === fp || afterFp === screenFingerprint(afterTitle, path)) {
          emitStep('done', `「${item.name}」无下级页面，跳过深入`);
          const backTask = '返回上一页';
          emitStep('start', backTask);
          try {
            await logModelCall('aiAct', backTask, () => handle!.aiAct(backTask), {
              machineOut,
              promptHint: backTask,
            });
            await sleep(1200);
          } catch {
            /* ignore */
          }
          continue;
        }

        const hasChild = await queryHasNextLevel(item.name, childPath);
        if (!hasChild) {
          emitStep('done', `「${item.name}」无子菜单，停止下级遍历`);
          const backTask = '返回上一页';
          emitStep('start', backTask);
          try {
            await logModelCall('aiAct', backTask, () => handle!.aiAct(backTask), {
              machineOut,
              promptHint: backTask,
            });
            await sleep(1200);
          } catch {
            /* ignore */
          }
          continue;
        }

        await exploreScreen(childPath, depth + 1, parentEntry.id);

        const backTask = '返回上一页';
        emitStep('start', backTask);
        try {
          await logModelCall('aiAct', backTask, () => handle!.aiAct(backTask), {
            machineOut,
            promptHint: backTask,
          });
          await sleep(1200);
          emitStep('done', backTask);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          emitStep('error', backTask, msg);
          try {
            const alt = '按系统返回键返回';
            await logModelCall('aiAct', alt, () => handle!.aiAct(alt), {
              machineOut,
              promptHint: alt,
            });
            await sleep(1000);
          } catch {
            /* ignore */
          }
        }
      }
    }

    await exploreScreen([], 0);

    const tree: ExploreTreeResult = {
      app_name: appName,
      bundle_id: resolvedBundleId,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      features,
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
    const tree: ExploreTreeResult = {
      app_name: appName,
      bundle_id: resolvedBundleId,
      started_at: startedAt,
      finished_at: new Date().toISOString(),
      features,
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
  return {
    ok: false,
    message,
    tree: {
      app_name: options.appName || '',
      bundle_id: '',
      started_at: new Date().toISOString(),
      features: [],
      screens_visited: 0,
    },
  };
}

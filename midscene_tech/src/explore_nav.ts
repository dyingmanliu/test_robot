/** 功能遍历 — 路径导航（LCA 回退 + 正向重放） */

import type { ExploreAgentHandle } from './explore_agent.js';
import { scopedTapTask } from './app_scope.js';
import { logModelCall } from './model_log.js';
import { longestCommonPrefix, pathKey, tapKey } from './explore_common.js';
import { waitAfterTap } from './explore_snapshot.js';
import type { ExploreMetrics } from './explore_metrics.js';
import { withStepTimeout } from './step_timeout.js';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export type EmitStep = (
  phase: 'start' | 'done' | 'error',
  task: string,
  error?: string,
) => void;

export interface ExploreNavigationDeps {
  handle: ExploreAgentHandle;
  appName: string;
  targetBundle: () => string;
  machineOut: boolean;
  emitStep: EmitStep;
  tryNavigateBack: (context?: string) => Promise<void>;
  ensureInTargetApp: (
    context: string,
    opts?: { relaunch?: boolean },
  ) => Promise<boolean>;
  tappedKeys: Set<string>;
  metrics?: ExploreMetrics;
}

export class ExploreNavigation {
  private currentPath: string[] = [];

  constructor(private readonly deps: ExploreNavigationDeps) {}

  get path(): string[] {
    return [...this.currentPath];
  }

  setPath(path: string[]): void {
    this.currentPath = [...path];
  }

  /** 导航至目标路径（从应用内任意位置） */
  async navigateTo(targetPath: string[]): Promise<boolean> {
    const target = targetPath.map((s) => s.trim()).filter(Boolean);
    const lcp = longestCommonPrefix(this.currentPath, target);
    const ctx = pathKey(target);

    while (this.currentPath.length > lcp) {
      await this.deps.tryNavigateBack(`导航至 ${ctx}`);
      if (this.currentPath.length > 0) {
        this.currentPath = this.currentPath.slice(0, -1);
      } else {
        break;
      }
      await sleep(400);
    }

    for (let i = lcp; i < target.length; i += 1) {
      const seg = target[i];
      const parentPath = target.slice(0, i);
      const tKey = tapKey(parentPath, seg);
      if (this.deps.tappedKeys.has(tKey)) {
        const tapTask = scopedTapTask(
          seg,
          this.deps.appName,
          this.deps.targetBundle(),
        );
        this.deps.emitStep('start', `重放 ${tapTask}`);
        try {
          await logModelCall(
            'aiAct',
            tapTask,
            () =>
              withStepTimeout(
                this.deps.handle.aiAct(tapTask),
                tapTask,
              ),
            {
              machineOut: this.deps.machineOut,
              metrics: this.deps.metrics,
              promptHint: tapTask,
            },
          );
          this.deps.metrics?.onTap();
          await waitAfterTap(
            this.deps.handle,
            this.deps.appName,
            this.deps.machineOut,
            { maxMs: 1400, metrics: this.deps.metrics },
          );
          this.deps.emitStep('done', tapTask);
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : String(err);
          this.deps.emitStep('error', tapTask, msg);
          return false;
        }
      } else {
        return false;
      }

      if (!(await this.deps.ensureInTargetApp(`导航重放「${seg}」后`))) {
        return false;
      }
      this.currentPath = target.slice(0, i + 1);
    }

    this.currentPath = [...target];
    return true;
  }

  /** 点击后更新当前路径 */
  afterTap(childPath: string[]): void {
    this.currentPath = [...childPath];
  }

  reset(): void {
    this.currentPath = [];
  }
}

/** APP 功能遍历 — 数据结构 */

export type FeatureStatus = 'listed' | 'visited';

export interface NavItem {
  name: string;
  region?: string;
  clickable?: boolean;
}

export interface FeatureEntry {
  id: string;
  name: string;
  path: string[];
  depth: number;
  region?: string;
  screen_title?: string;
  status: FeatureStatus;
  parent_id?: string;
}

export interface ExploreTreeResult {
  app_name: string;
  bundle_id: string;
  started_at: string;
  finished_at?: string;
  features: FeatureEntry[];
  screens_visited: number;
}

export interface ExploreOptions {
  /** APP 显示名称（用于报告展示） */
  appName: string;
  /** APP ID，与 `hdc shell bm dump -a` 中的 bundleName 一致；优先用于启动 */
  bundleId?: string;
  /** android | harmonyos */
  devicePlatform?: string;
  maxScreens?: number;
  maxDepth?: number;
  maxTapsPerScreen?: number;
  deviceId?: string;
  hdcHome?: string;
  aiActionContext?: string;
  /** Web 子进程模式：输出 model_usage JSONL */
  machineOut?: boolean;
  onEvent?: (event: ExploreMachineEvent) => void;
  shouldCancel?: () => boolean;
}

export type ExploreMachineEvent =
  | {
      kind: 'explore_page';
      screen_title: string;
      depth: number;
      path: string[];
    }
  | { kind: 'explore_feature'; feature: FeatureEntry }
  | {
      kind: 'step';
      step: number;
      phase: 'start' | 'done' | 'error';
      task: string;
      error?: string;
    };

export interface ExploreRunOutcome {
  ok: boolean;
  message: string;
  tree: ExploreTreeResult;
  reportFile?: string;
}

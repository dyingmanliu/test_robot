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
  /** GIIC 功能完备度：功能类型（由 region 映射） */
  function_type?: string;
  /** GIIC：功能点描述 */
  description?: string;
  /** GIIC：位置信息（路径 + 界面） */
  location?: string;
  /** 发现时所在界面 ID */
  screen_id?: string;
}

/** 按界面深度遍历记录 */
export interface ScreenRecord {
  id: string;
  screen_title: string;
  path: string[];
  depth: number;
  visit_order: number;
  feature_ids: string[];
}

export type FunctionTreeNodeType = 'application' | 'screen' | 'module' | 'function';

/** GIIC 层级功能树节点 */
export interface FunctionTreeNode {
  id: string;
  name: string;
  node_type: FunctionTreeNodeType;
  depth: number;
  path: string[];
  function_type?: string;
  description?: string;
  location?: string;
  screen_title?: string;
  region?: string;
  status?: FeatureStatus;
  feature_id?: string;
  children: FunctionTreeNode[];
}

export interface ExploreTreeResult {
  app_name: string;
  bundle_id: string;
  started_at: string;
  finished_at?: string;
  features: FeatureEntry[];
  /** 按界面访问顺序组织的层级树 */
  function_tree: FunctionTreeNode;
  /** 按导航路径组织的层级树（一级/二级/…） */
  function_tree_by_path?: FunctionTreeNode;
  screens: ScreenRecord[];
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
      screen_id?: string;
      in_target?: boolean;
      foreground_bundle?: string;
      target_bundle?: string;
    }
  | { kind: 'explore_feature'; feature: FeatureEntry }
  | {
      kind: 'step';
      step: number;
      phase: 'start' | 'done' | 'error';
      task: string;
      error?: string;
    }
  | {
      kind: 'explore_scope';
      in_target: boolean;
      foreground_bundle?: string;
      target_bundle: string;
      message: string;
    };

export interface ExploreRunOutcome {
  ok: boolean;
  message: string;
  tree: ExploreTreeResult;
  reportFile?: string;
}

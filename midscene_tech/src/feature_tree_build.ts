/**
 * 将 DFS 扁平功能点列表组装为 GIIC 功能完备度分析用的层级功能树。
 */

import { SEARCH_FEATURE_LABEL, isSearchItem } from './explore_common.js';
import type { FeatureEntry, FunctionTreeNode, ScreenRecord } from './explore_types.js';

const REGION_TO_FUNCTION_TYPE: Record<string, string> = {
  top_tab: '顶部Tab',
  bottom_tab: '底部Tab',
  top: '顶部导航',
  bottom: '底部导航',
  side: '侧栏',
  left: '左侧入口',
  right: '右侧入口',
  search_bar: '搜索框',
  search: '搜索框',
  search_box: '搜索框',
  button: '按钮',
  tab: 'Tab',
  list_item: '列表项',
  other: '其他控件',
};

export function regionToFunctionType(region?: string): string {
  const r = (region || 'other').toLowerCase();
  return REGION_TO_FUNCTION_TYPE[r] || REGION_TO_FUNCTION_TYPE.other;
}

export function buildFeatureDescription(feat: FeatureEntry): string {
  const parts: string[] = [];
  if (feat.screen_title) parts.push(`所在界面：${feat.screen_title}`);
  const ft = regionToFunctionType(feat.region);
  parts.push(`控件类型：${ft}`);
  if (feat.status === 'visited') parts.push('已深度访问');
  else parts.push('本页已识别');
  return parts.join('；');
}

function isSearchFeature(feat: FeatureEntry): boolean {
  return isSearchItem({
    name: feat.name,
    region: feat.region,
    clickable: true,
  });
}

export function buildLocationInfo(feat: FeatureEntry): string {
  if (isSearchFeature(feat)) return SEARCH_FEATURE_LABEL;
  const path = (feat.path || []).join(' > ');
  const screen = feat.screen_title || '';
  if (path && screen) return `${path} @ ${screen}`;
  return path || screen || feat.name || '';
}

/** 为单条功能点补充 GIIC 对齐字段 */
export function enrichFeatureGiicFields(feat: FeatureEntry): FeatureEntry {
  let normalized = feat;
  if (isSearchFeature(feat)) {
    const path = [...(feat.path || [])];
    if (path.length) path[path.length - 1] = SEARCH_FEATURE_LABEL;
    else path.push(SEARCH_FEATURE_LABEL);
    normalized = {
      ...feat,
      name: SEARCH_FEATURE_LABEL,
      region: 'search_bar',
      path,
    };
  }
  return {
    ...normalized,
    function_type: regionToFunctionType(normalized.region),
    description: buildFeatureDescription(normalized),
    location: buildLocationInfo(normalized),
  };
}

function ensureChild(
  parent: FunctionTreeNode,
  name: string,
  nodeType: FunctionTreeNode['node_type'],
  depth: number,
  path: string[],
): FunctionTreeNode {
  const existing = parent.children.find(
    (c) => c.name === name && c.node_type === nodeType,
  );
  if (existing) return existing;
  const node: FunctionTreeNode = {
    id: `${parent.id}/${name}`,
    name,
    node_type: nodeType,
    depth,
    path: [...path],
    children: [],
  };
  parent.children.push(node);
  return node;
}

/**
 * 按导航路径构建层级树：应用 → 模块（路径段）→ 功能点（叶子）。
 */
export function buildFunctionTree(
  appName: string,
  features: FeatureEntry[],
): FunctionTreeNode {
  const root: FunctionTreeNode = {
    id: 'app-root',
    name: appName || '应用',
    node_type: 'application',
    depth: 0,
    path: [],
    children: [],
  };

  const sorted = [...features].sort((a, b) => {
    const pa = (a.path || []).join('\0');
    const pb = (b.path || []).join('\0');
    if (pa.length !== pb.length) return pa.length - pb.length;
    return pa.localeCompare(pb, 'zh');
  });

  for (const raw of sorted) {
    const feat = enrichFeatureGiicFields(raw);
    const path = feat.path || [];
    if (!path.length) continue;

    let parent = root;
    const ancestors: string[] = [];

    for (let i = 0; i < path.length - 1; i += 1) {
      const segment = path[i];
      ancestors.push(segment);
      parent = ensureChild(
        parent,
        segment,
        'module',
        i + 1,
        [...ancestors],
      );
    }

    const leafName = path[path.length - 1];
    const leafPath = [...path];
    const duplicate = parent.children.find(
      (c) => c.node_type === 'function' && c.name === leafName,
    );
    if (duplicate) {
      Object.assign(duplicate, {
        function_type: feat.function_type,
        description: feat.description,
        location: feat.location,
        screen_title: feat.screen_title,
        region: feat.region,
        status: feat.status,
        feature_id: feat.id,
      });
      continue;
    }

    parent.children.push({
      id: feat.id || `fn-${leafPath.join('/')}`,
      name: leafName,
      node_type: 'function',
      depth: leafPath.length,
      path: leafPath,
      function_type: feat.function_type,
      description: feat.description,
      location: feat.location,
      screen_title: feat.screen_title,
      region: feat.region,
      status: feat.status,
      feature_id: feat.id,
      children: [],
    });
  }

  return root;
}

/** 按界面访问顺序挂载屏幕节点（界面 → 其下功能点） */
export function buildScreenGroupedTree(
  appName: string,
  screens: ScreenRecord[],
  features: FeatureEntry[],
): FunctionTreeNode {
  const root: FunctionTreeNode = {
    id: 'app-root',
    name: appName || '应用',
    node_type: 'application',
    depth: 0,
    path: [],
    children: [],
  };

  const featById = new Map(features.map((f) => [f.id, enrichFeatureGiicFields(f)]));

  for (const scr of screens) {
    const pathLabel = scr.path.length ? scr.path.join(' > ') : '主界面';
    const screenNode: FunctionTreeNode = {
      id: scr.id,
      name: `${scr.screen_title}（${pathLabel}）`,
      node_type: 'screen',
      depth: scr.depth + 1,
      path: [...scr.path],
      screen_title: scr.screen_title,
      description: `界面深度 ${scr.depth}；路径 ${pathLabel}`,
      location: pathLabel,
      children: [],
    };

    for (const fid of scr.feature_ids || []) {
      const feat = featById.get(fid);
      if (!feat) continue;
      screenNode.children.push({
        id: feat.id,
        name: feat.name,
        node_type: 'function',
        depth: feat.depth,
        path: [...feat.path],
        function_type: feat.function_type,
        description: feat.description,
        location: feat.location,
        screen_title: feat.screen_title,
        region: feat.region,
        status: feat.status,
        feature_id: feat.id,
        children: [],
      });
    }

    if (screenNode.children.length > 0) {
      root.children.push(screenNode);
    }
  }

  if (!root.children.length) {
    return buildFunctionTree(appName, features);
  }
  return root;
}

export function attachTreesToResult(
  appName: string,
  features: FeatureEntry[],
  screens: ScreenRecord[],
): {
  features: FeatureEntry[];
  function_tree: FunctionTreeNode;
  function_tree_by_path: FunctionTreeNode;
  screens: ScreenRecord[];
} {
  const enriched = features.map(enrichFeatureGiicFields);
  return {
    features: enriched,
    function_tree: buildScreenGroupedTree(appName, screens, enriched),
    function_tree_by_path: buildFunctionTree(appName, enriched),
    screens,
  };
}

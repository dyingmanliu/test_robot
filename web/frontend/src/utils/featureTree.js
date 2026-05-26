/** GIIC 功能完备度：解析 feature_json 中的层级功能树与功能点列表 */

const REGION_LABELS = {
  top_tab: "顶部 Tab",
  bottom_tab: "底部 Tab",
  category_tab: "顶部分类 Tab",
  top: "顶部",
  bottom: "底部",
  side: "侧栏",
  icon_grid: "图标宫格",
  list_item: "列表项",
  button: "按钮",
  tab: "Tab",
  other: "其他",
};

const NODE_TYPE_LABELS = {
  application: "应用",
  screen: "功能",
  module: "功能",
  function: "功能",
};

/** 树/表：除应用根外一律视为功能点 */
export function isFunctionLikeNode(node) {
  if (!node) return false;
  const t = node.node_type;
  return t === "function" || t === "module" || t === "screen";
}

/** 项目占位或空串不应作为应用展示名 */
export function normalizeAppDisplayLabel(name, fallback = "应用") {
  const n = String(name || "").trim();
  if (!n || n === "无") return fallback;
  return n;
}

export function parseFeatureJson(raw) {
  if (!raw) return { features: [], function_tree: null, screens: [] };
  try {
    const data = typeof raw === "string" ? JSON.parse(raw) : raw;
    return {
      features: Array.isArray(data.features) ? data.features : [],
      function_tree: data.function_tree || data.function_tree_by_path || null,
      screens: Array.isArray(data.screens) ? data.screens : [],
      app_name: data.app_name || "",
      bundle_id: data.bundle_id || "",
    };
  } catch {
    return { features: [], function_tree: null, screens: [] };
  }
}

/** 列表/详情展示用应用名：优先 tree_json，与编辑器内应用根一致 */
export function appDisplayNameFromTreeRecord(tree) {
  if (!tree) return "";
  const parsed = parseFeatureJson(tree.tree_json || "");
  const fromJson = String(parsed.app_name || "").trim();
  if (fromJson) return fromJson;
  const ft = parsed.function_tree;
  if (ft?.node_type === "application") {
    const root = String(ft.name || "").trim();
    if (root) return root;
  }
  return String(tree.app_display_name || tree.bundle_id || "").trim();
}

export function nodeTypeLabel(t) {
  return NODE_TYPE_LABELS[t] || t || "节点";
}

export function regionLabel(r) {
  return REGION_LABELS[r] || r || "—";
}

/** 树节点 → 完整路径分段（含自身 name） */
export function nodeFullPathSegs(node) {
  if (!node || node.node_type === "application") return [];
  const name = String(node.name || "").trim();
  let prefix = Array.isArray(node.path)
    ? node.path.map((p) => String(p).trim()).filter(Boolean)
    : [];
  if (name && prefix.length && prefix[prefix.length - 1] === name) return prefix;
  return name ? [...prefix, name] : prefix;
}

/** 树节点 → 表格行 path 前缀（不含叶子 name） */
export function nodePathPrefix(node) {
  const full = nodeFullPathSegs(node);
  const name = String(node?.name || "").trim();
  if (!name || !full.length) return [];
  if (full[full.length - 1] === name) return full.slice(0, -1);
  return full;
}

/** 深度优先展平树，用于表格（除应用根外均为功能） */
export function flattenFunctionTree(node, out = []) {
  if (!node) return out;
  if (isFunctionLikeNode(node)) {
    const prefix = nodePathPrefix(node);
    const full = nodeFullPathSegs(node);
    out.push({
      id: node.feature_id || node.id,
      function_type: node.function_type || regionLabel(node.region),
      name: node.name,
      description: node.description || "",
      location: node.location || full.join(" > "),
      path: prefix,
      depth: node.depth ?? full.length,
      region: node.region,
      screen_title: node.screen_title,
      status: node.status,
    });
  }
  for (const ch of node.children || []) {
    flattenFunctionTree(ch, out);
  }
  return out;
}

/** 树节点列表（含非叶子），供左侧树展示 */
export function treeNodesForUi(root, depth = 0) {
  if (!root) return [];
  const row = {
    id: root.id,
    name: root.name,
    node_type: root.node_type,
    node_type_label: nodeTypeLabel(root.node_type),
    depth,
    path: root.path || [],
    has_children: (root.children || []).length > 0,
    is_function: isFunctionLikeNode(root),
    function_type: root.function_type,
    description: root.description,
    location: root.location,
    screen_title: root.screen_title,
    status: root.status,
    feature_id: root.feature_id,
    children: (root.children || []).map((c) => treeNodesForUi(c, depth + 1)).flat(),
  };
  return [row, ...(row.children || [])];
}

function findFunctionChild(parent, segName) {
  return (parent.children || []).find(
    (c) => c.name === segName && isFunctionLikeNode(c),
  );
}

function upsertFunctionNode(parent, pathSegs, feat) {
  const full = pathSegs;
  const leafName = full[full.length - 1];
  const parentPrefix = full.slice(0, -1);
  const existing = findFunctionChild(parent, leafName);
  const node = {
    id: feat?.id || existing?.id || `f-${full.join("/")}`,
    name: leafName,
    node_type: "function",
    depth: full.length,
    path: parentPrefix,
    function_type: feat?.function_type || existing?.function_type || "功能",
    description: feat?.description || existing?.description || "",
    location: feat?.location || full.join(" > "),
    screen_title: feat?.screen_title || existing?.screen_title,
    region: feat?.region || existing?.region || "other",
    status: feat?.status || existing?.status || "listed",
    feature_id: feat?.id || existing?.feature_id,
    children: existing?.children || [],
  };
  if (existing) {
    Object.assign(existing, node);
    return existing;
  }
  parent.children.push(node);
  return node;
}

/** 从 features 路径构建层级树（中介层与叶子均为 function） */
export function buildTreeFromFeatures(appName, features) {
  const root = {
    id: "app-root",
    name: appName || "应用",
    node_type: "application",
    depth: 0,
    path: [],
    children: [],
  };
  const sorted = [...(features || [])].sort(
    (a, b) => (a.path?.length || 0) - (b.path?.length || 0),
  );
  const pathKeys = new Set();
  for (const feat of sorted) {
    const path = (feat.path || []).filter(Boolean);
    if (!path.length) continue;
    let parent = root;
    const acc = [];
    for (let i = 0; i < path.length; i += 1) {
      acc.push(path[i]);
      const key = acc.join(" > ");
      if (pathKeys.has(key)) {
        const existing = findFunctionChild(parent, path[i]);
        if (existing) parent = existing;
        continue;
      }
      const isLeaf = i === path.length - 1;
      const ch = upsertFunctionNode(
        parent,
        acc,
        isLeaf ? feat : null,
      );
      pathKeys.add(key);
      parent = ch;
    }
  }
  return root;
}

/** 行 → 完整 path（含叶子 name） */
export function featurePathFromRow(row) {
  const name = String(row.name || "").trim();
  const prefix = Array.isArray(row.path) ? row.path.map((p) => String(p).trim()).filter(Boolean) : [];
  if (!name) return prefix;
  if (prefix.length && prefix[prefix.length - 1] === name) return prefix;
  return [...prefix, name];
}

/**
 * 规范表格行：path 仅存父级前缀，name 为叶子名；改名称时左侧树可正确重建。
 */
export function normalizeTableRow(row, allRows = []) {
  if (!row) return row;
  let name = String(row.name || "").trim();
  let prefix = Array.isArray(row.path) ? row.path.map((p) => String(p).trim()).filter(Boolean) : [];
  const locParts = String(row.location || "")
    .split(" > ")
    .map((p) => p.trim())
    .filter(Boolean);
  // 仅当名称与位置信息一致时才用 location 推导，避免改名后 location 未改被旧值覆盖
  if (locParts.length > 1) {
    const locLeaf = locParts[locParts.length - 1];
    if (!name || name === locLeaf) {
      name = locLeaf;
      prefix = locParts.slice(0, -1);
    }
  } else if (locParts.length === 1 && !name) {
    name = locParts[0];
    prefix = [];
  } else if (name && prefix.length && prefix[prefix.length - 1] === name) {
    prefix = prefix.slice(0, -1);
  }
  const fullPath = name ? [...prefix, name] : prefix;
  const isApp =
    row.node_type === "application" || String(row.function_type || "").trim() === "应用";
  const out = {
    ...row,
    path: prefix,
    name,
    location: fullPath.join(" > "),
    depth: fullPath.length,
    node_type: isApp ? "application" : "function",
    function_type: isApp ? "应用" : row.function_type,
  };
  delete out.is_container;
  if (out.node_type !== "application") {
    const ft = String(out.function_type || "").trim();
    if (!ft || ft === "模块" || ft === "界面") out.function_type = "功能";
  }
  return out;
}

export function normalizeTableRows(rows) {
  const list = rows || [];
  return list.map((r) => normalizeTableRow(r, list));
}

/** 按 name+path 刷新 location，与左侧树路径一致 */
export function syncRowLocations(rows) {
  return (rows || []).map((row) => {
    if (row.node_type === "application") {
      const name = String(row.name || "").trim() || "应用";
      return { ...row, name, location: name };
    }
    const full = featurePathFromRow(row);
    return {
      ...row,
      location: full.join(" > "),
      depth: full.length,
    };
  });
}

/** 按完整路径去重，避免左侧树出现重复同级节点 */
export function dedupeTableRows(rows) {
  const normalized = normalizeTableRows(rows || []);
  const seen = new Set();
  const out = [];
  for (const r of normalized) {
    if (r.node_type === "application") {
      if (!seen.has("__app__")) {
        seen.add("__app__");
        out.push(r);
      }
      continue;
    }
    const key = featurePathKey(r);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(r);
  }
  return out;
}

/** 树节点 → 表格行（仅应用根特殊，其余均为功能） */
export function treeNodeToTableRow(node) {
  if (!node) return null;
  if (node.node_type === "application") {
    return {
      id: node.id,
      function_type: "应用",
      name: node.name,
      description: node.description || "",
      location: node.name,
      path: [],
      depth: 0,
      region: "other",
      status: "listed",
      node_type: "application",
    };
  }
  if (isFunctionLikeNode(node) || node.node_type === "function") {
    const full = nodeFullPathSegs(node);
    const prefix = nodePathPrefix(node);
    return {
      id: node.feature_id || node.id,
      function_type: node.function_type || regionLabel(node.region) || "功能",
      name: node.name,
      description: node.description || "",
      location: node.location || full.join(" > "),
      path: prefix,
      depth: node.depth ?? full.length,
      region: node.region || "other",
      screen_title: node.screen_title,
      status: node.status,
      node_type: "function",
    };
  }
  return null;
}

/** 表格行 → features 列表（除应用根外均为功能） */
export function rowsToFeatures(rows) {
  return (rows || [])
    .filter((row) => row.node_type !== "application")
    .map((row, i) => {
      const path = featurePathFromRow(row);
      const leaf = path[path.length - 1] || String(row.name || "").trim();
      if (!leaf) return null;
      return {
        id: String(row.id || `row-${i + 1}`),
        name: leaf,
        path,
        depth: row.depth ?? path.length,
        region: row.region || "other",
        screen_title: row.screen_title || "",
        status: row.status || "listed",
        function_type: row.function_type || regionLabel(row.region),
        description: row.description || "",
        location: row.location || path.join(" > "),
      };
    })
    .filter(Boolean);
}

/** 识别表格中的应用根行（兼容缺少 node_type 的历史数据） */
export function findAppTableRow(rows) {
  return (rows || []).find(
    (r) =>
      r?.node_type === "application" ||
      String(r?.function_type || "").trim() === "应用",
  );
}

/** 从表格应用根行或 fallback 解析应用显示名 */
export function appNameFromTableRows(rows, appDisplayName = "", parsed = {}) {
  const appRow = findAppTableRow(rows);
  const fromRow = String(appRow?.name || "").trim();
  if (fromRow) return fromRow;
  return String(parsed.app_name || appDisplayName || "").trim() || "应用";
}

/** 根据 features 重建左侧功能树（保存/删除后必须与表格一致） */
export function syncTreeFromTableRows(appDisplayName, rows, parsed = {}) {
  const normalized = normalizeTableRows(rows);
  const appName = appNameFromTableRows(normalized, appDisplayName, parsed);
  const features = rowsToFeatures(normalized);
  return buildTreeFromFeatures(appName, features);
}

/** 在选中节点下新增功能点时，path 前缀（父节点完整路径，不含新叶子名） */
export function parentPathForNewChild(node) {
  if (!node || node.node_type === "application") return [];
  return nodeFullPathSegs(node);
}

/** 新建子功能点默认名称（避免空名导致左侧树不显示） */
export function nextDefaultChildName(rows, base = "新功能点", parentPrefix = []) {
  const names = new Set(
    (rows || []).map((r) => featurePathKey(r)).filter(Boolean),
  );
  let n = 1;
  let candidate = base;
  while (true) {
    const full = [...parentPrefix, candidate].filter(Boolean).join(" > ");
    if (!names.has(full)) return candidate;
    n += 1;
    candidate = `${base}${n}`;
  }
}

export function findTreeNodeByRowId(root, rowId) {
  if (!root || !rowId) return null;
  if (root.feature_id === rowId || root.id === rowId) return root;
  for (const ch of root.children || []) {
    const hit = findTreeNodeByRowId(ch, rowId);
    if (hit) return hit;
  }
  return null;
}

export function findTreeNodeById(root, nodeId) {
  if (!root || !nodeId) return null;
  if (root.id === nodeId) return root;
  for (const ch of root.children || []) {
    const hit = findTreeNodeById(ch, nodeId);
    if (hit) return hit;
  }
  return null;
}

/** 按完整路径（如 新功能点2 > 新功能点21）查找树节点 */
export function findTreeNodeByPathKey(root, pathKey) {
  if (!root || pathKey == null) return null;
  const segs = String(pathKey)
    .split(" > ")
    .map((p) => p.trim())
    .filter(Boolean);
  if (!segs.length) return root.node_type === "application" ? root : null;
  let node = root;
  for (const seg of segs) {
    const ch = (node.children || []).find(
      (c) => c.name === seg && (isFunctionLikeNode(c) || c.node_type === "application"),
    );
    if (!ch) return null;
    node = ch;
  }
  return node;
}

/** 为树中功能节点补齐表格行（含中介层） */
export function enrichTableRowsWithTreeFunctions(tree, rows) {
  const normalized = normalizeTableRows(rows || []);
  const byKey = new Map();
  for (const r of normalized) {
    const k = featurePathKey(r);
    if (k) byKey.set(k, r);
  }
  const out = [...normalized];
  const seen = new Set();

  function walk(node) {
    if (!node) return;
    if (isFunctionLikeNode(node)) {
      const nodeKey = nodeFullPathSegs(node).join(" > ");
      if (nodeKey && !byKey.has(nodeKey) && !seen.has(nodeKey)) {
        const row = treeNodeToTableRow(node);
        if (row) {
          out.push(row);
          seen.add(nodeKey);
        }
      }
    }
    for (const ch of node.children || []) walk(ch);
  }
  walk(tree);
  return out;
}

/** @deprecated 使用 enrichTableRowsWithTreeFunctions */
export const enrichTableRowsWithTreeModules = enrichTableRowsWithTreeFunctions;

export function featurePathKey(rowOrNode) {
  if (!rowOrNode || rowOrNode.node_type === "application") return "";
  const path = featurePathFromRow(rowOrNode);
  return path.join(" > ");
}

/** 表格行是否与树节点同一功能点（id 或 path 一致） */
export function isSameFeatureRow(row, node) {
  if (!row || !node || row.node_type === "application") return false;
  if (node.node_type === "application") return false;
  const rid = row.id;
  const nid = node.feature_id || node.id;
  if (rid && nid && (rid === nid || rid === node.id)) return true;
  const rk = featurePathKey(row);
  const nk = nodeFullPathSegs(node).join(" > ");
  return Boolean(rk && nk && rk === nk);
}

export function resolveWorkbenchData(featureJsonStr, appDisplayName) {
  const parsed = parseFeatureJson(featureJsonStr);
  const appName = normalizeAppDisplayLabel(
    parsed.app_name || appDisplayName,
    normalizeAppDisplayLabel(appDisplayName),
  );
  const features = parsed.features || [];
  const treeFromFeatures = buildTreeFromFeatures(appName, features);
  let tree = parsed.function_tree;
  if (features.length) {
    tree = treeFromFeatures;
  } else if (!tree || !tree.children?.length) {
    tree = treeFromFeatures;
  }
  const tableRows = flattenFunctionTree(tree);
  const fallbackRows = (parsed.features || []).map((f) => ({
    id: f.id,
    function_type: f.function_type || regionLabel(f.region),
    name: f.name || (f.path || []).slice(-1)[0],
    description: f.description || "",
    location: f.location || (f.path || []).join(" > "),
    path: f.path || [],
    depth: f.depth,
    region: f.region,
    screen_title: f.screen_title,
    status: f.status,
  }));
  return {
    tree,
    tableRows: tableRows.length ? tableRows : fallbackRows,
    screens: parsed.screens,
    features: parsed.features,
  };
}

/** 选中节点对应的完整路径分段（用于匹配子级） */
export function subtreePathPrefix(node) {
  if (!node) return null;
  if (node.node_type === "application") return [];
  return nodeFullPathSegs(node);
}

function rowMatchesSubtree(row, prefixSegs) {
  const rowPath = featurePathFromRow(row);
  if (!prefixSegs.length) return rowPath.length >= 1;
  if (rowPath.length < prefixSegs.length) return false;
  for (let i = 0; i < prefixSegs.length; i += 1) {
    if (rowPath[i] !== prefixSegs[i]) return false;
  }
  return true;
}

/** 是否为直接子级（路径深度 = 父前缀 + 1） */
function rowIsDirectChild(row, prefixSegs) {
  const rowPath = featurePathFromRow(row);
  if (!prefixSegs.length) return rowPath.length === 1;
  return rowMatchesSubtree(row, prefixSegs) && rowPath.length === prefixSegs.length + 1;
}

function rowMatchesNodeKey(row, node) {
  const nodeKey = nodeFullPathSegs(node).join(" > ");
  return Boolean(nodeKey && featurePathKey(row) === nodeKey);
}

function resolveRowForTreeNode(tableRows, treeNode) {
  const rows = tableRows || [];
  if (treeNode.node_type === "application") {
    return (
      rows.find((r) => r.node_type === "application") || treeNodeToTableRow(treeNode)
    );
  }
  const nodeKey = nodeFullPathSegs(treeNode).join(" > ");
  if (nodeKey) {
    const exact = rows.find((r) => featurePathKey(r) === nodeKey);
    if (exact) return exact;
  }
  if (isFunctionLikeNode(treeNode)) {
    const byId = rows.find(
      (r) =>
        r.node_type !== "application" &&
        (r.id === treeNode.feature_id || r.id === treeNode.id),
    );
    if (byId) return byId;
  }
  return treeNodeToTableRow(treeNode);
}

/** 保证表格含应用根行（选中根节点时右侧可展示） */
export function ensureAppTableRow(tree, rows, appDisplayName = "") {
  const list = [...(rows || [])];
  const appName = normalizeAppDisplayLabel(
    tree?.name || appDisplayName,
    "应用",
  );
  const idx = list.findIndex(
    (r) => r.node_type === "application" || String(r.function_type || "").trim() === "应用",
  );
  const appRow = {
    id: tree?.id || "app-root",
    function_type: "应用",
    name: appName,
    description: "",
    location: appName,
    path: [],
    depth: 0,
    region: "other",
    status: "listed",
    node_type: "application",
  };
  if (idx >= 0) {
    const editedName = normalizeAppDisplayLabel(list[idx].name, "");
    list[idx] = {
      ...appRow,
      ...list[idx],
      name: editedName || appName,
      location:
        normalizeAppDisplayLabel(list[idx].location, "") || editedName || appName,
    };
    return list;
  }
  return [appRow, ...list];
}

/** 按左侧树深度优先顺序排列表格行（应用根行置顶） */
export function tableRowsInTreeOrder(tree, rows) {
  if (!tree) return rows || [];
  const byKey = new Map();
  const byId = new Map();
  for (const r of rows || []) {
    if (r.id) byId.set(r.id, r);
    const k = featurePathKey(r);
    if (k) byKey.set(k, r);
  }
  const out = [];
  const seen = new Set();
  const appRow = (rows || []).find((r) => r.node_type === "application");
  if (appRow) {
    seen.add("app");
    out.push(appRow);
  }

  function walk(node) {
    if (!node) return;
    if (isFunctionLikeNode(node)) {
      const k = nodeFullPathSegs(node).join(" > ");
      const row = byKey.get(k) || byId.get(node.feature_id || node.id);
      if (row) {
        const sig = featurePathKey(row) || row.id;
        if (!seen.has(sig)) {
          seen.add(sig);
          out.push(row);
        }
      }
    }
    for (const ch of node.children || []) walk(ch);
  }
  walk(tree);
  for (const r of rows || []) {
    const sig = featurePathKey(r) || r.id;
    if (sig && !seen.has(sig)) {
      seen.add(sig);
      out.push(r);
    }
  }
  return out;
}

function visitTreeRowsDepthFirst(treeNode, tableRows, out, seen) {
  const row = resolveRowForTreeNode(tableRows, treeNode);
  if (row) {
    const key = featurePathKey(row) || row.id || "";
    const sig = `f:${key}`;
    if (!seen.has(sig)) {
      seen.add(sig);
      out.push(row);
    }
  }
  for (const ch of treeNode.children || []) {
    visitTreeRowsDepthFirst(ch, tableRows, out, seen);
  }
}

/** 选中树节点时：右侧与左侧树层级对齐（自身 + 全部子孙，深度优先） */
export function filterRowsByTreeNode(tableRows, node, treeRoot = null) {
  if (!node) return tableRows;
  const prefixSegs = subtreePathPrefix(node);
  if (prefixSegs === null) return tableRows;

  const rows = tableRows || [];
  const resolved = treeRoot
    ? findTreeNodeById(treeRoot, node.id) ||
      findTreeNodeByRowId(treeRoot, node.feature_id || node.id) ||
      findTreeNodeByPathKey(treeRoot, nodeFullPathSegs(node).join(" > ")) ||
      node
    : node;

  if (treeRoot && resolved.node_type === "application") {
    const anchor = findTreeNodeById(treeRoot, resolved.id) || treeRoot;
    const out = [];
    const seen = new Set();
    const appRow = resolveRowForTreeNode(rows, anchor) || treeNodeToTableRow(anchor);
    if (appRow) {
      seen.add("app");
      out.push(appRow);
    }
    for (const ch of anchor.children || []) {
      visitTreeRowsDepthFirst(ch, rows, out, seen);
    }
    return out;
  }

  if (treeRoot && isFunctionLikeNode(resolved)) {
    const anchor = findTreeNodeById(treeRoot, resolved.id) || resolved;
    const out = [];
    const seen = new Set();
    visitTreeRowsDepthFirst(anchor, rows, out, seen);
    return out;
  }

  const out = [];
  const seenIds = new Set();
  const seenKeys = new Set();

  function push(r) {
    if (!r) return;
    const key = featurePathKey(r);
    if (key && seenKeys.has(key)) return;
    if (r.id && seenIds.has(r.id)) return;
    if (key) seenKeys.add(key);
    if (r.id) seenIds.add(r.id);
    out.push(r);
  }

  if (resolved.node_type === "application") {
    const appRow = resolveRowForTreeNode(rows, resolved) || treeNodeToTableRow(resolved);
    if (appRow) push(appRow);
    for (const r of rows) {
      if (r.node_type !== "application" && rowMatchesSubtree(r, prefixSegs)) push(r);
    }
    return out;
  }

  for (const r of rows) {
    if (rowMatchesNodeKey(r, resolved)) push(r);
  }
  if (isFunctionLikeNode(resolved)) {
    const descendants = rows.filter(
      (r) =>
        r.node_type !== "application" &&
        rowMatchesSubtree(r, prefixSegs) &&
        !rowMatchesNodeKey(r, resolved),
    );
    descendants.sort((a, b) => {
      const pa = featurePathFromRow(a);
      const pb = featurePathFromRow(b);
      if (pa.length !== pb.length) return pa.length - pb.length;
      return pa.join(" > ").localeCompare(pb.join(" > "), "zh-CN");
    });
    for (const r of descendants) push(r);
    const nodeKey = nodeFullPathSegs(resolved).join(" > ");
    const hasRow = nodeKey && out.some((r) => featurePathKey(r) === nodeKey);
    if (!hasRow) {
      const selfRow = treeNodeToTableRow(resolved);
      if (selfRow) out.unshift(selfRow);
    }
  } else {
    for (const r of rows) {
      if (r.node_type === "application") continue;
      if (rowIsDirectChild(r, prefixSegs)) push(r);
    }
  }

  return out;
}

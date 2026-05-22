/**
 * 功能树编辑同步冒烟测试：node web/frontend/scripts/test-feature-tree.mjs
 */
import {
  buildTreeFromFeatures,
  dedupeTableRows,
  enrichTableRowsWithTreeFunctions,
  featurePathKey,
  filterRowsByTreeNode,
  flattenFunctionTree,
  normalizeTableRow,
  nodeFullPathSegs,
  parentPathForNewChild,
  rowsToFeatures,
  appNameFromTableRows,
  appDisplayNameFromTreeRecord,
  ensureAppTableRow,
  syncTreeFromTableRows,
  tableRowsInTreeOrder,
} from "../src/utils/featureTree.js";

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

const app = "时钟";

// 1) 删除后树与表格一致
let rows = [
  { id: "1", name: "11", path: ["11"], function_type: "按钮", description: "111", location: "11" },
  { id: "2", name: "22", path: ["22"], function_type: "按钮", description: "", location: "" },
];
let tree = syncTreeFromTableRows(app, rows, { app_name: app });
assert(flattenFunctionTree(tree).length === 2, "应有 2 个功能叶");

rows = rows.filter((r) => r.id !== "2");
tree = syncTreeFromTableRows(app, rows, { app_name: app });
assert(flattenFunctionTree(tree).length === 1, "删除后树应只剩 1 项");

// 2) 子层级新增
const moduleNode = { node_type: "function", name: "我的", path: [] };
const prefix = parentPathForNewChild(moduleNode);
assert(prefix.join("/") === "我的", "模块下新增 path 前缀");

rows.push({
  id: "3",
  name: "待付款",
  path: prefix,
  function_type: "按钮",
  description: "",
  location: "",
});
tree = syncTreeFromTableRows(app, rows, { app_name: app });
const flat = flattenFunctionTree(tree);
const pay = flat.find((r) => r.name === "待付款");
assert(
  pay && (pay.location === "我的 > 待付款" || featurePathKey(pay) === "我的 > 待付款"),
  "子层级 location 应为 我的 > 待付款",
);

// 3) rowsToFeatures 与 rebuild
const features = rowsToFeatures(rows);
const tree2 = buildTreeFromFeatures(app, features);
assert(flattenFunctionTree(tree2).length === 3, "rebuild 后应含中介功能「我的」与待付款");

// 4) 功能点下添加子级（非同级）
const fnNode = { node_type: "function", name: "11", path: ["11"] };
const childPrefix = parentPathForNewChild(fnNode);
assert(childPrefix.join("/") === "11", "功能点下子级 path 前缀应为 11");

// 5) 有子级时不重复父节点
const dupFeatures = [
  { id: "a", name: "新功能点11", path: ["新功能点11"], region: "button" },
  { id: "b", name: "新功能点", path: ["新功能点11", "新功能点"], region: "button" },
];
const dupTree = buildTreeFromFeatures(app, dupFeatures);
const names = (dupTree.children || []).map((c) => c.name);
assert(names.length === 1 && names[0] === "新功能点11", `应只有一个顶层子节点，实际 ${names.join(",")}`);
const mod = dupTree.children[0];
assert(mod.node_type === "function", "父级应为功能点");
assert((mod.children || []).length === 1, "模块下仅一个叶子");

// 6) 选中父节点：应用/功能点均展示自身+全部子孙
const filterRows = [
  { id: "a", name: "新功能点1", path: [], function_type: "按钮" },
  { id: "b", name: "子A", path: ["新功能点1"], function_type: "按钮" },
  { id: "c", name: "孙B", path: ["新功能点1", "子A"], function_type: "按钮" },
];
const fnFilterTree = buildTreeFromFeatures(app, rowsToFeatures(filterRows));
const fnNodeFilter = fnFilterTree.children.find((c) => c.name === "新功能点1");
const fnFiltered = filterRowsByTreeNode(filterRows, fnNodeFilter, fnFilterTree);
assert(fnFiltered.length === 3, "功能点应显示自身及全部子孙");
assert(fnFiltered.some((r) => r.name === "子A"), "应含子级");
assert(fnFiltered.some((r) => r.name === "孙B"), "应含孙级");

const duped = dedupeTableRows([
  { id: "1", name: "功能点1", path: [], function_type: "按钮" },
  { id: "2", name: "功能点1", path: [], function_type: "按钮" },
]);
assert(duped.length === 1, "重复路径应去重");

// 6b) 在「功能点1」下新增子级：左侧应嵌套，不应出现两个同级「功能点1」
let parentRows = [
  { id: "p1", name: "功能点1", path: [], function_type: "按钮" },
];
const parentFn = { node_type: "function", name: "功能点1", path: [], feature_id: "p1" };
const childPrefix2 = parentPathForNewChild(parentFn);
parentRows.push({
  id: "c1",
  name: "新功能点",
  path: childPrefix2,
  function_type: "按钮",
});
parentRows = dedupeTableRows(parentRows.map((r) => normalizeTableRow(r, parentRows)));
const treeChild = syncTreeFromTableRows(app, parentRows, { app_name: app });
const topKids = (treeChild.children || []).map((c) => c.name);
assert(topKids.length === 1 && topKids[0] === "功能点1", `顶层应只有一个「功能点1」，实际: ${topKids.join(",")}`);
const nested = treeChild.children[0];
assert((nested.children || []).length === 1, "「功能点1」下应有一个子功能点");
assert(nested.children[0].name === "新功能点", "子节点名称应为新功能点");
const parentTreeNode = nested;
const panel = filterRowsByTreeNode(parentRows, parentTreeNode, treeChild);
assert(panel.length === 2, "选中父级右侧应为自身+子功能点");
assert(panel.filter((r) => r.name === "功能点1").length === 1, "右侧不应重复两行「功能点1」");

// 7) 改名称后树路径应更新
const renamed = normalizeTableRow({
  id: "x",
  name: "新功能1111",
  path: ["新功能1"],
  function_type: "按钮",
});
const treeRenamed = buildTreeFromFeatures(app, rowsToFeatures([renamed]));
const flatRenamed = flattenFunctionTree(treeRenamed);
const hit = flatRenamed.find((r) => r.id === "x");
assert(hit && hit.name === "新功能1111", "改名后树节点应更新");

// 8) 筛选行与 tableRows 同一引用，按 id 可删除
const table = [
  { id: "a", name: "新功能点", path: [], function_type: "按钮" },
];
const fn = { node_type: "function", id: "a", feature_id: "a", name: "新功能点", path: [] };
const filtered = filterRowsByTreeNode(table, fn);
assert(filtered.length === 1 && filtered[0] === table[0], "筛选应返回 tableRows 原对象");
const idx = table.findIndex((r) => r.id === filtered[0].id);
table.splice(idx, 1);
assert(table.length === 0, "按 id 删除应生效");

// 9) 按 path 删除（id 不一致时）
const delTable = [
  { id: "tree-f-新功能点", name: "新功能点", path: [], function_type: "按钮" },
  { id: "row-other", name: "新功能1", path: [], function_type: "按钮" },
];
const delKey = featurePathKey(delTable[0]);
const delNext = delTable.filter(
  (r) => !(featurePathKey(r) === delKey && r.name === "新功能点"),
);
assert(delNext.length === 1 && delNext[0].name === "新功能1", "按 path 删除应生效");

// 10) 跨多层：应用视图应展示中介模块行；删子不删父
const deepRows = [
  { id: "f1", name: "新功能点1", path: [], function_type: "按钮" },
  { id: "f3", name: "新功能点", path: ["新功能点2"], function_type: "按钮" },
];
let deepTree = syncTreeFromTableRows(app, deepRows, { app_name: app });
let deepTable = enrichTableRowsWithTreeFunctions(deepTree, deepRows);
const appRoot = { id: "app-root", node_type: "application", name: "时钟", path: [] };
const appPanel = filterRowsByTreeNode(deepTable, appRoot, deepTree);
const panelNames = appPanel.map((r) => r.name);
assert(panelNames[0] === "时钟", "应用视图首行应为根节点「时钟」");
assert(panelNames.includes("新功能点2"), "应用视图应含中介层「新功能点2」");
assert(
  panelNames.indexOf("新功能点2") < panelNames.indexOf("新功能点"),
  "中介层应排在子级之前",
);
const ordered = tableRowsInTreeOrder(deepTree, deepTable).map((r) => r.name);
assert(
  ordered.indexOf("新功能点1") < ordered.indexOf("新功能点2") &&
    ordered.indexOf("新功能点2") < ordered.indexOf("新功能点"),
  "表格行应按树层级深度优先排序",
);
const childIdx = deepTable.findIndex((r) => r.id === "f3");
deepTable.splice(childIdx, 1);
deepTree = syncTreeFromTableRows(app, deepTable, { app_name: app });
deepTable = enrichTableRowsWithTreeFunctions(deepTree, deepTable);
assert(
  deepTable.some((r) => r.name === "新功能点2" && r.node_type === "function"),
  "删除子级后中介功能行应保留",
);
assert(deepTable.some((r) => r.id === "f1"), "删除子级不应删掉兄弟节点");

// 11) 子层下新增：路径不重复叠加；选中后右侧有行
const nestedRows = dedupeTableRows([
  { id: "a", name: "新功能点1", path: [], function_type: "按钮" },
  { id: "b", name: "新功能点", path: ["新功能点2"], function_type: "按钮", location: "新功能点2 > 新功能点" },
]);
let nTree = syncTreeFromTableRows(app, nestedRows, { app_name: app });
let nTable = enrichTableRowsWithTreeFunctions(nTree, nestedRows);
const mod2 = nTree.children.find((c) => c.name === "新功能点2");
assert(mod2 && mod2.node_type === "function", "新功能点2 应为功能点");
const leaf = mod2.children.find((c) => c.name === "新功能点");
assert(leaf && leaf.node_type === "function", "新功能点应嵌套在新功能点2 下");
const addPrefix = parentPathForNewChild(leaf);
assert(addPrefix.join(" > ") === "新功能点2 > 新功能点", "子级新增前缀不应重复");
nTable.push({
  id: "c2",
  name: "新功能点2",
  path: addPrefix,
  function_type: "按钮",
});
nTree = syncTreeFromTableRows(app, nTable, { app_name: app });
nTable = enrichTableRowsWithTreeFunctions(nTree, nTable);
const leafNode = nTree.children
  .find((c) => c.name === "新功能点2")
  ?.children?.find((c) => c.name === "新功能点");
const leafPanel = filterRowsByTreeNode(nTable, leafNode, nTree);
assert(leafPanel.length >= 1, "选中子层后右侧应至少显示自身");
assert(
  !parentPathForNewChild(leafNode).join(" > ").includes("新功能点 > 新功能点 >"),
  "不应出现三段重复新功能点路径",
);

// 12) dedupe 须保留应用根行
const dedupedApp = dedupeTableRows([
  { id: "app-root", node_type: "application", name: "时钟1", function_type: "应用", path: [] },
  { id: "f1", name: "子", path: [], function_type: "按钮" },
]);
assert(
  dedupedApp.some((r) => r.node_type === "application" && r.name === "时钟1"),
  "dedupe 不应丢弃应用根行",
);

// 13) 修改应用根名称后左侧树应同步
const appRows = ensureAppTableRow(
  syncTreeFromTableRows(app, [], { app_name: app }),
  [],
  app,
);
appRows[0].name = "时钟1";
appRows[0].location = "时钟1";
const renamedTree = syncTreeFromTableRows(app, appRows, { app_name: app });
assert(renamedTree.name === "时钟1", "改应用根名称后树根应更新");

// 14) 三层：新功能点1 > 新功能点 > 新功能点11，改名不被 location 覆盖
let deep3 = [
  { id: "app-root", node_type: "application", name: "时钟", function_type: "应用", path: [] },
  { id: "f1", name: "新功能点1", path: [], function_type: "按钮" },
  {
    id: "f2",
    name: "新功能点",
    path: ["新功能点1"],
    function_type: "按钮",
    location: "新功能点1 > 新功能点",
  },
];
deep3.push({
  id: "f3",
  name: "新功能点11",
  path: ["新功能点1", "新功能点"],
  function_type: "按钮",
  location: "新功能点1 > 新功能点 > 新功能点11",
});
const norm3 = dedupeTableRows(deep3.map((r) => normalizeTableRow(r, deep3)));
const renamedMid = normalizeTableRow(
  { ...deep3[2], name: "新功能点11", location: "新功能点1 > 新功能点" },
  deep3,
);
assert(renamedMid.name === "新功能点11", "子级改名不应被旧 location 覆盖");
const tree3 = buildTreeFromFeatures(app, rowsToFeatures(norm3));
const l1 = tree3.children.find((c) => c.name === "新功能点1");
const l2 = (l1?.children || []).find((c) => c.name === "新功能点");
const l3 = (l2?.children || []).find((c) => c.name === "新功能点11");
assert(l1 && l2 && l3, "三层子级应出现在左侧树结构中");
assert(appNameFromTableRows(appRows, app, { app_name: app }) === "时钟1", "app_name 应来自表格");

const appRowByFunctionType = [
  { id: "app-root", function_type: "应用", name: "时钟2", location: "时钟2", path: [] },
  { id: "1", name: "新功能点1", path: ["新功能点1"], function_type: "按钮", location: "新功能点1" },
];
assert(
  appNameFromTableRows(appRowByFunctionType, "时钟", { app_name: "时钟" }) === "时钟2",
  "功能类型为应用时应识别根名",
);

assert(
  appDisplayNameFromTreeRecord({
    app_display_name: "时钟",
    tree_json: JSON.stringify({ app_name: "时钟21", function_tree: { node_type: "application", name: "时钟21" } }),
  }) === "时钟21",
  "列表展示名应优先 tree_json.app_name",
);

console.log("OK: feature tree sync tests passed");

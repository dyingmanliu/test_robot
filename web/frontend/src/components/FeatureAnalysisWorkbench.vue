<template>
  <div class="fa-workbench">
    <div class="wb-grid" :class="{ 'no-mirror': !showMirror }">
      <aside class="wb-tree-pane">
        <h3 class="wb-pane-title">功能树</h3>
        <p class="muted small wb-pane-hint">界面深度优先遍历 · GIIC 功能完备度</p>
        <div v-if="!treeRoot" class="muted small">等待分析产出功能树…</div>
        <ul v-if="treeRoot" class="tree-root">
          <FeatureTreeBranch
            :key="treeRenderKey"
            :node="treeRoot"
            :selected-id="selectedId"
            :collapsed-ids="collapsedIds"
            :depth="0"
            @select="onSelectNode"
            @toggle-collapse="toggleNodeCollapse"
          />
        </ul>
      </aside>

      <section class="wb-table-pane">
        <h3 class="wb-pane-title">功能点信息</h3>
        <p class="muted small wb-pane-hint">
          {{ visibleRowIndices.length }} 项
          <span v-if="selectedNode">· {{ filterScopeLabel }}</span>
        </p>
        <div class="table-wrap">
          <table class="giic-tbl">
            <colgroup>
              <col class="col-type" />
              <col class="col-name" />
              <col class="col-desc" />
              <col class="col-loc" />
              <col v-if="editable" class="col-act" />
            </colgroup>
            <thead>
              <tr>
                <th>功能类型</th>
                <th>功能点名称</th>
                <th>功能点描述</th>
                <th>位置信息</th>
                <th v-if="editable" class="th-act">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!visibleRowIndices.length">
                <td :colspan="editable ? 5 : 4" class="empty-cell muted">暂无功能点，选中左侧节点后点击下方按钮添加</td>
              </tr>
              <tr
                v-for="idx in visibleRowIndices"
                :key="tableRows[idx]?.id || idx"
                :class="{
                  highlight: selectedId && tableRows[idx]?.id === selectedId,
                  'row-container': tableRows[idx]?.node_type === 'application',
                }"
              >
                <td>
                  <input
                    v-if="editable"
                    v-model="tableRows[idx].function_type"
                    class="cell-input"
                    type="text"
                    @input="scheduleSyncTreeFromRows"
                  />
                  <span v-else>{{ tableRows[idx].function_type }}</span>
                </td>
                <td>
                  <input
                    v-if="editable"
                    v-model="tableRows[idx].name"
                    class="cell-input"
                    type="text"
                    @input="scheduleSyncTreeFromRows"
                  />
                  <span v-else>{{ tableRows[idx].name }}</span>
                </td>
                <td>
                  <input
                    v-if="editable"
                    v-model="tableRows[idx].description"
                    class="cell-input"
                    type="text"
                    @input="scheduleSyncTreeFromRows"
                  />
                  <span v-else class="desc-cell">{{ tableRows[idx].description }}</span>
                </td>
                <td>
                  <input
                    v-if="editable"
                    v-model="tableRows[idx].location"
                    class="cell-input"
                    type="text"
                    @input="scheduleSyncTreeFromRows"
                  />
                  <span v-else class="loc-cell">{{ tableRows[idx].location }}</span>
                </td>
                <td v-if="editable">
                  <button
                    v-if="tableRows[idx]?.node_type !== 'application'"
                    type="button"
                    class="btn-link danger"
                    @click.stop="removeRow(tableRows[idx])"
                  >
                    删除
                  </button>
                  <span v-else class="muted small">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="editable" class="table-foot">
          <button type="button" class="btn btn-add" @click="addRow">
            {{ addRowLabel }}
          </button>
        </div>
      </section>

      <aside v-if="showMirror" class="wb-mirror-pane">
        <DeviceScreenMirror
          v-if="robotInstanceId"
          :key="`${robotInstanceId}-${devicePlatform}-${deviceId}`"
          :robot-instance-id="robotInstanceId"
          :device-platform="devicePlatform"
          :device-id="deviceId"
          :active="mirrorActive"
          idle-hint="分析进行中显示设备画面"
        />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from "vue";
import DeviceScreenMirror from "@/components/DeviceScreenMirror.vue";
import FeatureTreeBranch from "@/components/FeatureTreeBranch.vue";
import {
  featurePathFromRow,
  featurePathKey,
  nodeFullPathSegs,
  filterRowsByTreeNode,
  findTreeNodeById,
  findTreeNodeByPathKey,
  findTreeNodeByRowId,
  isSameFeatureRow,
  dedupeTableRows,
  enrichTableRowsWithTreeFunctions,
  isFunctionLikeNode,
  nextDefaultChildName,
  normalizeTableRow,
  normalizeTableRows,
  parentPathForNewChild,
  parseFeatureJson,
  resolveWorkbenchData,
  rowsToFeatures,
  syncRowLocations,
  syncTreeFromTableRows,
  appNameFromTableRows,
  ensureAppTableRow,
  tableRowsInTreeOrder,
} from "@/utils/featureTree";

const props = defineProps({
  featureJson: { type: String, default: "" },
  appDisplayName: { type: String, default: "" },
  editable: { type: Boolean, default: false },
  /** 为 true 时不因 featureJson 更新而 reload（实时保存回写 API 时避免打断编辑） */
  freezeJsonReload: { type: Boolean, default: false },
  showMirror: { type: Boolean, default: false },
  robotInstanceId: { type: Number, default: null },
  devicePlatform: { type: String, default: "harmonyos" },
  deviceId: { type: String, default: "" },
  mirrorActive: { type: Boolean, default: false },
});

const emit = defineEmits(["change"]);

function notifyChange() {
  if (props.editable) emit("change");
}

const treeRoot = ref(null);
const tableRows = ref([]);
const selectedId = ref("");
const selectedNode = ref(null);
const treeJsonDraft = ref(null);
const treeRenderKey = ref(0);
/** 折叠的节点 id 集合（默认全部展开） */
const collapsedIds = ref(new Set());
/** 编辑时锚定选中行 id，避免输入过程中路径变化导致选中跳回根节点 */
const selectionAnchor = ref({ rowId: "", pathKey: "" });

const filteredRows = computed(() => {
  const root = treeRoot.value;
  const node = selectedNode.value || root;
  if (!node) return [];
  return filterRowsByTreeNode(tableRows.value, node, root);
});

/** 右侧表格绑定 tableRows 下标，避免 v-model 写在筛选副本上无法输入 */
const visibleRowIndices = computed(() => {
  const filtered = filteredRows.value;
  const rows = tableRows.value;
  const indices = [];
  const seen = new Set();
  for (const f of filtered) {
    let idx = rows.indexOf(f);
    if (idx < 0) idx = findRowIndex(f);
    if (idx >= 0 && !seen.has(idx)) {
      seen.add(idx);
      indices.push(idx);
    }
  }
  return indices;
});

let syncTreeTimer = null;
let skipTableWatch = false;

function updateSelectionAnchor(nodeOrRow) {
  if (!nodeOrRow) {
    selectionAnchor.value = { rowId: "", pathKey: "" };
    return;
  }
  if (nodeOrRow.node_type === "application") {
    selectionAnchor.value = { rowId: nodeOrRow.id || "app-root", pathKey: "" };
    return;
  }
  selectionAnchor.value = {
    rowId: String(nodeOrRow.feature_id || nodeOrRow.id || "").trim(),
    pathKey: featurePathKey(nodeOrRow) || nodeFullPathSegs(nodeOrRow).join(" > "),
  };
}

function scheduleSyncTreeFromRows() {
  if (syncTreeTimer) clearTimeout(syncTreeTimer);
  syncTreeTimer = setTimeout(() => {
    syncTreeTimer = null;
    syncTreeFromRows({ rebuildTable: false, reconcile: false });
    resolveTreeSelection();
  }, 350);
}

const filterScopeLabel = computed(() => {
  const n = selectedNode.value;
  if (!n) return "";
  const cnt = visibleRowIndices.value.length;
  const featCnt = filteredRows.value.filter((r) => r.node_type !== "application").length;
  if (n.node_type === "application") {
    return featCnt
      ? `「${n.name}」及全部子级 · ${cnt} 项`
      : `「${n.name}」· 应用根（可在此添加子功能点）`;
  }
  if (isFunctionLikeNode(n)) {
    return `「${n.name}」及全部子级 · ${cnt} 项`;
  }
  return `已筛选：${n.name}`;
});

const addChildHint = computed(() => {
  const n = selectedNode.value;
  const app = props.appDisplayName || treeRoot.value?.name || "应用";
  if (!n || n.node_type === "application") return `在「${app}」下添加子功能点`;
  if (isFunctionLikeNode(n)) {
    const loc = nodeFullPathSegs(n).join(" > ") || n.name;
    return `在「${loc}」下添加子功能点`;
  }
  return `在「${n.name}」下添加子功能点`;
});

const addRowLabel = computed(() => addChildHint.value);

function selectAppRoot() {
  if (!treeRoot.value) return;
  selectedId.value = treeRoot.value.id;
  selectedNode.value = treeRoot.value;
  updateSelectionAnchor(treeRoot.value);
}

function resolveTreeSelection(nodeOrRow = null) {
  if (!treeRoot.value) return false;
  const anchorId = selectionAnchor.value.rowId;
  if (anchorId) {
    const hit = findTreeNodeByRowId(treeRoot.value, anchorId);
    if (hit) {
      selectedId.value = hit.id;
      selectedNode.value = hit;
      return true;
    }
    const anchorRow = tableRows.value.find((r) => r.id === anchorId);
    if (anchorRow) {
      const hit2 = findTreeNodeByRowId(treeRoot.value, anchorRow.id);
      if (hit2) {
        selectedId.value = hit2.id;
        selectedNode.value = hit2;
        return true;
      }
    }
  }
  const ref = nodeOrRow || selectedNode.value;
  if (!ref) return false;
  const tryIds = [
    selectedId.value,
    ref.id,
    ref.feature_id,
  ].filter(Boolean);
  for (const id of tryIds) {
    const hit =
      findTreeNodeByRowId(treeRoot.value, id) || findTreeNodeById(treeRoot.value, id);
    if (hit) {
      selectedId.value = hit.id;
      selectedNode.value = hit;
      return true;
    }
  }
  const pathKey = nodeFullPathSegs(ref).join(" > ") || featurePathKey(ref);
  if (pathKey) {
    const hit = findTreeNodeByPathKey(treeRoot.value, pathKey);
    if (hit) {
      selectedId.value = hit.id;
      selectedNode.value = hit;
      return true;
    }
    const row = tableRows.value.find((r) => featurePathKey(r) === pathKey);
    if (row?.id) {
      const hit = findTreeNodeByRowId(treeRoot.value, row.id);
      if (hit) {
        selectedId.value = hit.id;
        selectedNode.value = hit;
        return true;
      }
    }
  }
  return false;
}

function reconcileSelectionAfterChange(deletedRow = null) {
  if (!treeRoot.value) {
    selectedId.value = "";
    selectedNode.value = null;
    return;
  }
  if (deletedRow && selectedNode.value && isSameFeatureRow(deletedRow, selectedNode.value)) {
    selectAppRoot();
    return;
  }
  if (resolveTreeSelection()) return;
  if (selectionAnchor.value.rowId) {
    const row = tableRows.value.find((r) => r.id === selectionAnchor.value.rowId);
    if (row && resolveTreeSelection(row)) return;
  }
  if (isFunctionLikeNode(selectedNode.value)) {
    const still = tableRows.value.some((r) =>
      isSameFeatureRow(r, selectedNode.value),
    );
    if (!still) selectAppRoot();
    return;
  }
  if (!selectedNode.value || selectedNode.value.node_type === "application") {
    selectAppRoot();
  }
}

function syncTreeFromRows({ rebuildTable = true, reconcile = true } = {}) {
  if (syncTreeTimer) {
    clearTimeout(syncTreeTimer);
    syncTreeTimer = null;
  }
  let normalized = dedupeTableRows(
    normalizeTableRows([...tableRows.value]),
  );
  normalized = syncRowLocations(
    normalized.map((r) => {
      if (r.node_type !== "application") return r;
      const name = String(r.name || "").trim() || "应用";
      return { ...r, name, location: name };
    }),
  );
  const parsed = parseFeatureJson(props.featureJson);
  const nextTree = syncTreeFromTableRows(
    props.appDisplayName,
    normalized,
    parsed,
  );
  treeRoot.value = nextTree;
  if (!rebuildTable) {
    skipTableWatch = true;
    tableRows.value = syncRowLocations(tableRows.value);
    skipTableWatch = false;
  }
  if (rebuildTable) {
    skipTableWatch = true;
    const enriched = enrichTableRowsWithTreeFunctions(nextTree, normalized);
    tableRows.value = tableRowsInTreeOrder(
      nextTree,
      ensureAppTableRow(nextTree, enriched, props.appDisplayName),
    );
    skipTableWatch = false;
  }
  if (reconcile) {
    reconcileSelectionAfterChange();
  } else {
    resolveTreeSelection();
  }
  notifyChange();
}

function reload() {
  const wb = resolveWorkbenchData(props.featureJson, props.appDisplayName);
  const normalized = dedupeTableRows(
    wb.tableRows.map((r, i) => ({ ...r, id: r.id || `row-${i}` })),
  );
  treeRoot.value = wb.tree;
  const enriched = enrichTableRowsWithTreeFunctions(wb.tree, normalized);
  skipTableWatch = true;
  tableRows.value = tableRowsInTreeOrder(
    wb.tree,
    ensureAppTableRow(wb.tree, enriched, props.appDisplayName),
  );
  skipTableWatch = false;
  selectAppRoot();
}

function toggleNodeCollapse(nodeId) {
  if (!nodeId) return;
  const next = new Set(collapsedIds.value);
  if (next.has(nodeId)) next.delete(nodeId);
  else next.add(nodeId);
  collapsedIds.value = next;
}

function ensurePathExpanded(node) {
  if (!treeRoot.value || !node) return;
  const next = new Set(collapsedIds.value);
  const segs =
    node.node_type === "application" ? [] : nodeFullPathSegs(node);
  let cur = treeRoot.value;
  if (cur?.id) next.delete(cur.id);
  for (const seg of segs) {
    const ch = (cur.children || []).find((c) => c.name === seg);
    if (!ch) break;
    if (ch.id) next.delete(ch.id);
    cur = ch;
  }
  collapsedIds.value = next;
}

function onSelectNode(node) {
  selectedId.value = node.id;
  selectedNode.value = node;
  updateSelectionAnchor(node);
  ensurePathExpanded(node);
}

function addChildRow() {
  if (syncTreeTimer) {
    clearTimeout(syncTreeTimer);
    syncTreeTimer = null;
  }
  const parentSnap = selectedNode.value;
  const prefix = parentPathForNewChild(parentSnap);
  const defaultName = nextDefaultChildName(tableRows.value, "新功能点", prefix);
  const fullPath = [...prefix, defaultName];
  const rowId = `new-${Date.now()}`;
  const row = {
    id: rowId,
    function_type: "按钮",
    name: defaultName,
    description: "",
    location: fullPath.join(" > "),
    path: prefix,
    depth: fullPath.length,
    region: "other",
    status: "listed",
    node_type: "function",
  };
  skipTableWatch = true;
  tableRows.value.push(row);
  syncTreeFromRows({ rebuildTable: true, reconcile: false });
  const treeNode = findTreeNodeByRowId(treeRoot.value, rowId);
  if (treeNode) {
    selectedId.value = treeNode.id;
    selectedNode.value = treeNode;
    updateSelectionAnchor(treeNode);
  } else {
    selectedId.value = rowId;
    selectedNode.value = {
      id: rowId,
      name: defaultName,
      node_type: "function",
      path: prefix,
      feature_id: rowId,
    };
    updateSelectionAnchor(selectedNode.value);
  }
  nextTick(() => {
    skipTableWatch = false;
  });
}

function addRow() {
  addChildRow();
}

function findRowIndex(row) {
  if (!row) return -1;
  const id = row.id;
  if (id) {
    const byId = tableRows.value.findIndex((r) => r.id === id);
    if (byId >= 0) return byId;
  }
  if (row.node_type === "application") {
    return tableRows.value.findIndex((r) => r.node_type === "application");
  }
  const key = featurePathKey(row);
  if (!key) return -1;
  return tableRows.value.findIndex((r) => featurePathKey(r) === key);
}

function removeRow(row) {
  if (row?.node_type === "application") return;
  const targetPath = featurePathFromRow(row);
  const targetKey = featurePathKey(row);
  skipTableWatch = true;
  tableRows.value = tableRows.value.filter((r) => {
    if (r.node_type === "application") return true;
    if (row.id && r.id === row.id) return false;
    if (targetKey && featurePathKey(r) === targetKey) return false;
    if (!targetPath.length) return true;
    const fp = featurePathFromRow(r);
    if (fp.length < targetPath.length) return true;
    for (let i = 0; i < targetPath.length; i += 1) {
      if (fp[i] !== targetPath[i]) return true;
    }
    return false;
  });
  skipTableWatch = false;
  syncTreeFromRows({ rebuildTable: true });
  reconcileSelectionAfterChange(row);
}

function getTreeJson() {
  if (syncTreeTimer) {
    clearTimeout(syncTreeTimer);
    syncTreeTimer = null;
  }
  syncTreeFromRows({ rebuildTable: false });
  const parsed = parseFeatureJson(props.featureJson);
  const normalized = dedupeTableRows(
    normalizeTableRows([...tableRows.value]),
  );
  const features = rowsToFeatures(normalized);
  const tree = syncTreeFromTableRows(props.appDisplayName, normalized, parsed);
  treeRoot.value = tree;
  const appName =
    appNameFromTableRows(normalized, props.appDisplayName, parsed) ||
    String(tree?.name || "").trim() ||
    "应用";
  return {
    app_name: appName,
    bundle_id: parsed.bundle_id || "",
    features,
    function_tree: tree,
    function_tree_by_path: tree,
    screens: parsed.screens || [],
    screens_visited: parsed.screens?.length || features.length || 0,
  };
}

watch(
  () => props.featureJson,
  () => {
    // 首次进入须加载树；已有树时跳过外部 JSON 回写，避免打断编辑
    if (props.freezeJsonReload && props.editable && treeRoot.value) return;
    reload();
  },
  { immediate: true },
);

onUnmounted(() => {
  if (syncTreeTimer) clearTimeout(syncTreeTimer);
});

defineExpose({ getTreeJson, reload, syncTreeFromRows });
</script>

<style scoped>
.fa-workbench {
  width: 100%;
}
.wb-grid {
  display: grid;
  grid-template-columns: minmax(260px, 300px) minmax(0, 1fr) minmax(240px, 280px);
  gap: 1.25rem;
  min-height: 440px;
  align-items: stretch;
}
.wb-grid.no-mirror {
  grid-template-columns: minmax(260px, 300px) minmax(0, 1fr);
}
.wb-pane-title {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
}
.wb-pane-hint {
  margin: 0 0 0.75rem;
  color: #64748b;
}
.wb-tree-pane,
.wb-table-pane,
.wb-mirror-pane {
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.wb-tree-pane {
  padding: 0.85rem 0.65rem 0.75rem;
  background: linear-gradient(180deg, #f8fafc 0%, #fff 48%);
}
.tree-root {
  list-style: none;
  margin: 0;
  padding: 0.15rem 0 0;
  flex: 1;
  overflow: auto;
  max-height: 480px;
}
.wb-table-pane {
  min-width: 0;
  padding: 0.85rem 1rem 1rem;
}
.table-wrap {
  flex: 1;
  overflow: auto;
  max-height: 480px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fafbfc;
}
.giic-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  table-layout: fixed;
}
.giic-tbl col.col-type {
  width: 7.5rem;
}
.giic-tbl col.col-name {
  width: 10rem;
}
.giic-tbl col.col-desc {
  width: auto;
}
.giic-tbl col.col-loc {
  width: 14rem;
}
.giic-tbl col.col-act {
  width: 4.5rem;
}
.giic-tbl thead {
  position: sticky;
  top: 0;
  z-index: 1;
}
.giic-tbl th {
  text-align: left;
  font-weight: 600;
  font-size: 0.8rem;
  color: #475569;
  background: #f1f5f9;
  border-bottom: 1px solid #cbd5e1;
  padding: 0.6rem 0.85rem;
  white-space: nowrap;
}
.giic-tbl td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.65rem 0.85rem;
  vertical-align: top;
  background: #fff;
  color: #334155;
  line-height: 1.45;
}
.giic-tbl tbody tr:hover td {
  background: #f8fafc;
}
.giic-tbl tbody tr.highlight td {
  background: #fffbeb;
}
.giic-tbl tbody tr.row-container td {
  background: #f1f5f9;
  color: #475569;
}
.giic-tbl tbody tr.row-container:hover td {
  background: #e2e8f0;
}
.giic-tbl tbody tr:last-child td {
  border-bottom: none;
}
.th-act,
.giic-tbl td:last-child {
  text-align: center;
}
.empty-cell {
  text-align: center;
  padding: 2rem 1rem !important;
  color: #94a3b8;
}
.cell-input {
  width: 100%;
  box-sizing: border-box;
  padding: 0.4rem 0.55rem;
  border: 1px solid #cbd5e1;
  border-radius: 5px;
  font-size: 0.875rem;
  background: #fff;
}
.cell-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}
.desc-cell,
.loc-cell {
  word-break: break-word;
}
.table-foot {
  margin-top: 0.85rem;
  padding-top: 0.25rem;
}
.btn-add {
  width: 100%;
  max-width: 100%;
  justify-content: center;
}
@media (max-width: 960px) {
  .wb-grid {
    grid-template-columns: 1fr;
  }
  .wb-mirror-pane {
    order: -1;
    min-height: 280px;
  }
}
</style>

<template>
  <div class="app-explore">
    <header class="page-head">
      <p v-if="projectMode" class="back-row">
        <router-link class="back-link" :to="{ name: 'projects' }">← 项目空间</router-link>
      </p>
      <h1>{{ pageTitle }}</h1>
      <p v-if="project" class="project-sub">
        项目空间：<strong>{{ project.name }}</strong> · 被测应用：{{ project.tested_app_name }}
      </p>
      <p class="hint">
        通过 <strong>Midscene + HDC</strong> 连接鸿蒙真机，仅遍历<strong>按钮与导航菜单</strong>（不含列表正文），生成
        <strong>功能菜单树</strong> 并导出 Excel。请确保机器人实例执行引擎为
        <code>midscene</code>，且已配置 <code>MIDSCENE_MODEL_*</code>、<code>HDC_HOME</code>。
        <strong>APP ID</strong> 须与真机执行
        <code>hdc shell bm dump -a</code> 列出的 bundleName 一致；可先刷新下方列表再选择。
      </p>
    </header>

    <section class="card block">
      <h2>探索配置</h2>
      <p v-if="projectError" class="banner err">{{ projectError }}</p>
      <p v-if="robotsError" class="banner err">{{ robotsError }}</p>
      <p v-if="appsError" class="banner err">{{ appsError }}</p>
      <div class="form-grid">
        <label class="field">
          <span>机器人实例（Midscene）</span>
          <select v-model.number="form.robot_instance_id" :disabled="running">
            <option :value="0" disabled>请选择</option>
            <option v-for="r in midsceneRobots" :key="r.id" :value="r.id">
              {{ r.display_name || r.instance_code }} (#{{ r.id }})
            </option>
          </select>
        </label>
        <label class="field field-wide">
          <span>
            APP ID（bundleName）
            <button
              type="button"
              class="btn-link"
              :disabled="appsLoading || running"
              @click="loadInstalledApps"
            >
              {{ appsLoading ? "刷新中…" : "刷新设备应用列表" }}
            </button>
          </span>
          <select v-model="form.bundle_id" :disabled="running || appsLoading" @change="onBundleChange">
            <option value="" disabled>请选择已安装应用</option>
            <option v-for="a in installedApps" :key="a.bundle_id" :value="a.bundle_id">
              {{ a.bundle_id }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>APP 显示名（可选）</span>
          <input
            v-model="form.app_name"
            type="text"
            placeholder="用于报告展示，默认同 APP ID"
            :disabled="running"
          />
        </label>
        <label class="field">
          <span>最大页面数</span>
          <input v-model.number="form.max_screens" type="number" min="5" max="1000" :disabled="running" />
        </label>
        <label class="field">
          <span>最大深度</span>
          <input v-model.number="form.max_depth" type="number" min="1" max="10" :disabled="running" />
        </label>
      </div>
      <div class="form-actions">
        <button
          type="button"
          class="btn primary"
          :disabled="running || !canStart"
          @click="startExplore"
        >
          {{ running ? "探索进行中…" : "开始探索" }}
        </button>
        <button v-if="running && runId" type="button" class="btn" @click="cancelExplore">
          取消
        </button>
      </div>
      <p v-if="!midsceneRobots.length && !robotsLoading" class="muted small">
        暂无 Midscene 机器人。请在「我的机器人」详情中将执行引擎设为 midscene。
      </p>
    </section>

    <section v-if="run" class="card block">
      <div class="status-head">
        <h2>任务状态</h2>
        <span class="pill" :class="statusClass">{{ statusLabel }}</span>
      </div>
      <p v-if="run.output_message" class="muted">{{ run.output_message }}</p>
      <div class="metrics">
        <div class="metric">
          <span class="label">功能项</span>
          <strong>{{ run.feature_count ?? 0 }}</strong>
        </div>
        <div class="metric">
          <span class="label">访问页面</span>
          <strong>{{ run.screens_visited ?? 0 }}</strong>
        </div>
      </div>
      <div v-if="run.has_excel" class="download-row">
        <button type="button" class="btn primary" @click="downloadExcel">下载 Excel 功能清单</button>
      </div>
    </section>

    <section v-if="featureRows.length" class="card block">
      <h2>功能预览（{{ featureRows.length }} 项）</h2>
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>完整路径</th>
              <th>层级</th>
              <th>区域</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in featureRows" :key="row.id || i">
              <td>{{ i + 1 }}</td>
              <td>{{ row.fullPath }}</td>
              <td>{{ row.depth }}</td>
              <td>{{ row.regionLabel }}</td>
              <td>{{ row.statusLabel }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <p v-if="actionError" class="banner err">{{ actionError }}</p>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => {
  const raw = route.params.projectId;
  const n = Number(Array.isArray(raw) ? raw[0] : raw);
  return Number.isFinite(n) && n > 0 ? n : null;
});
const projectMode = computed(() => projectId.value != null);
const pageTitle = computed(() =>
  projectMode.value ? "功能点分析" : "APP 功能清单探索",
);

const project = ref(null);
const projectError = ref("");

const REGION_LABELS = {
  top_tab: "顶部 Tab",
  bottom_tab: "底部 Tab",
  bottom: "底部",
  top: "顶部",
  category_tab: "顶部分类 Tab",
  side: "侧栏",
  icon_grid: "图标宫格",
  list_item: "列表项",
  other: "其他",
};

const STATUS_LABELS = {
  listed: "已列出",
  visited: "已访问",
};

const robots = ref([]);
const robotsLoading = ref(true);
const robotsError = ref("");

const installedApps = ref([]);
const appsLoading = ref(false);
const appsError = ref("");

const form = reactive({
  robot_instance_id: 0,
  bundle_id: "",
  app_name: "",
  max_screens: 1000,
  max_depth: 5,
});

const run = ref(null);
const runId = ref(null);
const actionError = ref("");
let pollTimer = null;

const midsceneRobots = computed(() =>
  (robots.value || []).filter(
    (r) => String(r.test_agent_backend || "").toLowerCase() === "midscene",
  ),
);

const running = computed(() => {
  const s = run.value?.status;
  return s === "pending" || s === "running";
});

const canStart = computed(
  () =>
    form.robot_instance_id > 0 &&
    form.bundle_id.trim().length >= 3 &&
    form.bundle_id.includes(".") &&
    midsceneRobots.value.length > 0,
);

const statusLabel = computed(() => {
  const m = {
    pending: "排队中",
    running: "执行中",
    success: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return m[run.value?.status] || run.value?.status || "—";
});

const statusClass = computed(() => {
  const s = run.value?.status;
  if (s === "success") return "ok";
  if (s === "failed") return "bad";
  if (s === "running" || s === "pending") return "warn";
  return "";
});

const featureRows = computed(() => {
  const log = run.value?.step_log;
  if (!log) return [];
  const feats = [];
  const seen = new Set();
  for (const line of log.split("\n")) {
    if (!line.trim()) continue;
    try {
      const obj = JSON.parse(line);
      if (obj.kind === "explore_feature" && obj.feature) {
        const f = obj.feature;
        const path = f.path || [];
        const key = path.length ? path.join(" > ") : f.name;
        if (seen.has(key)) continue;
        seen.add(key);
        feats.push({
          id: f.id,
          fullPath: path.join(" > ") || f.name,
          depth: f.depth ?? path.length,
          regionLabel: REGION_LABELS[f.region] || f.region || "—",
          statusLabel: STATUS_LABELS[f.status] || f.status || "—",
        });
      }
    } catch {
      /* skip */
    }
  }
  return feats;
});

function onBundleChange() {
  const hit = installedApps.value.find((a) => a.bundle_id === form.bundle_id);
  if (hit && !form.app_name.trim()) {
    form.app_name = hit.label || hit.bundle_id;
  }
}

function applyProjectAppHint() {
  const hint = (project.value?.tested_app_name || "").trim();
  if (!hint) return;
  if (!form.app_name.trim()) {
    form.app_name = hint;
  }
  const exact = installedApps.value.find((a) => a.bundle_id === hint);
  if (exact) {
    form.bundle_id = exact.bundle_id;
    return;
  }
  const partial = installedApps.value.find(
    (a) => a.bundle_id.includes(hint) || hint.includes(a.bundle_id),
  );
  if (partial) {
    form.bundle_id = partial.bundle_id;
    if (!form.app_name.trim()) {
      form.app_name = partial.label || partial.bundle_id;
    }
  }
}

async function loadProject() {
  if (!projectId.value) return;
  projectError.value = "";
  try {
    const { data } = await client.get(`/api/projects/${projectId.value}`);
    project.value = data;
    applyProjectAppHint();
  } catch (e) {
    projectError.value = formatApiError(e);
  }
}

async function loadInstalledApps() {
  appsLoading.value = true;
  appsError.value = "";
  try {
    const { data } = await client.get("/api/app-explore/installed-apps");
    installedApps.value = data || [];
    if (installedApps.value.length && !form.bundle_id) {
      if (!projectMode.value) {
        form.bundle_id = installedApps.value[0].bundle_id;
        onBundleChange();
      } else {
        applyProjectAppHint();
      }
    } else {
      applyProjectAppHint();
    }
  } catch (e) {
    appsError.value = formatApiError(e);
    installedApps.value = [];
  } finally {
    appsLoading.value = false;
  }
}

async function loadRobots() {
  robotsLoading.value = true;
  robotsError.value = "";
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    robots.value = data || [];
    if (midsceneRobots.value.length && !form.robot_instance_id) {
      form.robot_instance_id = midsceneRobots.value[0].id;
    }
  } catch (e) {
    robotsError.value = formatApiError(e);
  } finally {
    robotsLoading.value = false;
  }
}

async function pollRun() {
  if (!runId.value) return;
  try {
    const { data } = await client.get(`/api/app-explore/runs/${runId.value}`);
    run.value = data;
    if (data.status === "pending" || data.status === "running") {
      pollTimer = setTimeout(pollRun, 2000);
    } else {
      stopPoll();
    }
  } catch (e) {
    actionError.value = formatApiError(e);
    stopPoll();
  }
}

function stopPoll() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

async function startExplore() {
  actionError.value = "";
  stopPoll();
  try {
    const { data } = await client.post("/api/app-explore/runs", {
      robot_instance_id: form.robot_instance_id,
      bundle_id: form.bundle_id.trim(),
      app_name: form.app_name.trim() || form.bundle_id.trim(),
      max_screens: form.max_screens,
      max_depth: form.max_depth,
    });
    run.value = data;
    runId.value = data.id;
    pollTimer = setTimeout(pollRun, 1500);
  } catch (e) {
    actionError.value = formatApiError(e);
  }
}

async function cancelExplore() {
  if (!runId.value) return;
  actionError.value = "";
  try {
    const { data } = await client.post(`/api/app-explore/runs/${runId.value}/cancel`);
    run.value = data;
    stopPoll();
  } catch (e) {
    actionError.value = formatApiError(e);
  }
}

async function downloadExcel() {
  if (!runId.value) return;
  actionError.value = "";
  try {
    const { data } = await client.get(`/api/app-explore/runs/${runId.value}/download`, {
      responseType: "blob",
    });
    const name = `${run.value?.app_name || "APP"}-功能清单.xlsx`;
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    actionError.value = formatApiError(e);
  }
}

onMounted(async () => {
  if (projectMode.value) {
    await loadProject();
  }
  loadRobots();
  loadInstalledApps();
});
onUnmounted(stopPoll);
</script>

<style scoped>
.app-explore {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
}
.back-row {
  margin: 0 0 0.5rem;
}
.back-link {
  font-size: 0.9rem;
  color: var(--link, #2563eb);
  text-decoration: none;
}
.back-link:hover {
  text-decoration: underline;
}
.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}
.project-sub {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
  color: var(--text-muted, #64748b);
}
.hint {
  color: var(--text-muted);
  margin: 0 0 1.25rem;
  font-size: 0.92rem;
  line-height: 1.5;
}
.hint code {
  font-size: 0.85em;
  background: var(--bg-subtle);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.block {
  margin-bottom: 1.25rem;
  padding: 1rem 1.15rem;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.85rem 1rem;
  margin-bottom: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.88rem;
}
.field input,
.field select {
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
}
.field-wide {
  grid-column: 1 / -1;
}
.btn-link {
  margin-left: 0.5rem;
  font-size: 0.82rem;
  padding: 0;
  border: none;
  background: none;
  color: var(--link, #2563eb);
  cursor: pointer;
  text-decoration: underline;
}
.btn-link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
select {
  padding: 0.45rem 0.55rem;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 6px;
  max-width: 100%;
}
.form-actions {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}
.status-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}
.status-head h2 {
  margin: 0;
  font-size: 1.1rem;
}
.pill {
  font-size: 0.78rem;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: #e2e8f0;
}
.pill.ok {
  background: #dcfce7;
  color: #166534;
}
.pill.bad {
  background: #fee2e2;
  color: #991b1b;
}
.pill.warn {
  background: #fef9c3;
  color: #854d0e;
}
.metrics {
  display: flex;
  gap: 1.5rem;
  margin: 0.75rem 0;
}
.metric .label {
  display: block;
  font-size: 0.78rem;
  color: var(--text-muted);
}
.download-row {
  margin-top: 0.75rem;
}
.table-wrap {
  overflow-x: auto;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.tbl th,
.tbl td {
  border-bottom: 1px solid var(--border, #e2e8f0);
  padding: 0.45rem 0.5rem;
  text-align: left;
}
.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
}
.muted {
  color: var(--text-muted);
}
.small {
  font-size: 0.85rem;
}
</style>

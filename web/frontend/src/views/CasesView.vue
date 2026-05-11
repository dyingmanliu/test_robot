<template>
  <div class="cases-shell">
    <p class="br-line muted">
      <router-link to="/">工作台</router-link>
      · 用例归属<strong>项目空间</strong>（绑定被测应用与测试目标）；不同客户/应用独立项目，便于协作与隔离。
      <router-link to="/projects">管理项目空间</router-link>
    </p>

    <div v-if="projectsLoaded && !projects.length" class="banner warn">
      尚未创建项目空间。请先到
      <router-link to="/projects">项目空间</router-link>
      新建并绑定被测应用与测试目标。
    </div>
    <div class="toolbar">
      <div class="toolbar-left">
        <h1 class="title">测试用例</h1>
        <label v-if="projects.length" class="proj-picker">
          <span class="picker-label">当前项目空间</span>
          <select v-model.number="selectedProjectId" @change="onProjectChange">
            <option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }} · {{ p.tested_app_name }}
            </option>
          </select>
        </label>
      </div>
      <div class="actions">
        <router-link
          v-if="selectedProjectId"
          class="btn"
          :to="{ name: 'projectDashboard', params: { projectId: selectedProjectId } }"
        >
          项目看板
        </router-link>
        <button
          type="button"
          class="btn primary"
          :disabled="!selectedProjectId"
          @click="openCreate"
        >
          新建用例
        </button>
        <label class="btn import-label">
          导入 CSV/Excel
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            class="hidden-file"
            :disabled="!selectedProjectId"
            @change="onImportFile"
          />
        </label>
        <button
          type="button"
          class="btn"
          :disabled="!selectedIds.length || running"
          @click="runSelected"
        >
          {{ running ? "执行中…" : "自动化执行选中" }}
        </button>
      </div>
    </div>

    <div v-if="loadError" class="banner err">{{ loadError }}</div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th class="narrow">
              <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            </th>
            <th>标题</th>
            <th>优先级</th>
            <th>步骤</th>
            <th>执行说明</th>
            <th class="narrow">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cases" :key="c.id">
            <td>
              <input type="checkbox" :value="c.id" v-model="selectedIds" />
            </td>
            <td>{{ c.title }}</td>
            <td>{{ c.priority || "—" }}</td>
            <td class="muted small">{{ stepPreview(c) }}</td>
            <td class="task">{{ truncate(c.task_text, 80) }}</td>
            <td class="ops">
              <button type="button" class="linkish" @click="openEdit(c)">编辑</button>
              <button type="button" class="linkish" @click="openVersions(c)">版本</button>
              <button type="button" class="linkish danger" @click="remove(c)">删除</button>
            </td>
          </tr>
          <tr v-if="!cases.length && !loading">
            <td colspan="7" class="empty">暂无数据，点击「新建用例」开始。</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="loading" class="muted">加载中…</p>

    <div v-if="liveRun" class="panel live-panel">
      <div class="panel-head">
        <h2>执行进度（实时）</h2>
        <button
          v-if="canStopRun"
          type="button"
          class="btn stop"
          :disabled="stopBusy"
          @click="stopRun"
        >
          {{ stopBusy ? "请求中…" : "停止执行" }}
        </button>
      </div>
      <div class="status-strip">
        <span class="status-line">
          <strong>执行状态：</strong>
          <span class="badge inline" :class="liveRun.status">{{ statusLabel(liveRun.status) }}</span>
        </span>
        <span class="muted small">
          运行 ID {{ liveRun.id }} · 用例 ID {{ liveRun.case_id }}
          · 已完成步骤 {{ stepCount(liveRun) }}
        </span>
        <p v-if="liveRun.status === 'running' || liveRun.status === 'pending'" class="hint">
          停止将在<strong>当前这一步</strong>完成后生效（模型推理与设备操作期间无法立刻打断）。
        </p>
      </div>
      <p v-if="!liveRun.step_log" class="muted">已排队，等待第一步…</p>
      <div v-else class="steps">
        <div
          v-for="(st, idx) in parseStepLog(liveRun.step_log)"
          :key="idx"
          class="step-card"
          :class="{ finished: st.finished }"
        >
          <div class="step-meta">
            <span class="step-no">第 {{ st.step }} 步</span>
            <span v-if="st.finished" class="step-tag">结束</span>
          </div>
          <div v-if="st.thinking" class="step-block">
            <span class="step-label">推理</span>
            <pre class="step-pre">{{ st.thinking }}</pre>
          </div>
          <div v-if="st.action != null" class="step-block">
            <span class="step-label">动作</span>
            <pre class="step-pre action">{{ formatJson(st.action) }}</pre>
          </div>
          <div v-if="st.message" class="step-msg">{{ st.message }}</div>
        </div>
      </div>
    </div>

    <div v-if="resultRuns.length" class="panel">
      <h2>执行结果</h2>
      <div v-for="r in resultRuns" :key="r.id" class="run-block">
        <div class="run-head">
          <span class="badge" :class="r.status">{{ statusLabel(r.status) }}</span>
          <span class="muted small">运行 ID: {{ r.id }} · 用例 ID: {{ r.case_id }}</span>
        </div>
        <div v-if="r.step_log" class="steps">
          <div
            v-for="(st, idx) in parseStepLog(r.step_log)"
            :key="idx"
            class="step-card"
            :class="{ finished: st.finished }"
          >
            <div class="step-meta">
              <span class="step-no">第 {{ st.step }} 步</span>
              <span v-if="st.finished" class="step-tag">结束</span>
            </div>
            <div v-if="st.thinking" class="step-block">
              <span class="step-label">推理</span>
              <pre class="step-pre">{{ st.thinking }}</pre>
            </div>
            <div v-if="st.action != null" class="step-block">
              <span class="step-label">动作</span>
              <pre class="step-pre action">{{ formatJson(st.action) }}</pre>
            </div>
            <div v-if="st.message" class="step-msg">{{ st.message }}</div>
          </div>
        </div>
        <pre v-if="r.output_message" class="out summary">{{ r.output_message }}</pre>
        <pre v-if="r.error_trace" class="out err">{{ r.error_trace }}</pre>
      </div>
    </div>

    <p v-if="importMsg" class="banner ok">{{ importMsg }}</p>

    <div v-if="dialog.open" class="modal-overlay" @click.self="dialog.open = false">
      <div class="modal modal-wide">
        <h3>{{ dialog.editing ? "编辑用例" : "新建用例" }}</h3>
        <label class="field">
          <span>标题</span>
          <input v-model="dialog.title" maxlength="256" />
        </label>
        <label class="field">
          <span>优先级</span>
          <select v-model="dialog.priority">
            <option value="P0">P0 — 最高</option>
            <option value="P1">P1</option>
            <option value="P2">P2 — 默认</option>
            <option value="P3">P3</option>
          </select>
        </label>
        <label class="field">
          <span>前置条件</span>
          <textarea v-model="dialog.preconditions" rows="2" placeholder="环境、账号、数据准备等"></textarea>
        </label>
        <div class="field">
          <span>测试步骤与预期结果</span>
          <div v-for="(s, idx) in dialog.steps" :key="idx" class="step-row">
            <span class="step-no">{{ idx + 1 }}</span>
            <input v-model="s.description" placeholder="步骤说明" />
            <input v-model="s.expected" placeholder="预期结果" />
            <button type="button" class="btn ghost mini" @click="removeStep(idx)">删</button>
          </div>
          <button type="button" class="btn" @click="addStep">添加步骤</button>
        </div>
        <label class="field">
          <span>执行说明（交给自动化 Agent，可与步骤合并）</span>
          <textarea v-model="dialog.task_text" rows="4"></textarea>
        </label>
        <p class="muted small">保存时至少需要「执行说明」或一条有效步骤。</p>
        <p v-if="dialog.error" class="err">{{ dialog.error }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="dialog.open = false">取消</button>
          <button type="button" class="btn primary" @click="saveDialog">保存</button>
        </div>
      </div>
    </div>

    <div v-if="verDialog.open" class="modal-overlay" @click.self="verDialog.open = false">
      <div class="modal modal-wide">
        <h3>版本历史 · {{ verDialog.caseTitle }}</h3>
        <p v-if="verDialog.err" class="err">{{ verDialog.err }}</p>
        <div v-if="verDialog.loading" class="muted">加载中…</div>
        <table v-else class="ver-table">
          <thead>
            <tr>
              <th>版本号</th>
              <th>标题</th>
              <th>优先级</th>
              <th>保存时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in verDialog.items" :key="v.id">
              <td>v{{ v.revision_no }}</td>
              <td>{{ v.title }}</td>
              <td>{{ v.priority }}</td>
              <td>{{ fmtTime(v.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="verDialog.open = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from "axios";
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";

/** 轮询时短暂断网、502 等不应立刻当作「执行失败」；401 等仍应立即失败 */
function isTransientPollError(e) {
  if (!axios.isAxiosError(e)) return false;
  if (!e.response) return true;
  const s = e.response.status;
  return s >= 500 || s === 408 || s === 429;
}

const route = useRoute();
const router = useRouter();

const projects = ref([]);
const projectsLoaded = ref(false);
const selectedProjectId = ref(null);

const cases = ref([]);
const loading = ref(false);
const loadError = ref("");
const selectedIds = ref([]);
const running = ref(false);
const stopBusy = ref(false);
const liveRun = ref(null);
const resultRuns = ref([]);

const canStopRun = computed(() => {
  const r = liveRun.value;
  return !!(r && (r.status === "pending" || r.status === "running"));
});

const importMsg = ref("");

const dialog = reactive({
  open: false,
  editing: false,
  id: null,
  title: "",
  task_text: "",
  preconditions: "",
  priority: "P2",
  steps: [],
  error: "",
});

const verDialog = reactive({
  open: false,
  loading: false,
  err: "",
  items: [],
  caseTitle: "",
});

const allSelected = computed(() => {
  return cases.value.length > 0 && selectedIds.value.length === cases.value.length;
});

async function loadProjects() {
  try {
    const { data } = await client.get("/api/projects");
    projects.value = data;
  } catch {
    projects.value = [];
  }
}

async function load() {
  loading.value = true;
  loadError.value = "";
  if (!selectedProjectId.value) {
    cases.value = [];
    loading.value = false;
    return;
  }
  try {
    const { data } = await client.get("/api/test-cases", {
      params: { project_id: selectedProjectId.value },
    });
    cases.value = data;
    selectedIds.value = selectedIds.value.filter((id) => data.some((c) => c.id === id));
  } catch (e) {
    loadError.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

function onProjectChange() {
  router.replace({ path: "/cases", query: { project: String(selectedProjectId.value) } });
  load();
}

async function bootstrapProjectContext() {
  await loadProjects();
  projectsLoaded.value = true;
  const raw = route.query.project;
  const want = raw ? parseInt(String(raw), 10) : NaN;
  if (projects.value.length) {
    if (!Number.isNaN(want) && projects.value.some((p) => p.id === want)) {
      selectedProjectId.value = want;
    } else {
      selectedProjectId.value = projects.value[0].id;
      router.replace({ path: "/cases", query: { project: String(selectedProjectId.value) } });
    }
  } else {
    selectedProjectId.value = null;
  }
  await load();
}

function toggleAll(e) {
  if (e.target.checked) {
    selectedIds.value = cases.value.map((c) => c.id);
  } else {
    selectedIds.value = [];
  }
}

function truncate(s, n) {
  if (!s) return "—";
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function stepPreview(c) {
  const n = Array.isArray(c.steps) ? c.steps.length : 0;
  return n ? `${n} 步` : "—";
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function addStep() {
  dialog.steps.push({ description: "", expected: "" });
}

function removeStep(idx) {
  dialog.steps.splice(idx, 1);
}

function openCreate() {
  if (!selectedProjectId.value) return;
  dialog.open = true;
  dialog.editing = false;
  dialog.id = null;
  dialog.title = "";
  dialog.task_text = "";
  dialog.preconditions = "";
  dialog.priority = "P2";
  dialog.steps = [{ description: "", expected: "" }];
  dialog.error = "";
}

function openEdit(c) {
  dialog.open = true;
  dialog.editing = true;
  dialog.id = c.id;
  dialog.title = c.title;
  dialog.task_text = c.task_text || "";
  dialog.preconditions = c.preconditions || "";
  dialog.priority = c.priority || "P2";
  const st = Array.isArray(c.steps) && c.steps.length ? c.steps : [];
  dialog.steps = st.length
    ? st.map((x) => ({
        description: x.description || "",
        expected: x.expected || "",
      }))
    : [{ description: "", expected: "" }];
  dialog.error = "";
}

async function openVersions(c) {
  verDialog.open = true;
  verDialog.caseTitle = c.title;
  verDialog.err = "";
  verDialog.loading = true;
  verDialog.items = [];
  try {
    const { data } = await client.get(`/api/test-cases/${c.id}/versions`);
    verDialog.items = data;
  } catch (e) {
    verDialog.err = formatApiError(e);
  } finally {
    verDialog.loading = false;
  }
}

function buildStepsPayload() {
  return dialog.steps
    .map((s, i) => ({
      order: i + 1,
      description: (s.description || "").trim(),
      expected: (s.expected || "").trim(),
    }))
    .filter((s) => s.description || s.expected);
}

async function saveDialog() {
  dialog.error = "";
  if (!dialog.title.trim()) {
    dialog.error = "请填写标题";
    return;
  }
  const stepsPayload = buildStepsPayload();
  if (!dialog.task_text.trim() && stepsPayload.length === 0) {
    dialog.error = "请填写执行说明或至少一条步骤";
    return;
  }
  try {
    const body = {
      title: dialog.title.trim(),
      task_text: dialog.task_text.trim(),
      preconditions: (dialog.preconditions || "").trim(),
      priority: dialog.priority,
      steps: stepsPayload,
    };
    if (dialog.editing && dialog.id) {
      await client.patch(`/api/test-cases/${dialog.id}`, body);
    } else {
      await client.post("/api/test-cases", {
        project_id: selectedProjectId.value,
        ...body,
      });
    }
    dialog.open = false;
    await load();
  } catch (e) {
    dialog.error = formatApiError(e);
  }
}

async function onImportFile(ev) {
  const f = ev.target.files?.[0];
  importMsg.value = "";
  if (!f || !selectedProjectId.value) return;
  try {
    const fd = new FormData();
    fd.append("project_id", String(selectedProjectId.value));
    fd.append("file", f);
    const { data } = await client.post("/api/test-cases/import", fd);
    const errs = (data.errors || []).slice(0, 5).join("；");
    importMsg.value = `导入完成：新建 ${data.created} 条，跳过 ${data.skipped} 条${errs ? `。提示：${errs}` : ""}`;
    await load();
  } catch (e) {
    importMsg.value = formatApiError(e);
  } finally {
    ev.target.value = "";
  }
}

async function remove(c) {
  if (!confirm(`确定删除「${c.title}」？`)) return;
  await client.delete(`/api/test-cases/${c.id}`);
  selectedIds.value = selectedIds.value.filter((id) => id !== c.id);
  await load();
}

function statusLabel(s) {
  const m = {
    pending: "排队",
    running: "执行中",
    success: "成功",
    failed: "失败",
    cancelled: "已终止",
  };
  return m[s] || s;
}

function stepCount(run) {
  return parseStepLog(run?.step_log).length;
}

async function stopRun() {
  const id = liveRun.value?.id;
  if (!id) return;
  stopBusy.value = true;
  try {
    await client.post(`/api/test-cases/runs/${id}/cancel`);
  } catch (e) {
    window.alert(e.response?.data?.detail || String(e.message || e));
  } finally {
    stopBusy.value = false;
  }
}

function parseStepLog(raw) {
  if (!raw || typeof raw !== "string") return [];
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return { step: "?", thinking: line, action: null, message: "无法解析本行日志" };
      }
    });
}

function formatJson(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

async function pollRun(runId, onTick) {
  const deadline = Date.now() + 2 * 60 * 60 * 1000;
  let transientStreak = 0;
  while (Date.now() < deadline) {
    try {
      const { data } = await client.get(`/api/test-cases/runs/${runId}`);
      transientStreak = 0;
      if (typeof onTick === "function") onTick(data);
      if (data.status === "success" || data.status === "failed" || data.status === "cancelled") {
        return data;
      }
    } catch (e) {
      if (isTransientPollError(e)) {
        transientStreak++;
        if (transientStreak > 120) {
          throw new Error(
            "长时间无法连接后端（网络或服务异常）。若正在使用 uvicorn --reload，保存文件会重启进程并中断未完成的自动化任务；长时间跑测时请去掉 --reload。"
          );
        }
      } else {
        throw e;
      }
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("等待执行结果超时（超过 2 小时）");
}

async function runSelected() {
  if (!selectedIds.value.length) return;
  running.value = true;
  liveRun.value = null;
  resultRuns.value = [];
  try {
    for (const caseId of selectedIds.value) {
      liveRun.value = null;
      const { data: started } = await client.post(`/api/test-cases/${caseId}/run`);
      liveRun.value = { ...started };
      const final = await pollRun(started.id, (data) => {
        liveRun.value = data;
      });
      resultRuns.value.push(final);
    }
  } catch (e) {
    resultRuns.value.push({
      id: 0,
      case_id: 0,
      owner_id: 0,
      status: "failed",
      step_log: null,
      output_message: null,
      error_trace: e.response?.data?.detail || String(e.message || e),
      started_at: null,
      finished_at: null,
    });
  } finally {
    liveRun.value = null;
    running.value = false;
  }
}

onMounted(bootstrapProjectContext);
</script>

<style scoped>
.br-line {
  margin: 0 0 1rem;
  font-size: 0.88rem;
  line-height: 1.45;
}

.banner.warn {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  background: #fffbeb;
  color: #92400e;
  font-size: 0.9rem;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.proj-picker {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.picker-label {
  font-size: 0.8rem;
  color: #64748b;
}

.proj-picker select {
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font: inherit;
  max-width: min(420px, 100%);
}

.title {
  margin: 0;
  font-size: 1.35rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
}

.table-wrap {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  overflow: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.table th,
.table td {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.table th {
  background: #f8fafc;
  font-weight: 600;
}

.narrow {
  width: 42px;
}

.task {
  max-width: 420px;
  white-space: pre-wrap;
  word-break: break-word;
}

.ops {
  white-space: nowrap;
}

.linkish {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  padding: 0 0.35rem;
}

.linkish.danger {
  color: #b91c1c;
}

.empty {
  text-align: center;
  color: #64748b;
  padding: 2rem !important;
}

.banner {
  padding: 0.65rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.banner.err {
  background: #fef2f2;
  color: #991b1b;
}

.panel {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.panel h2 {
  margin-top: 0;
  font-size: 1.1rem;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.panel-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.status-strip {
  margin-bottom: 1rem;
  padding: 0.65rem 0.85rem;
  background: #f1f5f9;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.status-line {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-right: 0.5rem;
}

.hint {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: #475569;
}

.btn.stop {
  border-color: #dc2626;
  color: #b91c1c;
  background: #fff;
}

.btn.stop:hover:not(:disabled) {
  background: #fef2f2;
}

.run-block {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.run-block:first-of-type {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.run-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
}

.badge.pending,
.badge.running {
  background: #e0f2fe;
  color: #0369a1;
}

.badge.success {
  background: #dcfce7;
  color: #166534;
}

.badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.badge.cancelled {
  background: #ffedd5;
  color: #9a3412;
}

.badge.inline {
  font-size: 0.8rem;
  vertical-align: middle;
}

.out {
  margin: 0;
  padding: 0.75rem;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  overflow: auto;
  font-size: 0.85rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.out.err {
  background: #450a0a;
  color: #fecaca;
}

.out.summary {
  margin-top: 0.75rem;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.step-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.75rem 0.85rem;
  background: #f8fafc;
}

.step-card.finished {
  border-color: #86efac;
  background: #f0fdf4;
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.step-no {
  font-weight: 600;
  font-size: 0.9rem;
  color: #0f172a;
}

.step-tag {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
}

.step-block {
  margin-top: 0.35rem;
}

.step-label {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.2rem;
}

.step-pre {
  margin: 0;
  padding: 0.55rem 0.65rem;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 280px;
  overflow: auto;
}

.step-pre.action {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.step-msg {
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: #166534;
}

.small {
  font-size: 0.8rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 50;
}

.modal {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
}

.modal h3 {
  margin-top: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.field span {
  font-size: 0.85rem;
  color: #475569;
}

input,
textarea {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
}

.muted {
  color: #64748b;
}

.banner.ok {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  background: #ecfdf5;
  color: #065f46;
  font-size: 0.9rem;
}

.modal-wide {
  max-width: 720px;
  max-height: 90vh;
  overflow-y: auto;
}

.step-row {
  display: grid;
  grid-template-columns: 28px 1fr 1fr auto;
  gap: 0.35rem;
  align-items: center;
  margin-bottom: 0.35rem;
}

.step-no {
  font-size: 0.8rem;
  color: #64748b;
  text-align: right;
}

.hidden-file {
  display: none;
}

.import-label {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.mini {
  padding: 0.2rem 0.45rem;
  font-size: 0.78rem;
}

.ver-table {
  width: 100%;
  font-size: 0.88rem;
  border-collapse: collapse;
}

.ver-table th,
.ver-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.45rem 0.35rem;
  text-align: left;
}
</style>

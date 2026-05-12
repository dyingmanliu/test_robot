<template>
  <div class="runs-page">
    <header class="head">
      <div>
        <h1>执行历史</h1>
        <p v-if="project" class="sub">
          {{ project.name }} · 日志来自数据库持久化的 step_log，可随时回看
        </p>
      </div>
      <div class="head-actions">
        <router-link
          v-if="projectId"
          class="btn"
          :to="{ name: 'projectDashboard', params: { projectId: projectId } }"
        >
          项目看板
        </router-link>
        <router-link to="/projects" class="btn ghost">所有项目</router-link>
      </div>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading && !runs.length" class="muted">加载中…</p>

    <div v-else class="table-wrap card">
      <table class="tbl">
        <thead>
          <tr>
            <th>执行 ID</th>
            <th>用例</th>
            <th>机器人实例</th>
            <th>状态</th>
            <th>识别步数</th>
            <th>开始</th>
            <th>结束</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in runs" :key="r.id">
            <td>{{ r.id }}</td>
            <td class="title-cell">{{ r.case_title || "—" }}</td>
            <td class="muted small">{{ r.robot_instance_code || "—" }}</td>
            <td><span class="pill" :class="statusClass(r.status)">{{ r.status }}</span></td>
            <td>{{ r.recognition_steps }}</td>
            <td class="muted small">{{ fmt(r.started_at) }}</td>
            <td class="muted small">{{ fmt(r.finished_at) }}</td>
            <td>
              <button type="button" class="btn tiny" @click="openDetail(r.id)">查看日志</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!runs.length" class="muted empty">该项目尚无执行记录。</p>
      <div v-if="runs.length" class="pager">
        <button type="button" class="btn" :disabled="offset === 0 || loading" @click="prevPage">
          上一页
        </button>
        <span class="muted small">每页 {{ pageSize }} 条</span>
        <button type="button" class="btn" :disabled="!hasMore || loading" @click="nextPage">
          下一页
        </button>
      </div>
    </div>

    <div v-if="detail.open" class="modal-overlay" @click.self="detail.open = false">
      <div class="modal wide">
        <h3>执行 #{{ detail.runId }} 日志</h3>
        <p v-if="detail.err" class="err">{{ detail.err }}</p>
        <p v-else-if="detail.loading" class="muted">加载中…</p>
        <pre v-else class="log-body">{{ detail.text }}</pre>
        <div class="modal-actions">
          <button type="button" class="btn primary" @click="detail.open = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => parseInt(String(route.params.projectId), 10));

const project = ref(null);
const runs = ref([]);
const loading = ref(false);
const error = ref("");
const offset = ref(0);
const pageSize = 50;
const hasMore = ref(false);

const detail = reactive({
  open: false,
  runId: null,
  loading: false,
  text: "",
  err: "",
});

function fmt(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statusClass(s) {
  if (s === "success") return "ok";
  if (s === "failed") return "bad";
  if (s === "cancelled") return "warn";
  return "";
}

async function loadProject() {
  const pid = projectId.value;
  if (Number.isNaN(pid)) throw new Error("无效的项目 ID");
  const { data } = await client.get(`/api/projects/${pid}`);
  project.value = data;
}

async function loadRuns() {
  loading.value = true;
  error.value = "";
  try {
    const pid = projectId.value;
    if (Number.isNaN(pid)) throw new Error("无效的项目 ID");
    const { data } = await client.get("/api/test-cases/runs", {
      params: { project_id: pid, limit: pageSize, offset: offset.value },
    });
    runs.value = data;
    hasMore.value = data.length === pageSize;
  } catch (e) {
    error.value = formatApiError(e);
    runs.value = [];
    hasMore.value = false;
  } finally {
    loading.value = false;
  }
}

function nextPage() {
  if (!hasMore.value) return;
  offset.value += pageSize;
  loadRuns();
}

function prevPage() {
  if (offset.value === 0) return;
  offset.value = Math.max(0, offset.value - pageSize);
  loadRuns();
}

async function openDetail(runId) {
  detail.open = true;
  detail.runId = runId;
  detail.loading = true;
  detail.text = "";
  detail.err = "";
  try {
    const { data } = await client.get(`/api/test-cases/runs/${runId}`);
    detail.text = data.step_log || data.output_message || "(无 step_log)";
  } catch (e) {
    detail.err = formatApiError(e);
  } finally {
    detail.loading = false;
  }
}

onMounted(async () => {
  offset.value = 0;
  try {
    await loadProject();
    await loadRuns();
  } catch (e) {
    error.value = formatApiError(e);
  }
});
</script>

<style scoped>
.runs-page {
  max-width: 960px;
}

.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.25rem;
  flex-wrap: wrap;
}

.head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.45rem;
}

.sub {
  margin: 0;
  font-size: 0.9rem;
  color: #64748b;
}

.head-actions {
  display: flex;
  gap: 0.5rem;
}

.btn.ghost {
  text-decoration: none;
  color: #334155;
}

.banner.err {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
  margin-bottom: 1rem;
}

.card {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.table-wrap {
  padding: 0;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.tbl th,
.tbl td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.tbl th {
  background: #f8fafc;
  color: #64748b;
  font-weight: 600;
  font-size: 0.8rem;
}

.title-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pill {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  font-size: 0.78rem;
  background: #f1f5f9;
  color: #475569;
}

.pill.ok {
  background: #ecfdf5;
  color: #047857;
}

.pill.bad {
  background: #fef2f2;
  color: #b91c1c;
}

.pill.warn {
  background: #fffbeb;
  color: #b45309;
}

.btn.tiny {
  padding: 0.35rem 0.55rem;
  font-size: 0.8rem;
}

.small {
  font-size: 0.82rem;
}

.empty {
  padding: 2rem;
  text-align: center;
}

.pager {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.85rem 1rem;
  border-top: 1px solid #f1f5f9;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 40;
  padding: 1rem;
}

.modal {
  background: #fff;
  padding: 1.25rem;
  border-radius: 12px;
  max-width: 560px;
  width: 100%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

.modal.wide {
  max-width: 720px;
}

.modal h3 {
  margin-top: 0;
}

.log-body {
  flex: 1;
  overflow: auto;
  margin: 0.5rem 0 0;
  padding: 0.75rem;
  background: #f8fafc;
  color: #334155;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.78rem;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 55vh;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
}
</style>

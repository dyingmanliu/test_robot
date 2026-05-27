<template>
  <div class="pdboard">
    <header class="head">
      <div>
        <h1>项目看板</h1>
        <p v-if="project" class="sub">
          {{ project.name }} · 被测应用：{{ project.tested_app_name }}
        </p>
      </div>
      <div class="head-actions">
        <router-link
          v-if="projectId"
          class="btn"
          :to="{ name: 'cases', query: { project: projectId } }"
        >
          用例列表
        </router-link>
        <router-link
          v-if="projectId"
          class="btn"
          :to="{ name: 'projectRunsHistory', params: { projectId } }"
        >
          执行历史
        </router-link>
        <router-link
          v-if="projectId"
          class="btn"
          :to="{ name: 'projectKnowledge', params: { projectId } }"
        >
          知识库
        </router-link>
        <router-link to="/projects" class="btn ghost">所有项目</router-link>
      </div>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-else-if="board">
      <section class="grid">
        <div class="card metric">
          <span class="label">累计执行任务数</span>
          <strong>{{ board.metrics.total_task_runs }}</strong>
          <span class="hint">全历史该项目下 TestRun 条数</span>
        </div>
        <div class="card metric">
          <span class="label">近 30 天执行次数</span>
          <strong>{{ board.metrics.runs_last_30_days }}</strong>
          <span class="hint">开始或结束时间落在近 30 天</span>
        </div>
        <div class="card metric">
          <span class="label">成功次数</span>
          <strong>{{ board.metrics.success_runs ?? 0 }}</strong>
          <span class="hint">status = success</span>
        </div>
        <div class="card metric">
          <span class="label">失败次数</span>
          <strong>{{ board.metrics.failed_runs ?? 0 }}</strong>
          <span class="hint">status = failed</span>
        </div>
        <div class="card metric">
          <span class="label">识别步数合计</span>
          <strong>{{ board.metrics.total_recognition_steps ?? 0 }}</strong>
          <span class="hint">全部执行的 step_log 非空行数之和</span>
        </div>
        <div class="card metric">
          <span class="label">进行中 / 排队</span>
          <strong>{{ board.metrics.pending_or_running_runs ?? 0 }}</strong>
          <span class="hint">pending / running</span>
        </div>
      </section>

      <section v-if="caseStats.length" class="card block">
        <h2>用例执行看板</h2>
        <p class="muted small">
          按用例汇总执行次数、成功次数与识别步数（与单次执行的 step_log 行数一致）。
        </p>
        <div class="table-wrap">
          <table class="tbl">
            <thead>
              <tr>
                <th>用例</th>
                <th>执行次数</th>
                <th>成功次数</th>
                <th>识别步数</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in caseStats" :key="row.case_id">
                <td class="title-cell">{{ row.title }}</td>
                <td>{{ row.run_count }}</td>
                <td>{{ row.success_count }}</td>
                <td>{{ row.recognition_steps }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card block">
        <h2>最新测试报告摘要</h2>
        <p v-if="board.latest_report.placeholder" class="muted box">
          {{ board.latest_report.hint || "暂无报告摘要" }}
        </p>
        <div v-else class="box">
          <p class="report-meta muted small">
            {{ board.latest_report.generated_at }}
          </p>
          <pre class="report-body">{{ board.latest_report.summary }}</pre>
        </div>
      </section>

      <section class="card block">
        <h2>活跃数字机器人</h2>
        <ul class="robots">
          <li v-for="r in board.active_robots" :key="r.id">
            <strong>{{ r.name }}</strong>
            <span class="muted small">{{ r.id }}</span>
            <div class="muted small">
              最近执行：
              {{ r.last_used_at || "暂无记录" }}
            </div>
            <div v-if="r.catalog_note" class="muted tiny">{{ r.catalog_note }}</div>
          </li>
        </ul>
      </section>

      <section class="card block trend">
        <h2>{{ board.defect_trend.title }}</h2>
        <p class="muted small">{{ board.defect_trend.note }}</p>
        <div class="chart-wrap">
          <svg
            class="chart"
            :viewBox="`0 0 ${chartW} ${chartH}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <polyline
              fill="none"
              stroke="#2563eb"
              stroke-width="2"
              :points="linePoints"
            />
            <g v-for="(v, i) in board.defect_trend.open_backlog_series" :key="i">
              <circle :cx="pointX(i)" :cy="pointY(v)" r="4" fill="#2563eb" />
            </g>
          </svg>
          <div class="xlabels">
            <span v-for="(lb, i) in board.defect_trend.labels" :key="lb + i" class="xl">{{ lb }}</span>
          </div>
        </div>
        <div class="bars">
          <div
            v-for="(v, i) in board.defect_trend.open_backlog_series"
            :key="'b' + i"
            class="bar-wrap"
          >
            <div class="bar" :style="{ height: barHeight(v) + '%' }" />
            <span class="bv">{{ v }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => parseInt(String(route.params.projectId), 10));

const project = ref(null);
const board = ref(null);
const loading = ref(true);
const error = ref("");

const caseStats = computed(() => board.value?.case_execution_stats || []);

const chartW = 640;
const chartH = 200;
const pad = 24;

const maxY = computed(() => {
  const s = board.value?.defect_trend?.open_backlog_series || [];
  const m = Math.max(1, ...s);
  return m;
});

function pointX(i) {
  const n = board.value?.defect_trend?.open_backlog_series?.length || 14;
  if (n <= 1) return chartW / 2;
  return pad + (i * (chartW - 2 * pad)) / (n - 1);
}

function pointY(v) {
  const h = chartH - 2 * pad;
  return pad + h - (v / maxY.value) * h;
}

const linePoints = computed(() => {
  const s = board.value?.defect_trend?.open_backlog_series;
  if (!s?.length) return "";
  return s.map((v, i) => `${pointX(i)},${pointY(v)}`).join(" ");
});

function barHeight(v) {
  return Math.round((v / maxY.value) * 100);
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const pid = projectId.value;
    if (Number.isNaN(pid)) throw new Error("无效的项目 ID");
    const [{ data: p }, { data: d }] = await Promise.all([
      client.get(`/api/projects/${pid}`),
      client.get(`/api/projects/${pid}/dashboard`),
    ]);
    project.value = p;
    board.value = d;
  } catch (e) {
    error.value = formatApiError(e);
    board.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.pdboard {
  max-width: 900px;
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
  color: #0f172a;
}

.sub {
  margin: 0;
  font-size: 0.9rem;
  color: #64748b;
}

.head-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
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
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.card.metric {
  padding: 1.1rem 1.25rem;
}

.metric .label {
  display: block;
  font-size: 0.82rem;
  color: #64748b;
}

.metric strong {
  font-size: 1.75rem;
  display: block;
  margin: 0.35rem 0;
}

.metric .hint {
  font-size: 0.75rem;
  color: #94a3b8;
}

.block {
  margin-bottom: 1rem;
  padding: 1.25rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.block h2 {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
}

.box {
  margin: 0;
}

.report-body {
  margin: 0.5rem 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.9rem;
  line-height: 1.5;
}

.robots {
  list-style: none;
  padding: 0;
  margin: 0;
}

.robots li {
  padding: 0.65rem 0;
  border-bottom: 1px solid #f1f5f9;
}

.robots li:last-child {
  border-bottom: none;
}

.tiny {
  font-size: 0.72rem;
}

.chart-wrap {
  margin-top: 0.75rem;
}

.chart {
  width: 100%;
  height: 200px;
  background: #f8fafc;
  border-radius: 8px;
}

.xlabels {
  display: flex;
  justify-content: space-between;
  margin-top: 0.35rem;
  font-size: 0.65rem;
  color: #94a3b8;
}

.xl {
  flex: 1;
  text-align: center;
}

.bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 100px;
  margin-top: 1rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e2e8f0;
}

.bar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
}

.bar {
  width: 100%;
  max-width: 24px;
  background: linear-gradient(180deg, #93c5fd, #2563eb);
  border-radius: 4px 4px 0 0;
  min-height: 2px;
}

.bv {
  font-size: 0.65rem;
  color: #64748b;
}

.table-wrap {
  overflow-x: auto;
  margin-top: 0.75rem;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.tbl th,
.tbl td {
  padding: 0.55rem 0.65rem;
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
  max-width: 280px;
}
</style>

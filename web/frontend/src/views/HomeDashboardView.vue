<template>
  <div class="home-dash">
    <section class="hero tech-panel">
      <div class="hero-copy">
        <p class="eyebrow">工作台 · 测试资产总览</p>
        <h1>您好，{{ greetingName }}</h1>
        <p class="lead">
          以下为当前账号可见范围内的<strong>用例梳理</strong>与<strong>自动化执行数据</strong>摘要；支持数字机器人编排与持续回归。
        </p>
      </div>
      <div class="hero-actions">
        <router-link class="btn btn-primary glow" :to="{ name: 'cases' }">进入用例管理</router-link>
        <router-link class="btn btn-outline" :to="{ name: 'projects' }">项目空间</router-link>
        <router-link class="btn btn-outline" :to="{ name: 'robotMarketplace' }">机器人商城</router-link>
        <router-link class="btn btn-outline" :to="{ name: 'myRentalApplications' }">租用申请</router-link>
        <router-link class="btn btn-outline" :to="{ name: 'myRobots' }">我的机器人</router-link>
      </div>
    </section>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted loading-msg">加载工作台数据…</p>

    <template v-else-if="summary">
      <section class="metrics-grid">
        <article class="metric-card tech-panel">
          <span class="metric-icon" aria-hidden="true">◇</span>
          <div class="metric-body">
            <span class="metric-label">项目空间</span>
            <strong class="metric-value">{{ summary.projects }}</strong>
            <span class="metric-hint">可创建多个空间隔离应用与目标</span>
          </div>
        </article>
        <article class="metric-card tech-panel">
          <span class="metric-icon" aria-hidden="true">◎</span>
          <div class="metric-body">
            <span class="metric-label">测试用例</span>
            <strong class="metric-value">{{ summary.test_cases }}</strong>
            <span class="metric-hint">近 7 日有更新 {{ summary.cases_updated_last_7_days ?? 0 }} 条</span>
          </div>
        </article>
        <article class="metric-card tech-panel accent">
          <span class="metric-icon" aria-hidden="true">▸</span>
          <div class="metric-body">
            <span class="metric-label">执行记录</span>
            <strong class="metric-value">{{ summary.test_runs }}</strong>
            <span class="metric-hint">成功 {{ summary.runs_success ?? 0 }} · 失败 {{ summary.runs_failed ?? 0 }}</span>
          </div>
        </article>
        <article class="metric-card tech-panel">
          <span class="metric-icon" aria-hidden="true">⌁</span>
          <div class="metric-body">
            <span class="metric-label">识别推理步数</span>
            <strong class="metric-value">{{ summary.total_recognition_steps ?? 0 }}</strong>
            <span class="metric-hint">累计 step_log 推理步（Agent）</span>
          </div>
        </article>
        <article class="metric-card tech-panel">
          <span class="metric-icon" aria-hidden="true">%</span>
          <div class="metric-body">
            <span class="metric-label">执行成功率</span>
            <strong class="metric-value">{{ successRateText }}</strong>
            <span class="metric-hint">成功 / 已结束执行（不含排队中）</span>
          </div>
        </article>
        <article class="metric-card tech-panel">
          <span class="metric-icon" aria-hidden="true">⟳</span>
          <div class="metric-body">
            <span class="metric-label">进行中 / 排队</span>
            <strong class="metric-value">{{ summary.runs_pending_or_running ?? 0 }}</strong>
            <span class="metric-hint">取消 {{ summary.runs_cancelled ?? 0 }}</span>
          </div>
        </article>
      </section>

      <div class="two-col">
        <section class="tech-panel block">
          <header class="block-head">
            <h2>优先级分布</h2>
            <span class="scope-badge">{{ summary.scope === "global" ? "全平台" : "本租户" }}</span>
          </header>
          <ul class="prio-list">
            <li v-for="row in priorityRows" :key="row.label">
              <span class="prio-label">{{ row.label }}</span>
              <div class="prio-bar-wrap">
                <div class="prio-bar" :style="{ width: row.pct + '%' }" />
              </div>
              <span class="prio-num">{{ row.count }}</span>
            </li>
            <li v-if="!priorityRows.length" class="muted empty-inline">尚无优先级数据</li>
          </ul>
        </section>

        <section class="tech-panel block">
          <header class="block-head">
            <h2>项目空间一览</h2>
            <router-link class="text-link" :to="{ name: 'projects' }">管理 →</router-link>
          </header>
          <ul class="proj-mini">
            <li v-for="p in projectsTop" :key="p.id">
              <div class="proj-mini-main">
                <strong>{{ p.name }}</strong>
                <span class="muted tiny">{{ p.tested_app_name }}</span>
              </div>
              <div class="proj-mini-meta">
                <span class="pill">{{ p.test_case_count ?? 0 }} 用例</span>
                <router-link
                  class="mini-link"
                  :to="{ name: 'cases', query: { project: p.id } }"
                >
                  打开
                </router-link>
              </div>
            </li>
            <li v-if="!projects.length" class="muted empty-inline">暂无项目，请先创建项目空间</li>
          </ul>
        </section>
      </div>

      <section class="tech-panel block">
        <header class="block-head">
          <h2>最近维护的用例</h2>
          <router-link class="text-link" :to="{ name: 'cases' }">全部用例 →</router-link>
        </header>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>优先级</th>
                <th>项目</th>
                <th>最近更新</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in recentCases" :key="c.id">
                <td class="title-cell">{{ c.title }}</td>
                <td><span class="pill sm">{{ c.priority || "—" }}</span></td>
                <td class="muted">{{ projectName(c.project_id) }}</td>
                <td class="muted small">{{ fmt(c.updated_at) }}</td>
              </tr>
              <tr v-if="!recentCases.length">
                <td colspan="4" class="empty-cell muted">暂无数据，请新建项目并添加用例</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const summary = ref(null);
const projects = ref([]);
const cases = ref([]);
const loading = ref(true);
const error = ref("");

const greetingName = computed(() => auth.displayLabel || "用户");

const successRateText = computed(() => {
  const s = summary.value;
  if (!s) return "—";
  const done = (s.runs_success ?? 0) + (s.runs_failed ?? 0) + (s.runs_cancelled ?? 0);
  if (done <= 0) return "—";
  const pct = Math.round(((s.runs_success ?? 0) / done) * 1000) / 10;
  return `${pct}%`;
});

const priorityRows = computed(() => {
  const raw = summary.value?.cases_by_priority || {};
  const entries = Object.entries(raw).map(([label, count]) => ({ label, count }));
  const max = Math.max(1, ...entries.map((e) => e.count));
  return entries
    .sort((a, b) => b.count - a.count)
    .map((e) => ({ ...e, pct: Math.round((e.count / max) * 100) }));
});

const projectsTop = computed(() => projects.value.slice(0, 6));

const recentCases = computed(() => {
  const list = [...cases.value];
  list.sort((a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0));
  return list.slice(0, 10);
});

function projectName(pid) {
  const p = projects.value.find((x) => x.id === pid);
  return p ? p.name : "—";
}

function fmt(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [{ data: sum }, { data: plist }, { data: clist }] = await Promise.all([
      client.get("/api/dashboard/summary"),
      client.get("/api/projects"),
      client.get("/api/test-cases"),
    ]);
    summary.value = sum;
    projects.value = plist;
    cases.value = clist;
  } catch (e) {
    error.value = formatApiError(e);
    summary.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.home-dash {
  max-width: 1100px;
  margin: 0 auto;
}

.hero {
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.25rem;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  background: linear-gradient(135deg, #eff6ff 0%, #ffffff 72%);
  border: 1px solid #e2e8f0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent-soft);
  font-weight: 600;
}

.hero h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  max-width: 520px;
  font-size: 0.92rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.loading-msg {
  padding: 2rem;
  text-align: center;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 0.85rem;
  margin-bottom: 1rem;
}

.metric-card {
  display: flex;
  gap: 0.75rem;
  padding: 1rem 1.1rem;
  align-items: flex-start;
  min-height: 108px;
}

.metric-card.accent {
  border-color: #bfdbfe;
  background: linear-gradient(145deg, #ffffff 0%, #eff6ff 100%);
}

.metric-icon {
  font-size: 1.25rem;
  color: var(--accent);
  opacity: 0.85;
  line-height: 1;
}

.metric-body {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.metric-label {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 500;
}

.metric-value {
  font-size: 1.65rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1.15;
}

.metric-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.two-col {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.block {
  padding: 1.15rem 1.25rem;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.block-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.scope-badge {
  font-size: 0.7rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: var(--accent);
  font-weight: 600;
}

.text-link {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--accent);
  text-decoration: none;
}

.text-link:hover {
  text-decoration: underline;
}

.prio-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.prio-list li {
  display: grid;
  grid-template-columns: 52px 1fr 36px;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.55rem;
}

.prio-label {
  font-size: 0.82rem;
  color: var(--text-secondary);
}

.prio-bar-wrap {
  height: 8px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 999px;
  overflow: hidden;
}

.prio-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent), #38bdf8);
  min-width: 4px;
}

.prio-num {
  font-size: 0.85rem;
  font-weight: 600;
  text-align: right;
  color: var(--text-primary);
}

.proj-mini {
  list-style: none;
  margin: 0;
  padding: 0;
}

.proj-mini li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0;
  border-bottom: 1px solid var(--border-subtle);
}

.proj-mini li:last-child {
  border-bottom: none;
}

.proj-mini-main {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.proj-mini-main strong {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.proj-mini-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.pill {
  font-size: 0.72rem;
  padding: 0.2rem 0.45rem;
  border-radius: 6px;
  background: rgba(37, 99, 235, 0.1);
  color: var(--accent);
  font-weight: 600;
}

.pill.sm {
  font-size: 0.78rem;
}

.mini-link {
  font-size: 0.82rem;
  color: var(--accent);
  font-weight: 500;
  text-decoration: none;
}

.mini-link:hover {
  text-decoration: underline;
}

.tiny {
  font-size: 0.78rem;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.data-table th,
.data-table td {
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
}

.data-table th {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 600;
  background: rgba(37, 99, 235, 0.04);
}

.title-cell {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-weight: 500;
}

.empty-cell {
  text-align: center;
  padding: 1.5rem !important;
}

.empty-inline {
  padding: 0.5rem 0;
}

.banner.err {
  padding: 0.65rem 0.85rem;
  border-radius: var(--radius-md);
  background: rgba(185, 28, 28, 0.08);
  color: #991b1b;
  margin-bottom: 1rem;
}
</style>

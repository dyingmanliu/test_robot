<template>
  <div class="dash">
    <header class="page-head">
      <h1>数据看板</h1>
      <p class="hint">
        平台内置 RBAC：<strong>{{ roleLabel }}</strong
        >。TSE 与平台管理员查看<strong>全量</strong>统计；外部企业用户仅见<strong>本人项目空间</strong>数据。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>

    <div v-if="loading" class="muted">加载中…</div>

    <div v-else-if="summary" class="metrics">
      <div class="metric card">
        <span class="label">数据范围</span>
        <strong>{{ summary.scope === "global" ? "全平台" : "本租户" }}</strong>
      </div>
      <div class="metric card">
        <span class="label">项目空间数</span>
        <strong>{{ summary.projects }}</strong>
      </div>
      <div class="metric card">
        <span class="label">测试用例数</span>
        <strong>{{ summary.test_cases }}</strong>
      </div>
      <div class="metric card">
        <span class="label">执行记录数</span>
        <strong>{{ summary.test_runs }}</strong>
      </div>
      <div class="metric card">
        <span class="label">成功 / 失败</span>
        <strong>{{ summary.runs_success ?? 0 }} / {{ summary.runs_failed ?? 0 }}</strong>
      </div>
      <div class="metric card">
        <span class="label">识别步数累计</span>
        <strong>{{ summary.total_recognition_steps ?? 0 }}</strong>
      </div>
      <div class="metric card">
        <span class="label">近 7 日用例更新</span>
        <strong>{{ summary.cases_updated_last_7_days ?? 0 }}</strong>
      </div>
    </div>

    <section v-if="auth.role === 'enterprise'" class="card block">
      <h2>消费与报告</h2>
      <p class="muted small">外部企业用户仅可访问租户内的消费明细与报告（占位接口）。</p>
      <pre v-if="usageJson" class="pre">{{ usageJson }}</pre>
      <button type="button" class="btn" :disabled="usageLoading" @click="loadUsage">
        {{ usageLoading ? "加载中…" : "拉取租户用量占位数据" }}
      </button>
    </section>

    <section v-if="auth.role === 'platform_admin' || auth.role === 'tse'" class="card block">
      <h2>数字机器人（全量目录）</h2>
      <p class="muted small">内部角色可使用全部能力；企业租户侧为租用子集。</p>
      <pre v-if="catalogJson" class="pre">{{ catalogJson }}</pre>
      <button type="button" class="btn" :disabled="catalogLoading" @click="loadCatalog">
        {{ catalogLoading ? "加载中…" : "加载目录（GET /api/platform/robots/catalog）" }}
      </button>
    </section>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import { useAuthStore, ROLE_LABELS } from "@/stores/auth";

const auth = useAuthStore();
const summary = ref(null);
const loading = ref(true);
const error = ref("");
const catalogJson = ref("");
const catalogLoading = ref(false);
const usageJson = ref("");
const usageLoading = ref(false);

const roleLabel = computed(() => ROLE_LABELS[auth.role] || auth.role || "—");

async function loadSummary() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/dashboard/summary");
    summary.value = data;
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function loadCatalog() {
  catalogLoading.value = true;
  try {
    const { data } = await client.get("/api/platform/robots/catalog");
    catalogJson.value = JSON.stringify(data, null, 2);
  } catch (e) {
    catalogJson.value = formatApiError(e);
  } finally {
    catalogLoading.value = false;
  }
}

async function loadUsage() {
  usageLoading.value = true;
  try {
    const { data } = await client.get("/api/platform/enterprise/usage-report");
    usageJson.value = JSON.stringify(data, null, 2);
  } catch (e) {
    usageJson.value = formatApiError(e);
  } finally {
    usageLoading.value = false;
  }
}

onMounted(loadSummary);
</script>

<style scoped>
.dash {
  max-width: 720px;
}

.page-head h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
  color: #0f172a;
}

.hint {
  margin: 0 0 1rem;
  font-size: 0.88rem;
  line-height: 1.5;
  color: #64748b;
}

.banner.err {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.metric .label {
  display: block;
  font-size: 0.8rem;
  color: #64748b;
  margin-bottom: 0.35rem;
}

.metric strong {
  font-size: 1.35rem;
  color: #0f172a;
}

.card {
  padding: 1rem 1.25rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  color: #334155;
}

.block {
  margin-bottom: 1rem;
}

.block h2 {
  margin: 0 0 0.5rem;
  font-size: 1.05rem;
  color: #0f172a;
}

.small {
  font-size: 0.82rem;
}

.pre {
  margin: 0.75rem 0;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.78rem;
  overflow: auto;
  max-height: 200px;
  color: #334155;
}

.back {
  margin-top: 1rem;
}
</style>

<template>
  <div class="hist-page">
    <header class="page-head">
      <router-link class="back-link" :to="{ name: 'projects' }">← 项目空间</router-link>
      <router-link
        v-if="projectId"
        class="back-link"
        :to="{ name: 'projectFeatureAnalysis', params: { projectId } }"
        >功能点分析</router-link
      >
      <h1>功能树记录</h1>
      <p v-if="project" class="sub">{{ project.name }}</p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <section v-if="!loading" class="card">
      <h2>已确认功能树（{{ trees.length }}）</h2>
      <table v-if="trees.length" class="tbl">
        <thead>
          <tr>
            <th>版本</th>
            <th>应用</th>
            <th>确认时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t in trees" :key="t.id">
            <td>{{ t.version_label || `树 #${t.id}` }}</td>
            <td>{{ t.app_display_name || t.bundle_id || "—" }}</td>
            <td>{{ fmtDate(t.confirmed_at) }}</td>
            <td>
              <router-link
                class="btn link"
                :to="{ name: 'projectFeatureTreeDetail', params: { projectId, treeId: t.id } }"
                >查看</router-link
              >
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">暂无已确认功能树，请先在功能点分析页完成分析并确认。</p>
    </section>

    <section v-if="!loading" class="card">
      <h2>分析任务记录（{{ runs.length }}）</h2>
      <table v-if="runs.length" class="tbl">
        <thead>
          <tr>
            <th>ID</th>
            <th>应用</th>
            <th>平台</th>
            <th>状态</th>
            <th>功能项</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in runs" :key="r.id">
            <td>{{ r.id }}</td>
            <td>{{ r.app_display_name || r.bundle_id }}</td>
            <td>{{ r.device_platform }}</td>
            <td>{{ statusLabel(r.status) }}</td>
            <td>{{ r.feature_count ?? 0 }}</td>
            <td>{{ fmtDate(r.created_at) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="muted">暂无分析任务。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => Number(route.params.projectId));
const apiBase = computed(() => `/api/projects/${projectId.value}/feature-analysis`);

const project = ref(null);
const trees = ref([]);
const runs = ref([]);
const loading = ref(true);
const error = ref("");

function fmtDate(v) {
  if (!v) return "—";
  try {
    return new Date(v).toLocaleString();
  } catch {
    return String(v);
  }
}

function statusLabel(s) {
  const m = {
    pending: "排队",
    running: "进行中",
    success: "成功",
    failed: "失败",
    cancelled: "已取消",
  };
  return m[s] || s;
}

onMounted(async () => {
  loading.value = true;
  error.value = "";
  try {
    const [p, t, r] = await Promise.all([
      client.get(`/api/projects/${projectId.value}`),
      client.get(`${apiBase.value}/trees`),
      client.get(`${apiBase.value}/runs`),
    ]);
    project.value = p.data;
    trees.value = t.data || [];
    runs.value = r.data || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.hist-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
}
.back-link {
  margin-right: 1rem;
  font-size: 0.9rem;
  color: #2563eb;
  text-decoration: none;
}
.page-head h1 {
  margin: 0.5rem 0 0.25rem;
}
.sub {
  color: #64748b;
}
.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1rem;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.tbl th,
.tbl td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.45rem 0.5rem;
  text-align: left;
}
.btn.link {
  text-decoration: none;
  color: #2563eb;
}
.banner.err {
  background: #fef2f2;
  color: #991b1b;
  padding: 0.65rem;
  border-radius: 8px;
}
.muted {
  color: #64748b;
}
</style>

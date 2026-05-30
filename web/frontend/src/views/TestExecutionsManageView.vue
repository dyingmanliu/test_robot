<template>
  <div class="exec-page">
    <header class="page-head">
      <h1>测试执行管理</h1>
      <p class="hint">
        按项目空间查看<strong>执行历史</strong>与 step_log 日志；请选择项目进入对应记录列表。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载项目列表…</p>

    <ul v-else class="proj-list">
      <li v-for="p in list" :key="p.id" class="proj-row card">
        <div class="proj-main">
          <strong>{{ p.name }}</strong>
          <span class="muted small">{{ p.tested_app_name }}</span>
        </div>
        <div class="proj-actions">
          <router-link
            class="btn primary"
            :to="{ name: 'projectRunsHistory', params: { projectId: p.id } }"
          >
            执行历史
          </router-link>
          <router-link class="btn ghost" :to="{ name: 'cases', query: { project: p.id } }">
            测试用例
          </router-link>
        </div>
      </li>
      <li v-if="!list.length" class="muted empty">暂无项目空间，请先在「项目空间管理」中创建。</li>
    </ul>

    <p class="foot-link">
      <router-link :to="{ name: 'projects' }">← 项目空间管理</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const list = ref([]);
const loading = ref(true);
const error = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/projects");
    list.value = data || [];
  } catch (e) {
    error.value = formatApiError(e);
    list.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.exec-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.45rem;
}

.hint {
  margin: 0 0 1.25rem;
  color: var(--text-secondary);
  line-height: 1.55;
  font-size: 0.92rem;
}

.proj-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.proj-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.15rem;
  flex-wrap: wrap;
}

.proj-main {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  min-width: 0;
}

.proj-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.empty {
  padding: 2rem;
  text-align: center;
}

.foot-link {
  margin-top: 1.25rem;
  font-size: 0.88rem;
}

.foot-link a {
  color: var(--accent);
  text-decoration: none;
}

.foot-link a:hover {
  text-decoration: underline;
}
</style>

<template>
  <div class="page">
    <header class="head">
      <h1>执行详情</h1>
      <p class="sub">实时查看测试执行进度、步骤日志与设备画面。</p>
      <nav class="nav-links">
        <router-link :to="{ name: 'myRobots' }">← 我的机器人</router-link>
        <router-link
          v-if="casesLink"
          :to="casesLink"
        >
          测试用例
        </router-link>
      </nav>
    </header>

    <p v-if="loadError" class="banner err">{{ loadError }}</p>
    <p v-else-if="loading" class="muted">加载执行记录…</p>

    <template v-else-if="liveRun">
      <p v-if="terminalHint" class="banner share-hint">{{ terminalHint }}</p>
      <RunLivePanel ref="panelRef" />
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { storeToRefs } from "pinia";
import RunLivePanel from "@/components/RunLivePanel.vue";
import { useActiveTestRunStore, getActiveRunProjectId } from "@/stores/activeTestRun";
import { statusLabel } from "@/utils/runLive";

const route = useRoute();
const activeRunStore = useActiveTestRunStore();
const { liveRun } = storeToRefs(activeRunStore);

const loading = ref(true);
const loadError = ref("");
const panelRef = ref(null);

const casesLink = computed(() => {
  const project = getActiveRunProjectId();
  const runId = liveRun.value?.id || activeRunStore.runId;
  if (!project && !runId) return null;
  const q = {};
  if (project) q.project = project;
  if (runId) q.run = String(runId);
  return { name: "cases", query: q };
});

const terminalHint = computed(() => {
  const st = liveRun.value?.status;
  if (!st || st === "pending" || st === "running") return "";
  return `本次执行已结束（${statusLabel(st)}）。下方为最终步骤记录。`;
});

watch(
  () => liveRun.value?.step_log,
  () => {
    nextTick(() => panelRef.value?.scrollLiveLogToBottom?.());
  },
);

onMounted(async () => {
  const runId = Number(route.params.runId);
  if (!Number.isFinite(runId) || runId < 1) {
    loadError.value = "无效的运行 ID";
    loading.value = false;
    return;
  }
  try {
    const data = await activeRunStore.resumeIfNeeded(runId);
    if (!data) {
      loadError.value = "未找到该运行记录，或您无权查看。";
      return;
    }
    await nextTick();
    panelRef.value?.scrollLiveLogToBottom?.();
  } catch (e) {
    loadError.value = e.response?.data?.detail || String(e.message || e);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
}

.head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}

.sub {
  margin: 0 0 0.75rem;
  color: #64748b;
  font-size: 0.92rem;
}

.nav-links {
  display: flex;
  gap: 1rem;
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.nav-links a {
  color: #2563eb;
  text-decoration: none;
}

.nav-links a:hover {
  text-decoration: underline;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.banner.share-hint {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  color: #0c4a6e;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.muted {
  color: #64748b;
}
</style>

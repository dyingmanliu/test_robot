<template>
  <div class="tree-page">
    <header class="page-head">
      <router-link
        class="back-link"
        :to="{ name: 'projectFeatureAnalysisHistory', params: { projectId } }"
        >← 功能树记录</router-link
      >
      <h1>功能菜单树 · {{ tree?.version_label || "详情" }}</h1>
      <p v-if="tree" class="sub">
        {{ displayAppName }} · 确认于 {{ fmtDate(tree.confirmed_at) }}
        <span v-if="editing" class="mode-tag">编辑中</span>
        <span v-else class="mode-tag view">查看</span>
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <section v-if="tree && !loading" class="card">
      <div class="head-actions">
        <template v-if="editing">
          <span v-if="dirty" class="feedback warn">有未保存的修改</span>
          <button
            type="button"
            class="btn btn-primary action-btn"
            :disabled="saving"
            @click="saveEdit"
          >
            {{ saving ? "保存中…" : "保存修改" }}
          </button>
          <button
            type="button"
            class="btn btn-outline action-btn"
            :disabled="saving"
            @click="cancelEdit"
          >
            取消编辑
          </button>
        </template>
        <button v-else type="button" class="btn btn-primary action-btn" @click="enterEdit">
          编辑
        </button>
        <button
          type="button"
          class="btn btn-outline action-btn"
          :disabled="exporting"
          @click="exportExcel"
        >
          {{ exporting ? "导出中…" : "导出" }}
        </button>
        <span v-if="saveOk" class="feedback ok">{{ saveOk }}</span>
        <p v-if="saveErr" class="feedback err">{{ saveErr }}</p>
        <p v-if="exportErr" class="feedback err">{{ exportErr }}</p>
      </div>
      <FeatureAnalysisWorkbench
        ref="workbenchRef"
        :feature-json="tree.tree_json || ''"
        :app-display-name="displayAppName"
        :editable="editing"
        :freeze-json-reload="editing"
        :show-mirror="false"
        @change="onWorkbenchChange"
      />
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";
import FeatureAnalysisWorkbench from "@/components/FeatureAnalysisWorkbench.vue";
import { appDisplayNameFromTreeRecord } from "@/utils/featureTree";

const route = useRoute();
const projectId = computed(() => Number(route.params.projectId));
const treeId = computed(() => Number(route.params.treeId));
const apiBase = computed(() => `/api/projects/${projectId.value}/feature-analysis`);

const tree = ref(null);
const displayAppName = computed(() => appDisplayNameFromTreeRecord(tree.value) || "应用");
const workbenchRef = ref(null);
const loading = ref(true);
const error = ref("");
const editing = ref(false);
const dirty = ref(false);
const saving = ref(false);
const saveErr = ref("");
const saveOk = ref("");
const exporting = ref(false);
const exportErr = ref("");
let saveOkTimer = null;

function clearSaveFeedback() {
  saveOk.value = "";
  saveErr.value = "";
  if (saveOkTimer) {
    clearTimeout(saveOkTimer);
    saveOkTimer = null;
  }
}

function showSaveOk(msg = "已保存") {
  saveOk.value = msg;
  if (saveOkTimer) clearTimeout(saveOkTimer);
  saveOkTimer = setTimeout(() => {
    saveOk.value = "";
    saveOkTimer = null;
  }, 2500);
}

function fmtDate(v) {
  if (!v) return "—";
  return new Date(v).toLocaleString();
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get(`${apiBase.value}/trees/${treeId.value}`);
    tree.value = data;
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function reloadWorkbench() {
  await nextTick();
  workbenchRef.value?.reload?.();
}

function onWorkbenchChange() {
  if (editing.value) dirty.value = true;
}

function enterEdit() {
  editing.value = true;
  dirty.value = false;
  clearSaveFeedback();
}

async function cancelEdit() {
  if (dirty.value && !window.confirm("放弃未保存的修改？")) return;
  clearSaveFeedback();
  editing.value = false;
  dirty.value = false;
  await load();
  await reloadWorkbench();
}

async function exportExcel() {
  if (!tree.value) return;
  exporting.value = true;
  exportErr.value = "";
  try {
    const { data } = await client.get(`${apiBase.value}/trees/${treeId.value}/export`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    const ver = (tree.value.version_label || "export").replace(/[/\\]/g, "_");
    a.download = `${displayAppName.value}-${ver}-功能树导出.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    exportErr.value = formatApiError(e);
  } finally {
    exporting.value = false;
  }
}

async function saveEdit() {
  if (!tree.value || !workbenchRef.value?.getTreeJson) return;
  saving.value = true;
  saveErr.value = "";
  clearSaveFeedback();
  try {
    const { data } = await client.patch(`${apiBase.value}/trees/${treeId.value}`, {
      tree_json: workbenchRef.value.getTreeJson(),
      bump_version: true,
    });
    tree.value = {
      ...tree.value,
      tree_json: data.tree_json,
      version_label: data.version_label,
      confirmed_at: data.confirmed_at,
      app_display_name: data.app_display_name,
    };
    editing.value = false;
    dirty.value = false;
    await reloadWorkbench();
    showSaveOk(`已保存为 ${data.version_label}`);
  } catch (e) {
    saveErr.value = formatApiError(e);
  } finally {
    saving.value = false;
  }
}

onMounted(load);

onUnmounted(() => {
  if (saveOkTimer) clearTimeout(saveOkTimer);
});
</script>

<style scoped>
.tree-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
}
.back-link {
  font-size: 0.9rem;
  color: #2563eb;
  text-decoration: none;
}
.page-head h1 {
  margin: 0.5rem 0 0.25rem;
}
.sub {
  color: #64748b;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.mode-tag {
  font-size: 0.75rem;
  padding: 0.1rem 0.45rem;
  border-radius: 4px;
  background: #fef3c7;
  color: #92400e;
}
.mode-tag.view {
  background: #e0f2fe;
  color: #0369a1;
}
.card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.15rem 1.25rem 1.25rem;
}
.head-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.85rem;
}
.head-actions .action-btn {
  min-width: 6.75rem;
  padding: 0.5rem 1.15rem;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.25;
  border-radius: 8px;
}
.feedback {
  margin: 0;
  font-size: 0.875rem;
}
.feedback.err {
  color: #b91c1c;
  width: 100%;
}
.feedback.ok {
  color: #166534;
}
.feedback.warn {
  color: #b45309;
}
.btn-outline {
  background: #fff;
  color: #334155;
  border: 1px solid #cbd5e1;
}
.btn-outline:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #94a3b8;
}
.btn-outline:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

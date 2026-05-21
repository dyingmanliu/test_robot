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
        {{ tree.app_display_name || tree.bundle_id }} · 确认于 {{ fmtDate(tree.confirmed_at) }}
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <section v-if="tree && !loading" class="card">
      <div class="head-actions">
        <button type="button" class="btn" :disabled="editing" @click="editing = !editing">
          {{ editing ? "取消编辑" : "编辑" }}
        </button>
      </div>
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>#</th>
              <th>完整路径</th>
              <th>区域</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in rows" :key="row._key">
              <td>{{ i + 1 }}</td>
              <td>
                <input v-if="editing" v-model="row.pathText" class="cell-input" type="text" />
                <span v-else>{{ row.pathText }}</span>
              </td>
              <td>
                <input v-if="editing" v-model="row.region" class="cell-input" type="text" />
                <span v-else>{{ row.region || "—" }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="!rows.length" class="muted">该版本无功能项数据。</p>
      <div v-if="editing" class="actions">
        <button type="button" class="btn primary" :disabled="saving" @click="saveEdit">
          {{ saving ? "保存中…" : "保存修改" }}
        </button>
      </div>
      <p v-if="saveErr" class="err">{{ saveErr }}</p>
      <p v-if="saveOk" class="ok">{{ saveOk }}</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => Number(route.params.projectId));
const treeId = computed(() => Number(route.params.treeId));
const apiBase = computed(() => `/api/projects/${projectId.value}/feature-analysis`);

const tree = ref(null);
const rows = ref([]);
const loading = ref(true);
const error = ref("");
const editing = ref(false);
const saving = ref(false);
const saveErr = ref("");
const saveOk = ref("");

function fmtDate(v) {
  if (!v) return "—";
  return new Date(v).toLocaleString();
}

function parseRows(treeJsonStr) {
  try {
    const data = JSON.parse(treeJsonStr || "{}");
    return (data.features || []).map((f, i) => ({
      _key: f.id || `r-${i}`,
      pathText: Array.isArray(f.path) ? f.path.join(" > ") : f.name || "",
      region: f.region || "",
    }));
  } catch {
    return [];
  }
}

function buildTreeJson() {
  const data = tree.value?.tree_json ? JSON.parse(tree.value.tree_json) : { features: [] };
  data.features = rows.value.map((row, i) => {
    const parts = row.pathText.split(">").map((s) => s.trim()).filter(Boolean);
    const name = parts.length ? parts[parts.length - 1] : row.pathText.trim();
    return {
      id: String(i + 1),
      name,
      path: parts.length ? parts : [name],
      depth: parts.length || 1,
      region: row.region || "other",
      status: "listed",
    };
  });
  return data;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get(`${apiBase.value}/trees/${treeId.value}`);
    tree.value = data;
    rows.value = parseRows(data.tree_json);
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function saveEdit() {
  saving.value = true;
  saveErr.value = "";
  saveOk.value = "";
  try {
    const { data } = await client.patch(`${apiBase.value}/trees/${treeId.value}`, {
      tree_json: buildTreeJson(),
      version_label: tree.value?.version_label || "",
    });
    tree.value = data;
    rows.value = parseRows(data.tree_json);
    editing.value = false;
    saveOk.value = "已保存";
  } catch (e) {
    saveErr.value = formatApiError(e);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.tree-page {
  max-width: 900px;
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
}
.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1rem;
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
}
.cell-input {
  width: 100%;
  padding: 0.35rem;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
}
.head-actions {
  margin-bottom: 0.75rem;
}
.actions {
  margin-top: 1rem;
}
.err {
  color: #b91c1c;
}
.ok {
  color: #166534;
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

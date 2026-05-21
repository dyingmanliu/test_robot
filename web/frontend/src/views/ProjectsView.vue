<template>
  <div class="projects-page">
    <header class="page-head">
      <h1>项目空间</h1>
      <p class="hint">
        每个项目空间绑定<strong>被测应用</strong>与<strong>测试目标</strong>，作为用例、执行记录与报告的聚合容器；数据按租户隔离，由项目服务 API 管理。
      </p>
    </header>

    <div class="toolbar">
      <button type="button" class="btn primary" @click="openCreate">新建项目空间</button>
      <router-link :to="{ name: 'cases' }" class="muted back-link">← 测试用例</router-link>
    </div>

    <p v-if="error" class="banner err">{{ error }}</p>

    <div v-if="loading" class="muted">加载中…</div>

    <div v-else class="cards">
      <article v-for="p in list" :key="p.id" class="card">
        <h2>{{ p.name }}</h2>
        <dl class="meta">
          <dt>被测应用</dt>
          <dd>{{ p.tested_app_name }}</dd>
          <dt>测试目标</dt>
          <dd class="obj">{{ p.test_objective || "—" }}</dd>
          <dt>测试用例</dt>
          <dd>{{ p.test_case_count ?? 0 }} 条</dd>
          <dt>已确认功能树</dt>
          <dd>{{ p.confirmed_feature_tree_count ?? 0 }} 版</dd>
        </dl>
        <div class="ops">
          <button type="button" class="btn" @click="openEdit(p)">编辑</button>
          <button type="button" class="btn danger" @click="remove(p)">删除</button>
          <router-link class="btn link" :to="{ name: 'projectDashboard', params: { projectId: p.id } }">
            项目看板
          </router-link>
          <router-link class="btn link" :to="{ name: 'projectRunsHistory', params: { projectId: p.id } }">
            执行历史
          </router-link>
          <router-link
            class="btn link"
            :to="{ name: 'functionalTaskWizard', params: { projectId: p.id } }"
            >功能测试任务</router-link
          >
          <router-link
            class="btn link"
            :to="{ name: 'cases', query: { project: p.id } }"
            >进入用例</router-link
          >
          <router-link
            class="btn link"
            :to="{ name: 'projectFeatureAnalysis', params: { projectId: p.id } }"
            >功能点分析</router-link
          >
          <router-link
            class="btn link"
            :to="{ name: 'projectFeatureAnalysisHistory', params: { projectId: p.id } }"
            >功能树记录</router-link
          >
        </div>
      </article>
      <p v-if="!list.length" class="muted empty">暂无项目，点击「新建项目空间」创建。</p>
    </div>

    <div v-if="dialog.open" class="modal-overlay" @click.self="dialog.open = false">
      <div class="modal">
        <h3>{{ dialog.editing ? "编辑项目空间" : "新建项目空间" }}</h3>
        <label class="field">
          <span>项目名称</span>
          <input v-model="dialog.name" maxlength="256" />
        </label>
        <label class="field">
          <span>被测应用</span>
          <input v-model="dialog.tested_app_name" maxlength="256" placeholder="应用名称或包名/标识" />
        </label>
        <label class="field">
          <span>测试目标</span>
          <textarea v-model="dialog.test_objective" rows="4" placeholder="范围、验收标准等"></textarea>
        </label>
        <p v-if="dialog.err" class="err">{{ dialog.err }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="dialog.open = false">取消</button>
          <button type="button" class="btn primary" @click="saveDialog">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const list = ref([]);
const loading = ref(false);
const error = ref("");

const dialog = reactive({
  open: false,
  editing: false,
  id: null,
  name: "",
  tested_app_name: "",
  test_objective: "",
  err: "",
});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/projects");
    list.value = data;
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  dialog.open = true;
  dialog.editing = false;
  dialog.id = null;
  dialog.name = "";
  dialog.tested_app_name = "";
  dialog.test_objective = "";
  dialog.err = "";
}

function openEdit(p) {
  dialog.open = true;
  dialog.editing = true;
  dialog.id = p.id;
  dialog.name = p.name;
  dialog.tested_app_name = p.tested_app_name;
  dialog.test_objective = p.test_objective || "";
  dialog.err = "";
}

async function saveDialog() {
  dialog.err = "";
  if (!dialog.name.trim() || !dialog.tested_app_name.trim()) {
    dialog.err = "请填写项目名称与被测应用";
    return;
  }
  try {
    const body = {
      name: dialog.name.trim(),
      tested_app_name: dialog.tested_app_name.trim(),
      test_objective: dialog.test_objective.trim(),
    };
    if (dialog.editing && dialog.id) {
      await client.patch(`/api/projects/${dialog.id}`, body);
    } else {
      await client.post("/api/projects", body);
    }
    dialog.open = false;
    await load();
  } catch (e) {
    dialog.err = formatApiError(e);
  }
}

async function remove(p) {
  if (!confirm(`确定删除项目「${p.name}」？（须先清空该项目下用例）`)) return;
  try {
    await client.delete(`/api/projects/${p.id}`);
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  }
}

onMounted(load);
</script>

<style scoped>
.projects-page {
  max-width: 900px;
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

.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.back-link {
  font-size: 0.9rem;
}

.banner.err {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
  margin-bottom: 1rem;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card {
  padding: 1.25rem;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  color: #334155;
}

.card h2 {
  margin: 0 0 0.75rem;
  font-size: 1.15rem;
  color: #0f172a;
}

.meta {
  margin: 0 0 1rem;
  display: grid;
  grid-template-columns: 88px 1fr;
  gap: 0.35rem 0.75rem;
  font-size: 0.9rem;
}

.meta dt {
  color: #64748b;
}

.obj {
  white-space: pre-wrap;
  word-break: break-word;
}

.ops {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.btn.danger {
  border-color: #fecaca;
  color: #b91c1c;
}

.btn.link {
  text-decoration: none;
  display: inline-flex;
  align-items: center;
}

.empty {
  padding: 2rem;
  text-align: center;
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

.field input,
.field textarea {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
  background: #fff;
  color: #0f172a;
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
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
  padding: 1.5rem;
  border-radius: 12px;
  max-width: 480px;
  width: 100%;
  border: 1px solid #e2e8f0;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.12);
}

.modal h3 {
  margin-top: 0;
  color: #0f172a;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}
</style>

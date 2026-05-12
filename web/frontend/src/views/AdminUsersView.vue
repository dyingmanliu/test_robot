<template>
  <div class="admin">
    <header class="page-head">
      <h1>用户与角色</h1>
      <p class="hint">
        平台管理员可为账号分配或变更 RBAC 角色；JWT 携带 <code>role</code> 声明供 API 网关与各微服务统一鉴权（变更后客户端会自动刷新令牌）。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>

    <div v-if="loading" class="muted">加载中…</div>

    <div v-else class="table-wrap card">
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>账号信息</th>
            <th>公司</th>
            <th>当前角色</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.id }}</td>
            <td class="who">
              <div>{{ u.nickname || "—" }}</div>
              <div class="muted small">{{ u.phone || u.email || u.username }}</div>
            </td>
            <td class="muted small">{{ u.company || "—" }}</td>
            <td>
              <select v-model="draft[u.id]" class="role-select">
                <option v-for="(text, rk) in roleLabels" :key="rk" :value="rk">{{ text }}</option>
              </select>
            </td>
            <td>
              <button type="button" class="btn primary" :disabled="saving[u.id]" @click="save(u.id)">
                {{ saving[u.id] ? "保存…" : "保存" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import { ROLE_LABELS } from "@/stores/auth";

const users = ref([]);
const draft = reactive({});
const saving = reactive({});
const loading = ref(true);
const error = ref("");
const roleLabels = ROLE_LABELS;

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/admin/users");
    users.value = data;
    for (const u of data) {
      draft[u.id] = u.role;
    }
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function save(userId) {
  saving[userId] = true;
  error.value = "";
  try {
    await client.patch(`/api/admin/users/${userId}/role`, { role: draft[userId] });
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    saving[userId] = false;
  }
}

load();
</script>

<style scoped>
.admin {
  max-width: 900px;
}

.page-head h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
}

.hint {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #475569;
}

.hint code {
  font-size: 0.8rem;
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.banner.err {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
}

.card {
  padding: 1rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.table-wrap {
  overflow: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.table th,
.table td {
  padding: 0.55rem 0.5rem;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}

.who .small {
  font-size: 0.78rem;
}

.role-select {
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font: inherit;
}

.back {
  margin-top: 1rem;
}
</style>

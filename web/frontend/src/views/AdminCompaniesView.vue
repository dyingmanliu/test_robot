<template>
  <div class="admin">
    <header class="page-head">
      <h1>公司与内部共享</h1>
      <p class="hint">
        项目空间与测试用例默认仅归属人可见；开启「公司内部共享」后，同一公司下的用户可查看同事的项目与用例（编辑与删除仍仅归属人）。租用机器人全公司可见，不受此开关影响。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else class="table-wrap card">
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>公司名称</th>
            <th>用户数</th>
            <th>项目/用例公司内部共享</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in rows" :key="c.id">
            <td>{{ c.id }}</td>
            <td>{{ c.name }}</td>
            <td>{{ c.user_count }}</td>
            <td>{{ c.share_projects_cases_internally ? "已开启" : "已关闭" }}</td>
            <td>
              <button
                type="button"
                class="btn primary"
                :disabled="saving[c.id]"
                @click="toggle(c)"
              >
                {{ saving[c.id] ? "保存中…" : c.share_projects_cases_internally ? "关闭共享" : "开启共享" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="back muted">
      <router-link to="/admin/users">← 用户与角色</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const rows = ref([]);
const loading = ref(true);
const error = ref("");
const saving = reactive({});

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/admin/companies");
    rows.value = data || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function toggle(c) {
  saving[c.id] = true;
  error.value = "";
  try {
    await client.patch(`/api/admin/companies/${c.id}/share-internal`, {
      share_projects_cases_internally: !c.share_projects_cases_internally,
    });
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    saving[c.id] = false;
  }
}

onMounted(load);
</script>

<style scoped>
.admin {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.45rem;
}

.hint {
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.9rem;
  line-height: 1.5;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
}

.table-wrap {
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.table th,
.table td {
  padding: 0.65rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.table th {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.back {
  margin-top: 1.25rem;
}

.muted {
  color: #64748b;
}
</style>

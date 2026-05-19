<template>
  <div class="admin">
    <header class="page-head">
      <h1>机器人实例</h1>
      <p class="hint">
        平台管理员可切换实例<strong>启动 / 停用</strong>。仅<strong>已启动且运行状态为空闲</strong>的实例可在测试用例页被选中执行。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else-if="instances.length" class="table-wrap card">
      <table class="table">
        <thead>
          <tr>
            <th>实例编号</th>
            <th>展示名称</th>
            <th>机器人类型</th>
            <th>实例状态</th>
            <th>运行状态</th>
            <th>执行引擎</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in instances" :key="r.id">
            <td class="mono">{{ r.instance_code }}</td>
            <td>{{ r.display_name || "—" }}</td>
            <td>{{ robotTypeLabel(r.catalog_robot_id) }}</td>
            <td>
              <span class="instance-pill" :class="`instance-pill--${instanceStatusClass(r.status)}`">
                {{ instanceStatusLabel(r.status) }}
              </span>
            </td>
            <td>
              <span class="runtime-pill" :class="`runtime-pill--${r.runtime_status || 'idle'}`">
                {{ runtimeStatusLabel(r.runtime_status) }}
              </span>
            </td>
            <td class="muted small">
              {{ engineLabel(r.test_agent_backend) }} · {{ platformLabel(r.device_platform) }}
            </td>
            <td class="ops">
              <button
                type="button"
                class="btn ghost mini"
                :disabled="saving[r.id] || r.status === 'active'"
                @click="setStatus(r, 'active')"
              >
                启动
              </button>
              <button
                type="button"
                class="btn ghost mini"
                :disabled="saving[r.id] || r.status === 'suspended'"
                @click="setStatus(r, 'suspended')"
              >
                停用
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else-if="!loading" class="muted empty-card">暂无机器人实例。</p>

    <p class="back muted">
      <router-link to="/admin/users">← 用户与角色</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import {
  instanceStatusClass,
  instanceStatusLabel,
  robotTypeLabel,
  runtimeStatusLabel,
} from "@/constants/robotCatalog";

const instances = ref([]);
const loading = ref(true);
const error = ref("");
const saving = reactive({});

function engineLabel(backend) {
  const b = String(backend || "autoglm").toLowerCase();
  return b === "midscene" ? "Midscene" : "AutoGLM";
}

function platformLabel(platform) {
  const p = String(platform || "android").toLowerCase();
  return p === "harmonyos" ? "鸿蒙" : "Android";
}

async function load(silent = false) {
  if (!silent) {
    loading.value = true;
    error.value = "";
  }
  try {
    const { data } = await client.get("/api/admin/robot-instances");
    instances.value = data || [];
  } catch (e) {
    if (!silent) error.value = formatApiError(e);
  } finally {
    if (!silent) loading.value = false;
  }
}

async function setStatus(row, status) {
  saving[row.id] = true;
  error.value = "";
  try {
    const { data } = await client.patch(`/api/admin/robot-instances/${row.id}/status`, {
      status,
    });
    const idx = instances.value.findIndex((x) => x.id === row.id);
    if (idx >= 0) instances.value[idx] = data;
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    saving[row.id] = false;
  }
}

let refreshTimer = null;

onMounted(() => {
  load();
  refreshTimer = setInterval(() => load(true), 5000);
});

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer);
});
</script>

<style scoped>
.admin {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}

.hint {
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.92rem;
  line-height: 1.5;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  overflow-x: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
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

.mono {
  font-family: ui-monospace, monospace;
  font-weight: 600;
  color: #1d4ed8;
}

.ops {
  white-space: nowrap;
  display: flex;
  gap: 0.35rem;
}

.btn.ghost.mini {
  font-size: 0.78rem;
  padding: 0.2rem 0.5rem;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.82rem;
}

.back {
  margin-top: 1.25rem;
}

.empty-card {
  padding: 1rem;
  color: #64748b;
}

.runtime-pill,
.instance-pill {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
}

.runtime-pill--executing {
  background: #dbeafe;
  color: #1d4ed8;
}

.runtime-pill--idle {
  background: #f1f5f9;
  color: #475569;
}

.runtime-pill--abnormal {
  background: #fee2e2;
  color: #b91c1c;
}

.instance-pill--started {
  background: #dcfce7;
  color: #166534;
}

.instance-pill--stopped {
  background: #f1f5f9;
  color: #64748b;
}
</style>

<template>
  <div class="page">
    <header class="head">
      <h1>租用审批</h1>
      <p class="sub">审批通过后系统按数量实例化并分配编号（DR-xxxxxx）；驳回需填写原因（可选）。</p>
    </header>

    <div class="toolbar">
      <button type="button" class="btn" :class="{ ghost: filterStatus !== '' }" @click="setFilter('')">全部</button>
      <button
        type="button"
        class="btn"
        :class="{ primary: filterStatus === 'pending_approval' }"
        @click="setFilter('pending_approval')"
      >
        待审批
      </button>
      <label class="agent-pick">
        <span class="agent-pick-label">通过时绑定</span>
        <select v-model="approveAgentBackend" class="agent-select">
          <option value="autoglm">AutoGLM（Android / ADB）</option>
          <option value="midscene">Midscene（HarmonyOS / HDC）</option>
        </select>
      </label>
      <button type="button" class="btn ghost" :disabled="loading" @click="load">刷新</button>
    </div>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else class="table-wrap">
      <table class="tbl">
        <thead>
          <tr>
            <th>单号</th>
            <th>用户</th>
            <th>机器人</th>
            <th>计费</th>
            <th>数量</th>
            <th>单价(分)</th>
            <th>合计(分)</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td>#{{ o.id }}</td>
            <td>{{ userLabel(o.user_id) }}</td>
            <td>{{ o.robot_name }}</td>
            <td>{{ o.billing_mode }}</td>
            <td>{{ o.quantity }}</td>
            <td>{{ o.unit_price_cents }}</td>
            <td>{{ o.total_cents }}</td>
            <td><span class="pill" :class="o.status">{{ o.status }}</span></td>
            <td class="ops">
              <template v-if="o.status === 'pending_approval'">
                <button type="button" class="btn tiny primary" :disabled="busyId === o.id" @click="approve(o.id)">
                  通过
                </button>
                <button type="button" class="btn tiny danger" :disabled="busyId === o.id" @click="openReject(o)">
                  驳回
                </button>
              </template>
              <span v-else class="muted small">—</span>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!orders.length" class="muted empty">暂无租用单。</p>
    </div>

    <div v-if="reject.open" class="overlay" @click.self="reject.open = false">
      <div class="modal card">
        <h3>驳回租用单 #{{ reject.orderId }}</h3>
        <label class="field">
          <span>原因（可选）</span>
          <textarea v-model="reject.reason" rows="3" />
        </label>
        <div class="actions">
          <button type="button" class="btn ghost" @click="reject.open = false">取消</button>
          <button type="button" class="btn danger" :disabled="reject.busy" @click="confirmReject">
            {{ reject.busy ? "提交中…" : "确认驳回" }}
          </button>
        </div>
      </div>
    </div>

    <p class="back muted">
      <router-link to="/admin/users">← 用户与角色</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const orders = ref([]);
const usersById = ref({});
const loading = ref(true);
const error = ref("");
const filterStatus = ref("pending_approval");
const busyId = ref(null);

/** 审批通过并实例化时写入机器人实例的测试引擎 */
const approveAgentBackend = ref("autoglm");

const reject = reactive({
  open: false,
  orderId: null,
  reason: "",
  busy: false,
});

function userLabel(uid) {
  const u = usersById.value[uid];
  return u ? `${u.username} (#${uid})` : `#${uid}`;
}

function setFilter(s) {
  filterStatus.value = s;
  load();
}

async function loadUsers() {
  try {
    const { data } = await client.get("/api/admin/users");
    const m = {};
    for (const u of data || []) m[u.id] = u;
    usersById.value = m;
  } catch {
    usersById.value = {};
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const params = {};
    if (filterStatus.value) params.status = filterStatus.value;
    const { data } = await client.get("/api/admin/rental-orders", { params });
    orders.value = data || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function approve(id) {
  busyId.value = id;
  error.value = "";
  try {
    await client.post(`/api/admin/rental-orders/${id}/approve`, {
      test_agent_backend: approveAgentBackend.value,
    });
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    busyId.value = null;
  }
}

function openReject(o) {
  reject.open = true;
  reject.orderId = o.id;
  reject.reason = "";
}

async function confirmReject() {
  if (!reject.orderId) return;
  reject.busy = true;
  error.value = "";
  try {
    await client.post(`/api/admin/rental-orders/${reject.orderId}/reject`, {
      reason: reject.reason || "",
    });
    reject.open = false;
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    reject.busy = false;
  }
}

onMounted(async () => {
  await loadUsers();
  await load();
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
}

.sub {
  color: #64748b;
  margin: 0 0 1rem;
}

.toolbar {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
  align-items: center;
}

.agent-pick {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.82rem;
  color: #475569;
}

.agent-pick-label {
  white-space: nowrap;
}

.agent-select {
  font-size: 0.82rem;
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem;
  border-radius: 8px;
}

.table-wrap {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.tbl th,
.tbl td {
  padding: 0.55rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.ops {
  white-space: nowrap;
}

.btn.tiny {
  padding: 0.25rem 0.5rem;
  font-size: 0.78rem;
  margin-right: 0.35rem;
}

.pill.pending_approval {
  background: #fef3c7;
  color: #92400e;
}

.pill.approved {
  background: #dcfce7;
  color: #166534;
}

.pill.rejected {
  background: #fee2e2;
  color: #991b1b;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgb(15 23 42 / 45%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.modal {
  max-width: 420px;
  width: 100%;
  padding: 1.25rem;
  border-radius: 12px;
  background: #fff;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin: 1rem 0;
  font-size: 0.85rem;
  color: #64748b;
}

.field textarea {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.empty {
  padding: 1rem;
}

.back {
  margin-top: 1.25rem;
}
</style>

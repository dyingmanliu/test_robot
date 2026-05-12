<template>
  <div class="page">
    <header class="head">
      <h1>租用申请清单</h1>
      <p class="sub">展示本公司范围内的租用申请（含同事提交）、账单金额与审批状态。</p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else-if="!orders.length" class="empty card">暂无租用申请。请前往「机器人商城」提交申请。</div>

    <div v-else class="table-wrap card">
      <table class="tbl">
        <thead>
          <tr>
            <th>单号</th>
            <th>申请人</th>
            <th>机器人</th>
            <th>计费</th>
            <th>数量</th>
            <th>合计</th>
            <th>状态</th>
            <th>提交时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.id">
            <td class="mono">#{{ o.id }}</td>
            <td class="mono small">{{ o.user_id }}</td>
            <td>
              <strong>{{ o.robot_name }}</strong>
              <span class="muted tiny block">{{ o.robot_id }}</span>
            </td>
            <td>{{ billingLabel(o.billing_mode) }}</td>
            <td>{{ o.quantity }}</td>
            <td>{{ formatPrice(o.total_cents, o.currency) }}</td>
            <td>
              <span class="pill" :class="statusClass(o.status)">{{ statusLabel(o.status) }}</span>
              <p v-if="o.status === 'rejected' && o.reject_reason" class="reject tiny">{{ o.reject_reason }}</p>
            </td>
            <td class="muted small">{{ fmt(o.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="back muted">
      <router-link :to="{ name: 'robotMarketplace' }">← 返回机器人商城</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const orders = ref([]);
const loading = ref(true);
const error = ref("");

function fmt(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function formatPrice(cents, cur) {
  const c = cur || "CNY";
  return `${c === "CNY" ? "¥" : c + " "}${(Number(cents) / 100).toFixed(2)}`;
}

function billingLabel(mode) {
  if (mode === "duration") return "按时长";
  if (mode === "count") return "按次数";
  return mode;
}

function statusLabel(s) {
  if (s === "pending_approval") return "待审批";
  if (s === "approved") return "已通过";
  if (s === "rejected") return "已驳回";
  return s;
}

function statusClass(s) {
  if (s === "pending_approval") return "pill--pending";
  if (s === "approved") return "pill--ok";
  if (s === "rejected") return "pill--bad";
  return "";
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/rentals/orders/mine");
    orders.value = data || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
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
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.92rem;
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

.empty {
  padding: 1.25rem;
  color: #64748b;
}

.table-wrap {
  overflow-x: auto;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.tbl th,
.tbl td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
  vertical-align: top;
}

.tbl th {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, monospace;
  font-weight: 600;
  color: #334155;
}

.block {
  display: block;
}

.pill {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  background: #f1f5f9;
  color: #475569;
}

.pill--pending {
  background: #fffbeb;
  color: #92400e;
}

.pill--ok {
  background: #ecfdf5;
  color: #065f46;
}

.pill--bad {
  background: #fef2f2;
  color: #991b1b;
}

.reject {
  margin: 0.35rem 0 0;
  color: #991b1b;
  max-width: 18rem;
}

.small {
  font-size: 0.82rem;
}

.tiny {
  font-size: 0.72rem;
}

.muted {
  color: #64748b;
}

.back {
  margin-top: 1.5rem;
}
</style>

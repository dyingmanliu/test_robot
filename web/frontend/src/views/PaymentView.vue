<template>
  <div class="pay">
    <header class="page-head">
      <h1>支付</h1>
      <p class="hint">预订单由计费模块生成后进入本页；以下为占位收银台，后续可对接统一支付网关。</p>
    </header>

    <p v-if="!preorderId" class="banner err">
      缺少预订单参数，请从<router-link to="/marketplace">机器人商城</router-link>发起租用。
    </p>

    <div v-else-if="loading" class="muted">加载预订单…</div>
    <p v-else-if="error" class="banner err">{{ error }}</p>

    <div v-else-if="detail" class="card settle">
      <h2>待支付预订单</h2>
      <dl class="rows">
        <div class="row">
          <dt>预订单号</dt>
          <dd>#{{ detail.id }}</dd>
        </div>
        <div class="row">
          <dt>数字机器人</dt>
          <dd>{{ detail.robot_name }}</dd>
        </div>
        <div class="row">
          <dt>计费方式</dt>
          <dd>{{ modeLabel(detail.billing_mode) }}</dd>
        </div>
        <div class="row">
          <dt>应付金额</dt>
          <dd class="amount">{{ formatMoney(detail.amount_cents, detail.currency) }}</dd>
        </div>
        <div class="row">
          <dt>状态</dt>
          <dd>
            <span :class="['status', detail.status]">{{ statusLabel(detail.status) }}</span>
          </dd>
        </div>
      </dl>
      <p class="muted note">
        真实环境中将跳转至支付渠道或展示聚合扫码；当前为演示闭环，预订单已写入后端 <code>billing_preorders</code> 表。
      </p>
      <div class="actions">
        <router-link to="/marketplace" class="btn">返回商城</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const preorderId = computed(() => {
  const raw = route.query.preorderId;
  if (raw === undefined || raw === null || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : null;
});

const loading = ref(false);
const error = ref("");
const detail = ref(null);

function formatMoney(cents, currency) {
  const cur = currency === "CNY" ? "¥" : `${currency} `;
  return `${cur}${(Number(cents) / 100).toFixed(2)}`;
}

function modeLabel(mode) {
  if (mode === "duration") return "按时长";
  if (mode === "count") return "按次数";
  return mode;
}

function statusLabel(s) {
  if (s === "pending_payment") return "待支付";
  if (s === "paid") return "已支付";
  if (s === "cancelled") return "已取消";
  return s;
}

async function load() {
  if (preorderId.value === null) {
    detail.value = null;
    return;
  }
  loading.value = true;
  error.value = "";
  detail.value = null;
  try {
    const { data } = await client.get(`/api/billing/preorders/${preorderId.value}`);
    detail.value = data;
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(preorderId, load);
</script>

<style scoped>
.pay {
  max-width: 560px;
  margin: 0 auto;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}

.hint {
  margin: 0 0 1rem;
  color: #475569;
  font-size: 0.95rem;
  line-height: 1.5;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
}

.card.settle {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.25rem 1.35rem;
}

.card.settle h2 {
  margin: 0 0 1rem;
  font-size: 1.15rem;
}

.rows {
  margin: 0;
}

.row {
  display: grid;
  grid-template-columns: 7rem 1fr;
  gap: 0.5rem;
  padding: 0.45rem 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.92rem;
}

.row:last-of-type {
  border-bottom: none;
}

dt {
  margin: 0;
  color: #64748b;
}

dd {
  margin: 0;
  color: #0f172a;
}

.amount {
  font-size: 1.15rem;
  font-weight: 700;
  color: #059669;
}

.status.pending_payment {
  color: #b45309;
}

.status.paid {
  color: #059669;
}

.note {
  margin: 1rem 0 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.note code {
  font-size: 0.8rem;
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.actions {
  margin-top: 1.25rem;
}

.muted {
  color: #64748b;
}
</style>

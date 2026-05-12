<template>
  <div class="mall">
    <header class="page-head">
      <h1>数字机器人商城</h1>
      <p class="hint">
        四大数字机器人覆盖<strong>测试分析</strong>、<strong>功能执行</strong>、<strong>专项执行</strong>与<strong>质量评估</strong>。
        选择计费模式与数量后提交租用申请，系统生成账单（暂不支付）；管理员审批通过后将自动实例化并分配编号。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="topSuccessMsg" class="banner ok top-flash">{{ topSuccessMsg }}</p>
    <div v-if="loading" class="muted">加载目录中…</div>

    <div v-else class="grid">
      <article v-for="r in robots" :key="r.id" class="robot-card">
        <div class="card-intro">
          <div class="card-intro-text">
            <span class="badge">{{ r.category }}</span>
            <h2>{{ r.name }}</h2>
          </div>
          <RobotMascotAvatar class="card-art" inline :robot-id="r.id" />
        </div>
        <section class="block">
          <h3>基础档案</h3>
          <p class="profile">{{ r.profile }}</p>
        </section>
        <section class="block">
          <h3>核心能力</h3>
          <ul>
            <li v-for="(c, i) in r.capabilities" :key="i">{{ c }}</li>
          </ul>
        </section>
        <section class="block billing">
          <h3>计费模式</h3>
          <div class="modes">
            <div class="mode">
              <span class="mode-label">{{ r.billing_modes.duration.label }}</span>
              <span class="price">{{ formatPrice(r.billing_modes.duration.price_cents) }}</span>
              <span class="unit">{{ r.billing_modes.duration.unit_label }}</span>
              <p class="mode-desc">{{ r.billing_modes.duration.description }}</p>
            </div>
            <div class="mode">
              <span class="mode-label">{{ r.billing_modes.count.label }}</span>
              <span class="price">{{ formatPrice(r.billing_modes.count.price_cents) }}</span>
              <span class="unit">{{ r.billing_modes.count.unit_label }}</span>
              <p class="mode-desc">{{ r.billing_modes.count.description }}</p>
            </div>
          </div>
        </section>
        <button type="button" class="btn primary rent" @click="openRent(r)">立即租用</button>
      </article>
    </div>

    <div v-if="dialogRobot" class="overlay" @click.self="closeDialog">
      <div class="dialog card">
        <h3>租用数字机器人</h3>
        <p class="muted small">{{ dialogRobot.name }}</p>
        <label class="radio-row">
          <input v-model="pickedMode" type="radio" value="duration" />
          <span
            ><strong>{{ dialogRobot.billing_modes.duration.label }}</strong> ·
            {{ formatPrice(dialogRobot.billing_modes.duration.price_cents) }} /
            {{ dialogRobot.billing_modes.duration.unit_label }}</span
          >
        </label>
        <label class="radio-row">
          <input v-model="pickedMode" type="radio" value="count" />
          <span
            ><strong>{{ dialogRobot.billing_modes.count.label }}</strong> ·
            {{ formatPrice(dialogRobot.billing_modes.count.price_cents) }} /
            {{ dialogRobot.billing_modes.count.unit_label }}</span
          >
        </label>
        <div class="qty-row">
          <label for="rent-qty">租用数量</label>
          <input
            id="rent-qty"
            v-model.number="rentQuantity"
            type="number"
            min="1"
            max="99"
            class="qty-input"
          />
        </div>
        <div v-if="dialogRobot" class="bill-box">
          <p><strong>账单预览</strong></p>
          <p class="bill-line">单价：{{ formatPrice(unitPriceCents) }} × {{ rentQuantity }} 台</p>
          <p class="bill-total">应付合计：<strong>{{ formatPrice(totalCents) }}</strong>（{{ billCurrency }}）</p>
          <p class="muted tiny">提交后进入「待审批」，无需在线支付；审批通过后在「我的机器人」中查看实例。</p>
        </div>
        <p v-if="submitErr" class="banner err tight">{{ submitErr }}</p>
        <div class="dialog-actions">
          <button type="button" class="btn ghost" @click="closeDialog">关闭</button>
          <button type="button" class="btn primary" :disabled="submitting" @click="confirmRent">
            {{ submitting ? "提交中…" : "提交租用申请" }}
          </button>
        </div>
      </div>
    </div>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import RobotMascotAvatar from "@/components/RobotMascotAvatar.vue";

const robots = ref([]);
const loading = ref(true);
const error = ref("");
const dialogRobot = ref(null);
const pickedMode = ref("duration");
const rentQuantity = ref(1);
const submitting = ref(false);
const submitErr = ref("");
const topSuccessMsg = ref("");

const unitPriceCents = computed(() => {
  const r = dialogRobot.value;
  if (!r) return 0;
  const m = pickedMode.value === "duration" ? r.billing_modes.duration : r.billing_modes.count;
  return Number(m?.price_cents) || 0;
});

const totalCents = computed(() => unitPriceCents.value * Math.max(1, Math.min(99, Number(rentQuantity.value) || 1)));

const billCurrency = "CNY";

function formatPrice(cents) {
  return `¥${(Number(cents) / 100).toFixed(2)}`;
}

async function loadCatalog() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/marketplace/robots");
    robots.value = data.robots || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

function openRent(r) {
  dialogRobot.value = r;
  pickedMode.value = "duration";
  rentQuantity.value = 1;
  submitErr.value = "";
}

function closeDialog() {
  dialogRobot.value = null;
}

async function confirmRent() {
  if (!dialogRobot.value) return;
  const qty = Math.max(1, Math.min(99, Number(rentQuantity.value) || 1));
  submitting.value = true;
  submitErr.value = "";
  try {
    const { data } = await client.post("/api/rentals/orders", {
      robot_id: dialogRobot.value.id,
      billing_mode: pickedMode.value,
      quantity: qty,
    });
    topSuccessMsg.value = `已提交租用单 #${data.id}，合计 ${formatPrice(data.total_cents)}；${data.message || "待管理员审批。"}`;
    closeDialog();
  } catch (e) {
    submitErr.value = formatApiError(e);
  } finally {
    submitting.value = false;
  }
}

onMounted(loadCatalog);
</script>

<style scoped>
.mall {
  max-width: 1120px;
  margin: 0 auto;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.65rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.hint {
  margin: 0 0 1.25rem;
  color: #475569;
  font-size: 0.95rem;
  line-height: 1.55;
}

.banner.ok.top-flash {
  margin-bottom: 1rem;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.banner.err.tight {
  margin-bottom: 0.75rem;
}

.banner.ok {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  color: #065f46;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  font-size: 0.88rem;
}

.banner.ok.tight {
  margin-bottom: 0.75rem;
}

.qty-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin: 0.85rem 0;
  font-size: 0.9rem;
  color: #334155;
}

.qty-input {
  width: 5rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.bill-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.75rem;
  font-size: 0.88rem;
}

.bill-box p {
  margin: 0.25rem 0;
}

.bill-total {
  font-size: 1rem;
  margin-top: 0.35rem !important;
}

.bill-line {
  color: #475569;
}

.grid {
  display: grid;
  /* 仅 4 列一行 或 2×2，避免出现 3+1（不用 auto-fill + minmax） */
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1.25rem;
}

@media (min-width: 1100px) {
  .grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.robot-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 0 0 1.25rem;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 4px 16px rgb(15 23 42 / 5%);
}

.card-intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 1rem 1.15rem 0.85rem;
  border-bottom: 1px solid #f1f5f9;
}

.card-intro-text {
  flex: 1;
  min-width: 0;
}

.card-art {
  flex-shrink: 0;
  margin: 0;
}

.badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 600;
  color: #1d4ed8;
  background: #eff6ff;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
}

.robot-card h2 {
  margin: 0.45rem 0 0;
  font-size: 1.05rem;
  line-height: 1.35;
  color: #0f172a;
}

.block {
  margin-top: 0.75rem;
  padding: 0 1.15rem;
}

.block h3 {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
}

.profile {
  margin: 0;
  font-size: 0.88rem;
  color: #334155;
  line-height: 1.5;
}

.block ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.88rem;
  color: #334155;
  line-height: 1.45;
}

.block li + li {
  margin-top: 0.25rem;
}

.billing .modes {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.mode {
  padding: 0.5rem 0.6rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.mode-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: #0f172a;
}

.price {
  display: inline-block;
  margin-left: 0.35rem;
  font-weight: 700;
  color: #059669;
}

.unit {
  font-size: 0.8rem;
  color: #64748b;
  margin-left: 0.25rem;
}

.mode-desc {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.4;
}

.rent {
  margin-top: auto;
  padding: 1rem 1.15rem 0;
  width: 100%;
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

.dialog {
  max-width: 420px;
  width: 100%;
  padding: 1.25rem 1.35rem;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 12px 40px rgb(15 23 42 / 18%);
}

.dialog h3 {
  margin: 0 0 0.25rem;
}

.radio-row {
  display: flex;
  gap: 0.5rem;
  align-items: flex-start;
  margin: 0.65rem 0;
  cursor: pointer;
  font-size: 0.9rem;
  color: #334155;
}

.radio-row input {
  margin-top: 0.2rem;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}

.back {
  margin-top: 1.5rem;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.85rem;
}
</style>

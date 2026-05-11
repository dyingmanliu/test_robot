<template>
  <div class="monitor">
    <header class="monitor-head">
      <div>
        <h1>运行监控 · 测试数字机器人</h1>
        <p class="sub">
          已实例化 {{ summary.instantiated_count ?? "—" }} 台 · 数据与 <code>test_runs</code> 及实例池对齐；支持实时推送与 HTTP 轮询兜底
        </p>
      </div>
      <div class="conn">
        <span :class="['dot', `phase-${connPhase}`]" />
        <span class="conn-label">{{ wsLabel }}</span>
        <span v-if="lastPayload?.updated_at" class="ts">{{ formatTs(lastPayload.updated_at) }}</span>
      </div>
    </header>

    <p v-if="httpError" class="banner err">{{ httpError }}</p>
    <p v-if="wsOnlyError" class="banner warn">{{ wsOnlyError }}</p>

    <section class="metrics">
      <div class="tile inst">
        <span class="tile-label">已实例化</span>
        <strong class="tile-val">{{ num(summary.instantiated_count) }}</strong>
        <span class="tile-unit">台</span>
      </div>
      <div class="tile exec">
        <span class="tile-label">执行中</span>
        <strong class="tile-val">{{ num(summary.executing_slots) }}</strong>
        <span class="tile-unit">台</span>
      </div>
      <div class="tile wait">
        <span class="tile-label">等待</span>
        <strong class="tile-val">{{ num(summary.waiting_slots) }}</strong>
        <span class="tile-unit">台</span>
      </div>
      <div class="tile idle">
        <span class="tile-label">待机</span>
        <strong class="tile-val">{{ num(summary.idle_slots) }}</strong>
        <span class="tile-unit">台</span>
      </div>
      <div class="tile off">
        <span class="tile-label">离线</span>
        <strong class="tile-val">{{ num(summary.offline_count) }}</strong>
        <span class="tile-unit">台</span>
      </div>
    </section>

    <section class="viz-row">
      <div class="donut-card card">
        <h2>状态占比</h2>
        <div class="donut-wrap">
          <div
            class="donut"
            :style="{ background: donutGradient }"
            role="img"
            :aria-label="donutAria"
          />
          <div class="donut-center">
            <strong>{{ totalFleet }}</strong>
            <span>总计展示</span>
          </div>
        </div>
        <ul class="donut-legend">
          <li><i class="lg executing" /> 执行中 {{ num(summary.executing_slots) }}</li>
          <li><i class="lg waiting" /> 等待 {{ num(summary.waiting_slots) }}</li>
          <li><i class="lg idle" /> 待机 {{ num(summary.idle_slots) }}</li>
          <li><i class="lg offline" /> 离线 {{ num(summary.offline_count) }}</li>
        </ul>
      </div>

      <div class="bar-card card">
        <h2>负载条带</h2>
        <div class="stack">
          <div
            class="seg executing"
            :style="{ flex: segFlex.executing }"
            :title="`执行中 ${summary.executing_slots ?? 0}`"
          />
          <div
            class="seg waiting"
            :style="{ flex: segFlex.waiting }"
            :title="`等待 ${summary.waiting_slots ?? 0}`"
          />
          <div
            class="seg idle"
            :style="{ flex: segFlex.idle }"
            :title="`待机 ${summary.idle_slots ?? 0}`"
          />
          <div
            class="seg offline"
            :style="{ flex: segFlex.offline }"
            :title="`离线 ${summary.offline_count ?? 0}`"
          />
        </div>
        <p class="hint-muted">
          后台任务：运行中 {{ summary.running_tasks ?? 0 }} · 排队 {{ summary.pending_tasks ?? 0 }}
        </p>
      </div>
    </section>

    <section class="card robots-section">
      <h2>实例一览</h2>
      <div class="robot-grid">
        <article
          v-for="r in robotsList"
          :key="r.id"
          class="robot-card"
          :class="`st-${r.status}`"
        >
          <div class="robot-top">
            <span class="robot-id">{{ r.id }}</span>
            <span class="badge" :class="`badge-${r.status}`">{{ r.label }}</span>
          </div>
          <p class="robot-name">{{ r.name }}</p>
          <p v-if="r.run_id" class="robot-meta">任务 #{{ r.run_id }}</p>
          <p v-else-if="r.status !== 'offline'" class="robot-meta muted">无关联任务</p>
          <p v-else class="robot-meta muted">未接入调度</p>
        </article>
      </div>
    </section>

    <p class="back">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const connPhase = ref("connecting");
const httpError = ref("");
const wsOnlyError = ref("");
const lastPayload = ref(null);
let socket = null;
let reconnectTimer = null;
let pollTimer = null;
let reconnectAttempt = 0;
let destroyed = false;
let allowReconnect = true;

const POLL_MS = 4000;

function mergePayload(data) {
  if (!data || data.type !== "robot_monitor") return;
  lastPayload.value = data;
  httpError.value = "";
}

const summary = computed(() => lastPayload.value || {});

const robotsList = computed(() => summary.value.robots || []);

const totalFleet = computed(() => {
  const s = summary.value;
  const ex = s.executing_slots ?? 0;
  const wa = s.waiting_slots ?? 0;
  const idl = s.idle_slots ?? 0;
  const off = s.offline_count ?? 0;
  return ex + wa + idl + off;
});

const segFlex = computed(() => {
  const s = summary.value;
  const ex = Math.max(0, s.executing_slots ?? 0);
  const wa = Math.max(0, s.waiting_slots ?? 0);
  const idl = Math.max(0, s.idle_slots ?? 0);
  const off = Math.max(0, s.offline_count ?? 0);
  const m = Math.max(1, ex + wa + idl + off);
  return {
    executing: Math.max(0.08, ex / m),
    waiting: Math.max(0.08, wa / m),
    idle: Math.max(0.08, idl / m),
    offline: Math.max(0.08, off / m),
  };
});

function pctSlice(count, total) {
  if (!total || !count) return 0;
  return (count / total) * 100;
}

const donutGradient = computed(() => {
  const s = summary.value;
  const ex = s.executing_slots ?? 0;
  const wa = s.waiting_slots ?? 0;
  const idl = s.idle_slots ?? 0;
  const off = s.offline_count ?? 0;
  const t = ex + wa + idl + off;
  if (!t) {
    return "conic-gradient(#e2e8f0 0% 100%)";
  }
  let a = 0;
  const p1 = a + pctSlice(ex, t);
  a = p1;
  const p2 = a + pctSlice(wa, t);
  a = p2;
  const p3 = a + pctSlice(idl, t);
  a = p3;
  const p4 = a + pctSlice(off, t);
  return `conic-gradient(
    #2563eb 0% ${p1}%,
    #f59e0b ${p1}% ${p2}%,
    #38bdf8 ${p2}% ${p3}%,
    #94a3b8 ${p3}% ${p4}%
  )`;
});

const donutAria = computed(() => {
  const s = summary.value;
  return `执行中${s.executing_slots ?? 0}，等待${s.waiting_slots ?? 0}，待机${s.idle_slots ?? 0}，离线${s.offline_count ?? 0}`;
});

const wsLabel = computed(() => {
  if (connPhase.value === "open") return "实时通道已连接";
  if (connPhase.value === "closed") return "实时通道断开（HTTP 轮询中）";
  return "正在连接实时通道…";
});

function num(v) {
  if (v === null || v === undefined) return "—";
  return v;
}

function formatTs(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

async function fetchSnapshot() {
  try {
    const { data } = await client.get("/api/monitor/robots");
    mergePayload(data);
    wsOnlyError.value = "";
  } catch (e) {
    httpError.value = formatApiError(e);
  }
}

function wsUrl() {
  const token = localStorage.getItem("tcm_token");
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const q = token ? `?token=${encodeURIComponent(token)}` : "?token=";
  return `${proto}//${host}/api/ws/monitor/robots${q}`;
}

function clearReconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function scheduleReconnect() {
  if (destroyed || !allowReconnect) return;
  clearReconnect();
  const delay = Math.min(30000, 1000 * 2 ** reconnectAttempt);
  reconnectTimer = window.setTimeout(() => {
    if (!destroyed && allowReconnect) connect();
  }, delay);
  reconnectAttempt += 1;
}

function detachSocketHandlers(ws) {
  if (!ws) return;
  ws.onopen = null;
  ws.onmessage = null;
  ws.onerror = null;
  ws.onclose = null;
}

function connect() {
  if (destroyed) return;
  clearReconnect();
  wsOnlyError.value = "";
  connPhase.value = "connecting";
  try {
    detachSocketHandlers(socket);
    socket?.close();
  } catch {
    /* noop */
  }
  let ws;
  try {
    ws = new WebSocket(wsUrl());
  } catch (e) {
    connPhase.value = "closed";
    wsOnlyError.value = "无法建立 WebSocket，将仅使用 HTTP 轮询";
    scheduleReconnect();
    return;
  }
  socket = ws;
  socket.onopen = () => {
    if (destroyed) return;
    connPhase.value = "open";
    reconnectAttempt = 0;
  };
  socket.onmessage = (ev) => {
    if (destroyed) return;
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "error") {
        allowReconnect = false;
        wsOnlyError.value = data.detail || "订阅失败";
        connPhase.value = "closed";
        clearReconnect();
        detachSocketHandlers(socket);
        try {
          socket?.close();
        } catch {
          /* noop */
        }
        socket = null;
        return;
      }
      if (data.type === "robot_monitor") {
        mergePayload(data);
      }
    } catch {
      /* ignore */
    }
  };
  socket.onerror = () => {
    if (destroyed) return;
    wsOnlyError.value = "WebSocket 异常，已降级为轮询";
  };
  socket.onclose = () => {
    if (destroyed) return;
    connPhase.value = "closed";
    detachSocketHandlers(socket);
    socket = null;
    if (allowReconnect) scheduleReconnect();
  };
}

onMounted(async () => {
  destroyed = false;
  allowReconnect = true;
  await fetchSnapshot();
  pollTimer = window.setInterval(fetchSnapshot, POLL_MS);
  connect();
});

onBeforeUnmount(() => {
  destroyed = true;
  allowReconnect = false;
  clearReconnect();
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  detachSocketHandlers(socket);
  try {
    socket?.close();
  } catch {
    /* noop */
  }
  socket = null;
});
</script>

<style scoped>
.monitor {
  min-height: calc(100vh - 3rem);
  padding: 1.25rem 1.5rem 2rem;
  background: linear-gradient(180deg, #eff6ff 0%, #f1f5fb 48%, #f8fafc 100%);
  color: #0f172a;
  width: 100%;
  box-sizing: border-box;
}

.monitor-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.monitor-head h1 {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 700;
  color: #0f172a;
}

.sub {
  margin: 0.35rem 0 0;
  font-size: 0.88rem;
  color: #64748b;
  max-width: 52rem;
  line-height: 1.5;
}

.sub code {
  font-size: 0.8rem;
  background: #f1f5f9;
  padding: 0.1rem 0.35rem;
  border-radius: 4px;
}

.conn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.88rem;
  color: #475569;
}

.conn .dot {
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 999px;
  background: #94a3b8;
}

.conn .dot.phase-connecting {
  background: #94a3b8;
}

.conn .dot.phase-open {
  background: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.28);
}

.conn .dot.phase-closed {
  background: #f97316;
}

.ts {
  font-variant-numeric: tabular-nums;
  color: #64748b;
}

.banner {
  padding: 0.65rem 0.85rem;
  border-radius: 10px;
  margin-bottom: 1rem;
  font-size: 0.9rem;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.banner.warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.85rem;
  margin-bottom: 1.25rem;
}

.tile {
  border-radius: 12px;
  padding: 1rem 1.1rem;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.tile-label {
  display: block;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #64748b;
  margin-bottom: 0.35rem;
}

.tile-val {
  font-size: clamp(1.75rem, 4vw, 2.5rem);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: #0f172a;
}

.tile.inst .tile-val {
  color: #1d4ed8;
}

.tile.exec .tile-val {
  color: #2563eb;
}

.tile.wait .tile-val {
  color: #d97706;
}

.tile.idle .tile-val {
  color: #0369a1;
}

.tile.off .tile-val {
  color: #64748b;
}

.tile-unit {
  margin-left: 0.25rem;
  font-size: 0.9rem;
  color: #94a3b8;
}

.viz-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.1rem 1.2rem;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.card h2 {
  margin: 0 0 0.85rem;
  font-size: 1rem;
  font-weight: 600;
  color: #0f172a;
}

.donut-wrap {
  position: relative;
  width: 11rem;
  height: 11rem;
  margin: 0 auto 1rem;
}

.donut {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.06);
}

.donut-center {
  position: absolute;
  inset: 22%;
  border-radius: 50%;
  background: #fff;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.donut-center strong {
  font-size: 1.35rem;
  font-weight: 800;
  color: #0f172a;
}

.donut-center span {
  font-size: 0.72rem;
  color: #64748b;
}

.donut-legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #475569;
}

.donut-legend i.lg {
  display: inline-block;
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 3px;
  margin-right: 0.4rem;
  vertical-align: middle;
}

.donut-legend i.executing {
  background: #2563eb;
}

.donut-legend i.waiting {
  background: #f59e0b;
}

.donut-legend i.idle {
  background: #38bdf8;
}

.donut-legend i.offline {
  background: #94a3b8;
}

.stack {
  display: flex;
  height: 2.5rem;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
}

.seg {
  min-width: 6px;
  transition: flex 0.35s ease;
}

.seg.executing {
  background: linear-gradient(180deg, #3b82f6, #2563eb);
}

.seg.waiting {
  background: linear-gradient(180deg, #fbbf24, #d97706);
}

.seg.idle {
  background: linear-gradient(180deg, #7dd3fc, #0284c7);
}

.seg.offline {
  background: linear-gradient(180deg, #cbd5e1, #64748b);
}

.hint-muted {
  margin: 0.65rem 0 0;
  font-size: 0.82rem;
  color: #64748b;
}

.robots-section {
  margin-bottom: 1rem;
}

.robot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 0.65rem;
}

.robot-card {
  border-radius: 10px;
  padding: 0.75rem 0.85rem;
  border: 1px solid #e2e8f0;
  background: #fafafa;
}

.robot-card.st-executing {
  border-color: #93c5fd;
  background: linear-gradient(145deg, #eff6ff 0%, #fff 100%);
}

.robot-card.st-waiting {
  border-color: #fcd34d;
  background: linear-gradient(145deg, #fffbeb 0%, #fff 100%);
}

.robot-card.st-idle {
  border-color: #7dd3fc;
  background: linear-gradient(145deg, #f0f9ff 0%, #fff 100%);
}

.robot-card.st-offline {
  border-color: #cbd5e1;
  background: #f1f5f9;
  opacity: 0.92;
}

.robot-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 0.35rem;
}

.robot-id {
  font-size: 0.72rem;
  font-family: ui-monospace, monospace;
  color: #64748b;
}

.badge {
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.15rem 0.4rem;
  border-radius: 6px;
}

.badge-executing {
  background: #dbeafe;
  color: #1d4ed8;
}

.badge-waiting {
  background: #fef3c7;
  color: #b45309;
}

.badge-idle {
  background: #e0f2fe;
  color: #0369a1;
}

.badge-offline {
  background: #e2e8f0;
  color: #475569;
}

.robot-name {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
}

.robot-meta {
  margin: 0.35rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
}

.robot-meta.muted {
  color: #94a3b8;
}

.back {
  margin-top: 1rem;
}

.back a {
  color: #2563eb;
  font-weight: 500;
}
</style>

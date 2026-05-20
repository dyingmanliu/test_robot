<template>
  <div v-if="liveRun" class="panel live-panel">
    <div class="panel-head">
      <h2>执行进度（实时）</h2>
      <button
        v-if="canStopRun"
        type="button"
        class="btn stop"
        :disabled="stopBusy"
        @click="stopRun"
      >
        {{ stopBusy ? "请求中…" : "停止执行" }}
      </button>
    </div>
    <div class="status-strip">
      <div class="status-strip-main">
        <p v-if="executionTaskLabel" class="status-task-line">
          <strong>执行任务：</strong>
          <span class="exec-task-name">{{ executionTaskLabel }}</span>
        </p>
        <span class="status-line">
          <strong>执行状态：</strong>
          <span class="badge inline" :class="liveRun.status">{{ statusLabel(liveRun.status) }}</span>
        </span>
        <span class="muted small">
          运行 ID {{ liveRun.id }} · 用例 ID {{ liveRun.case_id }}
          · 已完成步骤 {{ stepCount(liveRun) }}
        </span>
        <p v-if="liveRun.status === 'running' || liveRun.status === 'pending'" class="hint">
          停止将在<strong>当前这一步</strong>完成后生效（模型推理与设备操作期间无法立刻打断）。
        </p>
      </div>
      <div class="status-progress" aria-label="执行进度">
        <span class="progress-label">预估进度</span>
        <span class="progress-pct">{{ runProgressPercent }}%</span>
        <div class="progress-track">
          <div
            class="progress-fill"
            :class="{ done: runProgressPercent >= 100 }"
            :style="{ width: `${runProgressPercent}%` }"
          />
        </div>
      </div>
    </div>
    <div class="exec-console">
      <aside class="exec-screen-pane">
        <DeviceScreenMirror
          v-if="mirrorInstanceId"
          :key="`${liveRun?.id}-${mirrorInstanceId}-${mirrorPlatform}-${mirrorDeviceId}`"
          :robot-instance-id="mirrorInstanceId"
          :device-platform="mirrorPlatform"
          :device-id="mirrorDeviceId"
          :active="screenMirrorActive"
        />
      </aside>
      <div class="exec-log-pane">
        <h3 class="exec-log-title">执行过程</h3>
        <div ref="liveLogScrollRef" class="exec-log-scroll">
          <p v-if="!liveRun.step_log" class="muted log-empty">已排队，等待第一步…</p>
          <div v-else class="steps">
            <div
              v-for="(st, idx) in parseStepLog(liveRun.step_log)"
              :key="idx"
              class="step-card"
              :class="{ finished: st.finished }"
            >
              <div class="step-meta">
                <span class="step-no">第 {{ st.step }} 步</span>
                <span v-if="st.finished" class="step-tag">结束</span>
              </div>
              <div v-if="st.thinking" class="step-block">
                <span class="step-label">推理</span>
                <pre class="step-pre">{{ st.thinking }}</pre>
              </div>
              <div v-if="st.action != null" class="step-block">
                <span class="step-label">动作</span>
                <pre class="step-pre action">{{ formatJson(st.action) }}</pre>
              </div>
              <div v-if="st.message" class="step-msg">{{ st.message }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import DeviceScreenMirror from "@/components/DeviceScreenMirror.vue";
import { useActiveTestRunStore } from "@/stores/activeTestRun";
import {
  estimateRunProgress,
  formatJson,
  parseStepLog,
  statusLabel,
  stepCount,
} from "@/utils/runLive";

const props = defineProps({
  robotInstanceId: { type: [Number, String], default: null },
  devicePlatform: { type: String, default: "" },
  deviceId: { type: String, default: "" },
  /** 用例标题；不传则显示「用例 #case_id」 */
  caseTitle: { type: String, default: "" },
});

const activeRunStore = useActiveTestRunStore();
const { liveRun } = storeToRefs(activeRunStore);

const executionTaskLabel = computed(() => {
  const t = String(props.caseTitle || "").trim();
  if (t) return t;
  const r = liveRun.value;
  return r?.case_id != null ? `用例 #${r.case_id}` : "";
});

const stopBusy = ref(false);
const liveLogScrollRef = ref(null);

const mirrorInstanceId = computed(() => {
  const fromRun = liveRun.value?.robot_instance_id;
  if (fromRun != null) return fromRun;
  const p = props.robotInstanceId;
  return p != null && p !== "" ? Number(p) : null;
});

const mirrorPlatform = computed(() => {
  const p = liveRun.value?.device_platform || props.devicePlatform || "android";
  return String(p).toLowerCase();
});

const mirrorDeviceId = computed(() => liveRun.value?.device_id || props.deviceId || "");

const canStopRun = computed(() => {
  const r = liveRun.value;
  return !!(r && (r.status === "pending" || r.status === "running"));
});

const screenMirrorActive = computed(() => {
  const r = liveRun.value;
  return !!(r && (r.status === "pending" || r.status === "running"));
});

const runProgressPercent = computed(() => estimateRunProgress(liveRun.value));

function scrollLiveLogToBottom() {
  nextTick(() => {
    const el = liveLogScrollRef.value;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  });
}

watch(
  () => liveRun.value?.step_log,
  () => {
    if (liveRun.value) scrollLiveLogToBottom();
  },
);

defineExpose({ scrollLiveLogToBottom });

async function stopRun() {
  if (!liveRun.value?.id) return;
  stopBusy.value = true;
  try {
    await activeRunStore.cancelCurrent();
  } catch (e) {
    window.alert(e.response?.data?.detail || String(e.message || e));
  } finally {
    stopBusy.value = false;
  }
}
</script>

<style scoped>
.panel {
  margin-top: 1rem;
  padding: 1rem 1.1rem;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
}

.panel-head h2 {
  margin: 0;
  font-size: 1.1rem;
}

.status-strip {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.25rem;
  margin-bottom: 1rem;
  padding: 0.65rem 0.85rem;
  background: #f1f5f9;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

.status-strip-main {
  flex: 1;
  min-width: 0;
}

.status-task-line {
  margin: 0 0 0.5rem;
  font-size: 0.92rem;
  line-height: 1.45;
  color: #0f172a;
}

.status-task-line .exec-task-name {
  font-weight: 500;
}

.status-progress {
  flex-shrink: 0;
  width: min(220px, 38%);
  padding-top: 0.1rem;
}

.progress-label {
  display: block;
  font-size: 0.72rem;
  color: #64748b;
  margin-bottom: 0.2rem;
}

.progress-pct {
  display: block;
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 0.35rem;
  text-align: right;
}

.progress-track {
  height: 8px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #38bdf8, #2563eb);
  border-radius: 999px;
  transition: width 0.45s ease;
}

.progress-fill.done {
  background: linear-gradient(90deg, #4ade80, #16a34a);
}

@media (max-width: 720px) {
  .status-strip {
    flex-direction: column;
  }

  .status-progress {
    width: 100%;
  }
}

.status-line {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-right: 0.5rem;
}

.hint {
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: #475569;
}

.btn.stop {
  border: 1px solid #dc2626;
  color: #b91c1c;
  background: #fff;
  padding: 0.35rem 0.75rem;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.88rem;
}

.btn.stop:hover:not(:disabled) {
  background: #fef2f2;
}

.btn.stop:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.badge {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
}

.badge.pending,
.badge.running {
  background: #e0f2fe;
  color: #0369a1;
}

.badge.success {
  background: #dcfce7;
  color: #166534;
}

.badge.failed {
  background: #fee2e2;
  color: #991b1b;
}

.badge.cancelled {
  background: #ffedd5;
  color: #9a3412;
}

.badge.inline {
  font-size: 0.8rem;
  vertical-align: middle;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.85rem;
}

.exec-console {
  --exec-mirror-width: 280px;
  display: grid;
  grid-template-columns: var(--exec-mirror-width) 1fr;
  gap: 1rem;
  margin-top: 0.75rem;
  height: 520px;
  min-height: 480px;
  align-items: stretch;
}

.exec-screen-pane {
  width: var(--exec-mirror-width, 280px);
  max-width: var(--exec-mirror-width, 280px);
  min-height: 0;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
}

.exec-log-pane {
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.exec-log-title {
  margin: 0 0 0.5rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
}

.exec-log-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.65rem 0.75rem;
  background: #f8fafc;
}

.log-empty {
  margin: 0;
  padding: 0.35rem 0;
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0;
}

.step-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 0.75rem 0.85rem;
  background: #f8fafc;
}

.step-card.finished {
  border-color: #86efac;
  background: #f0fdf4;
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.step-no {
  font-weight: 600;
  font-size: 0.9rem;
  color: #0f172a;
}

.step-tag {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
}

.step-block {
  margin-top: 0.35rem;
}

.step-label {
  display: block;
  font-size: 0.75rem;
  color: #64748b;
  margin-bottom: 0.2rem;
}

.step-pre {
  margin: 0;
  padding: 0.55rem 0.65rem;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 6px;
  font-size: 0.8rem;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow: auto;
}

.step-pre.action {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.step-msg {
  margin-top: 0.35rem;
  font-size: 0.85rem;
  color: #334155;
}

@media (max-width: 900px) {
  .exec-console {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 0;
  }

  .exec-screen-pane {
    width: 100%;
    max-width: 100%;
    min-height: 320px;
  }

  .exec-log-scroll {
    max-height: 420px;
  }
}
</style>

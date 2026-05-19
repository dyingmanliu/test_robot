<template>
  <div ref="rootEl" class="device-mirror" :class="{ active }">
    <div class="mirror-head">
      <span class="mirror-title">手机投屏</span>
      <span v-if="polling" class="mirror-badge">刷新中</span>
    </div>
    <div class="mirror-body">
      <div ref="frameEl" class="mirror-frame" :style="frameStyle">
        <img
          v-if="imageSrc"
          :src="imageSrc"
          class="mirror-img"
          :width="meta?.width"
          :height="meta?.height"
          alt="设备当前画面"
          draggable="false"
        />
        <div v-else class="mirror-placeholder" :style="placeholderStyle">
          <p v-if="!robotInstanceId">请先选择机器人实例</p>
          <p v-else-if="!active">执行开始后显示设备画面</p>
          <p v-else-if="loading">正在连接设备…</p>
          <p v-else>{{ placeholderText }}</p>
        </div>
      </div>
    </div>
    <p v-if="meta" class="mirror-meta muted small">
      {{ meta.width }}×{{ meta.height }} · {{ backendLabel(meta.backend) }}
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import client from "@/api/client";

const props = defineProps({
  robotInstanceId: { type: Number, default: null },
  /** android | harmonyos，与用例执行时选择的设备一致 */
  devicePlatform: { type: String, default: "android" },
  deviceId: { type: String, default: "" },
  /** 为 true 时按间隔轮询截屏（执行中） */
  active: { type: Boolean, default: false },
  intervalMs: { type: Number, default: 1500 },
});

const rootEl = ref(null);
const imageSrc = ref("");
const meta = ref(null);
const loading = ref(false);
const polling = ref(false);
const placeholderText = ref("等待画面…");
const hostMax = ref({ width: 280, height: 400 });
let timer = null;
let resizeObserver = null;

const backendLabel = (b) => {
  const p = String(b || "").toLowerCase();
  if (p === "harmonyos" || p === "midscene") return "鸿蒙 / HDC";
  return "Android / ADB";
};

/** 按设备分辨率宽高比计算展示尺寸，宽度与屏幕宽度成比例（非铺满整列） */
const displaySize = computed(() => {
  const m = meta.value;
  const maxW = hostMax.value.width;
  const maxH = hostMax.value.height;
  if (!m?.width || !m?.height) {
    const defaultW = Math.min(280, maxW);
    const defaultH = Math.min(Math.round(defaultW * (19.5 / 9)), maxH);
    return { width: defaultW, height: defaultH };
  }
  const deviceW = m.width;
  const deviceH = m.height;
  const ratio = deviceW / deviceH;
  let width = Math.min(deviceW, maxW);
  let height = width / ratio;
  if (height > maxH) {
    height = maxH;
    width = height * ratio;
  }
  return {
    width: Math.max(120, Math.round(width)),
    height: Math.max(160, Math.round(height)),
  };
});

const frameStyle = computed(() => {
  const { width, height } = displaySize.value;
  const m = meta.value;
  return {
    width: `${width}px`,
    height: `${height}px`,
    aspectRatio: m?.width && m?.height ? `${m.width} / ${m.height}` : "9 / 19.5",
  };
});

const placeholderStyle = computed(() => ({
  width: "100%",
  height: "100%",
}));

async function fetchFrame() {
  if (!props.robotInstanceId) return;
  if (!polling.value) polling.value = true;
  if (!imageSrc.value) loading.value = true;
  try {
    const { data } = await client.get(`/api/robot-instances/${props.robotInstanceId}/device-screen`, {
      params: {
        device_platform: props.devicePlatform || "android",
        ...(props.deviceId ? { device_id: props.deviceId } : {}),
      },
    });
    const mime = data.mime_type || "image/png";
    imageSrc.value = `data:${mime};base64,${data.image_base64}`;
    meta.value = { width: data.width, height: data.height, backend: data.backend };
    placeholderText.value = "";
  } catch (e) {
    const detail = e.response?.data?.detail;
    placeholderText.value =
      typeof detail === "string" ? detail : "无法获取设备画面，请确认设备已连接且 HDC/ADB 可用";
    if (!imageSrc.value) meta.value = null;
  } finally {
    loading.value = false;
    polling.value = false;
  }
}

function stopPoll() {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  polling.value = false;
}

function startPoll() {
  stopPoll();
  if (!props.active || !props.robotInstanceId) return;
  fetchFrame();
  timer = setInterval(fetchFrame, props.intervalMs);
}

function updateHostMax() {
  const el = rootEl.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  hostMax.value = {
    width: Math.max(120, Math.floor(rect.width)),
    height: Math.max(160, Math.floor(rect.height) - 52),
  };
}

watch(
  () => [props.active, props.robotInstanceId, props.devicePlatform, props.deviceId],
  () => {
    if (props.active && props.robotInstanceId) {
      startPoll();
    } else {
      stopPoll();
      if (!props.active) {
        loading.value = false;
      }
    }
  },
  { immediate: true },
);

onMounted(() => {
  updateHostMax();
  resizeObserver = new ResizeObserver(() => updateHostMax());
  if (rootEl.value) resizeObserver.observe(rootEl.value);
});

onBeforeUnmount(() => {
  stopPoll();
  resizeObserver?.disconnect();
});
</script>

<style scoped>
.device-mirror {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  align-items: center;
}

.mirror-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  width: 100%;
}

.mirror-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: #0f172a;
}

.mirror-badge {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  background: #e0f2fe;
  color: #0369a1;
}

.mirror-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.mirror-frame {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0f172a;
  border-radius: 10px;
  border: 1px solid #334155;
  overflow: hidden;
  box-sizing: border-box;
}

.mirror-img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: fill;
}

.mirror-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.82rem;
  line-height: 1.5;
  box-sizing: border-box;
}

.mirror-placeholder p {
  margin: 0;
}

.mirror-meta {
  margin: 0.4rem 0 0;
  width: 100%;
  text-align: center;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.78rem;
}
</style>

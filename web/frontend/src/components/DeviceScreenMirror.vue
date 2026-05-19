<template>
  <div class="device-mirror" :class="{ active }">
    <div class="mirror-head">
      <span class="mirror-title">手机投屏</span>
      <span v-if="polling" class="mirror-badge">刷新中</span>
    </div>
    <div ref="bodyEl" class="mirror-body">
      <div class="mirror-frame" :style="frameStyle">
        <img
          v-if="imageSrc"
          :src="imageSrc"
          class="mirror-img"
          alt="设备当前画面"
          draggable="false"
        />
        <div v-else class="mirror-placeholder">
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
  devicePlatform: { type: String, default: "android" },
  deviceId: { type: String, default: "" },
  active: { type: Boolean, default: false },
  intervalMs: { type: Number, default: 1500 },
});

const bodyEl = ref(null);
const imageSrc = ref("");
const meta = ref(null);
const loading = ref(false);
const polling = ref(false);
const placeholderText = ref("等待画面…");
/** 首次截屏后锁定宽高比，避免轮询时外框尺寸变化 */
const lockedRatio = ref(9 / 19.5);
const hostBounds = ref({ width: 260, height: 420 });

const backendLabel = (b) => {
  const p = String(b || "").toLowerCase();
  if (p === "harmonyos" || p === "midscene") return "鸿蒙 / HDC";
  return "Android / ADB";
};

const frameStyle = computed(() => {
  const maxW = hostBounds.value.width;
  const maxH = hostBounds.value.height;
  const ratio = lockedRatio.value;
  let height = maxH;
  let width = height * ratio;
  if (width > maxW) {
    width = maxW;
    height = width / ratio;
  }
  width = Math.max(100, Math.round(width));
  height = Math.max(160, Math.round(height));
  return {
    width: `${width}px`,
    height: `${height}px`,
  };
});

let timer = null;
let resizeObserver = null;

function measureHost() {
  const el = bodyEl.value;
  if (!el) return;
  const rect = el.getBoundingClientRect();
  const height = Math.max(160, Math.floor(rect.height));
  const widthCap = Math.floor(height * lockedRatio.value);
  hostBounds.value = {
    width: Math.max(100, Math.min(Math.floor(rect.width) || widthCap, widthCap)),
    height,
  };
}

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
    if (data.width && data.height) {
      if (!meta.value) {
        lockedRatio.value = data.width / data.height;
      }
      meta.value = { width: data.width, height: data.height, backend: data.backend };
    }
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

function resetMirrorState() {
  imageSrc.value = "";
  meta.value = null;
  lockedRatio.value = 9 / 19.5;
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
        resetMirrorState();
      }
    }
  },
  { immediate: true },
);

onMounted(() => {
  measureHost();
  resizeObserver = new ResizeObserver(() => measureHost());
  if (bodyEl.value) resizeObserver.observe(bodyEl.value);
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
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
}

.mirror-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-shrink: 0;
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
}

.mirror-frame {
  position: relative;
  flex-shrink: 0;
  background: #0f172a;
  border-radius: 10px;
  border: 1px solid #334155;
  overflow: hidden;
  box-sizing: border-box;
}

.mirror-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: fill;
}

.mirror-placeholder {
  width: 100%;
  height: 100%;
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
  flex-shrink: 0;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.78rem;
}
</style>

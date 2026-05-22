<template>
  <div class="device-mirror" :class="{ active }">
    <div class="mirror-head">
      <span class="mirror-title">手机投屏</span>
      <span v-if="polling" class="mirror-badge">刷新中</span>
    </div>
    <div class="mirror-body">
      <div class="mirror-frame">
        <img
          v-if="imageSrc"
          :src="imageSrc"
          class="mirror-img"
          alt="设备当前画面"
          draggable="false"
          @error="onImageError"
        />
        <div v-else class="mirror-placeholder">
          <p v-if="!robotInstanceId">请先选择机器人实例</p>
          <p v-else-if="!active">{{ idleHint }}</p>
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
import { onBeforeUnmount, ref, watch } from "vue";
import client from "@/api/client";

const props = defineProps({
  robotInstanceId: { type: Number, default: null },
  devicePlatform: { type: String, default: "android" },
  deviceId: { type: String, default: "" },
  active: { type: Boolean, default: false },
  intervalMs: { type: Number, default: 1500 },
  /** 未激活时的提示文案 */
  idleHint: { type: String, default: "执行开始后显示设备画面" },
});

const imageSrc = ref("");
const meta = ref(null);
const loading = ref(false);
const polling = ref(false);
const placeholderText = ref("等待画面…");
const backendLabel = (b) => {
  const p = String(b || "").toLowerCase();
  if (p === "harmonyos" || p === "midscene") return "鸿蒙 / HDC";
  return "Android / ADB";
};

let timer = null;
let objectUrl = null;

function revokeObjectUrl() {
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
    objectUrl = null;
  }
}

function base64ToBlob(b64, mime) {
  const clean = String(b64 || "").replace(/\s/g, "");
  const binary = atob(clean);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

function onImageError() {
  placeholderText.value = "画面解码失败，请刷新页面或检查设备连接";
  revokeObjectUrl();
  imageSrc.value = "";
  meta.value = null;
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
    const mime = data.mime_type || "image/jpeg";
    revokeObjectUrl();
    objectUrl = URL.createObjectURL(base64ToBlob(data.image_base64, mime));
    imageSrc.value = objectUrl;
    if (data.width && data.height) {
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
  revokeObjectUrl();
  imageSrc.value = "";
  meta.value = null;
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

onBeforeUnmount(() => {
  stopPoll();
  revokeObjectUrl();
});
</script>

<style scoped>
.device-mirror {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  width: 100%;
  max-width: 280px;
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
  justify-content: center;
  align-items: stretch;
}

.mirror-frame {
  position: relative;
  flex-shrink: 0;
  height: 100%;
  width: auto;
  max-width: 100%;
  aspect-ratio: 9 / 19.5;
  background: #0f172a;
  border-radius: 10px;
  border: 1px solid #334155;
  overflow: hidden;
  box-sizing: border-box;
}

.mirror-img {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.mirror-placeholder {
  position: absolute;
  inset: 0;
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

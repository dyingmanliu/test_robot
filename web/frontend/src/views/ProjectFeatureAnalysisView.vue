<template>
  <div class="fa-page">
    <header class="page-head">
      <p class="back-row">
        <router-link class="back-link" :to="{ name: 'projects' }">← 项目空间</router-link>
        <router-link
          v-if="projectId"
          class="back-link hist"
          :to="{ name: 'projectFeatureAnalysisHistory', params: { projectId } }"
          >功能树记录</router-link
        >
      </p>
      <h1>功能点分析</h1>
      <p v-if="project" class="project-sub">
        {{ project.name }} · 被测应用：{{ project.tested_app_name }}
      </p>
      <p class="hint">
        选择<strong>测试分析</strong>机器人；<strong>已安装应用</strong>按探测到的平台维度选择，选中后自动带出包名与应用名称；
        <strong>上传安装包</strong>则按文件类型自动识别平台。
      </p>
    </header>

    <p v-if="pageErr" class="banner err">{{ pageErr }}</p>

    <section class="card block">
      <h2>分析配置</h2>
      <div class="form-grid">
        <label class="field field-wide">
          <span>测试分析机器人</span>
          <select v-model.number="form.robot_instance_id" :disabled="running">
            <option :value="0" disabled>请选择</option>
            <option
              v-for="r in analysisRobots"
              :key="r.id"
              :value="r.id"
              :disabled="!isRobotRunnableForFeatureAnalysis(r)"
            >
              {{ r.display_name || r.instance_code }} (#{{ r.id }})
              {{ analysisRobotUnselectableHint(r) }}
            </option>
          </select>
        </label>
      </div>

      <div class="app-source">
        <label class="radio-row">
          <input v-model="form.app_source" type="radio" value="installed" :disabled="running" />
          <span>已安装应用</span>
        </label>
        <label class="radio-row">
          <input v-model="form.app_source" type="radio" value="uploaded" :disabled="running" />
          <span>上传安装应用</span>
        </label>
      </div>

      <div v-if="form.app_source === 'installed'" class="sub-block installed-panel">
        <div class="catalog-head">
          <span class="muted small">按平台维度选择待分析应用（自动读取已连接设备上的安装列表）</span>
          <button
            type="button"
            class="btn-link"
            :disabled="catalogLoading || running"
            @click="loadInstalledCatalog"
          >
            {{ catalogLoading ? "刷新中…" : "刷新应用列表" }}
          </button>
        </div>
        <p v-if="catalogError" class="err small">{{ catalogError }}</p>

        <div v-if="installedCatalog.length" class="dim-tabs" role="tablist">
          <button
            v-for="block in installedCatalog"
            :key="block.platform"
            type="button"
            role="tab"
            class="dim-tab"
            :class="{ active: activeInstalledPlatform === block.platform }"
            :disabled="running"
            :aria-selected="activeInstalledPlatform === block.platform"
            @click="setActiveInstalledPlatform(block.platform)"
          >
            {{ block.platform_label || platformLabel(block.platform) }}
          </button>
        </div>

        <div v-if="activeCatalogBlock" class="dim-panel">
          <p class="dim-panel-head">
            <span class="dim-platform">{{ activeCatalogBlock.platform_label }}</span>
            <span v-if="activeCatalogBlock.devices.length" class="device-hint muted">
              {{ activeCatalogBlock.devices.length }} 台在线设备 · 列表来自
              {{ activeCatalogBlock.devices[0].label }}
            </span>
          </p>
          <label class="field field-wide">
            <span>安装应用</span>
            <select
              :value="selectedByPlatform[activeCatalogBlock.platform] || ''"
              :disabled="running || catalogLoading || !activeCatalogBlock.apps.length"
              @change="onSelectInstalledApp(activeCatalogBlock.platform, $event.target.value)"
            >
              <option value="">请选择已安装应用</option>
              <option v-for="a in activeCatalogBlock.apps" :key="a.bundle_id" :value="a.bundle_id">
                {{ a.label || a.bundle_id }}（{{ a.bundle_id }}）
              </option>
            </select>
          </label>
          <p v-if="activeCatalogBlock.error" class="err small">
            {{ activeCatalogBlock.platform_label }}：{{ activeCatalogBlock.error }}
          </p>
          <p v-else-if="!activeCatalogBlock.apps.length" class="muted small">
            {{ activeCatalogBlock.platform_label }}：未读取到已安装应用
          </p>
        </div>
        <p v-else-if="installedCatalog.length" class="muted small dim-empty">
          {{ activePlatformLabel }}：未检测到在线设备，请连接真机后刷新列表
        </p>

      </div>

      <div v-else class="sub-block uploaded-panel">
        <label class="field field-wide">
          <span>上传安装包</span>
          <div class="upload-file-row">
            <input
              ref="fileInputRef"
              type="file"
              class="upload-file-input"
              accept=".apk,.aab,.hap,.app"
              :disabled="running || uploading || installingFromFile"
              @change="onPickFile"
            />
            <button
              type="button"
              class="btn btn-install-inline"
              :disabled="running || !pickedFile || uploading || installingFromFile"
              @click="doUploadAndInstall"
            >
              {{ fileInstallBusy ? "安装中…" : "安装" }}
            </button>
          </div>
        </label>
        <p class="muted small">
          上传安装包并安装到设备后，将自动识别应用包名、应用名称与分析平台
        </p>
      </div>

      <div v-if="showSelectedAppSummary" class="selected-app-readonly">
        <div class="readonly-row">
          <span class="readonly-label">应用包名</span>
          <span class="readonly-value">{{ form.bundle_id }}</span>
        </div>
        <div class="readonly-row">
          <span class="readonly-label">应用名称</span>
          <span class="readonly-value">{{ form.app_display_name }}</span>
        </div>
        <p class="muted small readonly-hint">
          分析平台：<strong>{{ summaryPlatformLabel }}</strong>
          · 将使用首台在线设备
        </p>
      </div>

      <div class="form-actions">
        <button type="button" class="btn primary" :disabled="running || !canStart" @click="startAnalysis">
          {{ running ? "分析进行中…" : "开始分析" }}
        </button>
        <button v-if="running && runId" type="button" class="btn" @click="cancelRun">取消</button>
      </div>
      <p v-if="!running && !canStart && startBlockedReason" class="err small start-hint">
        {{ startBlockedReason }}
      </p>
      <p
        v-if="staleBlockingRun && !running"
        class="warn-banner small"
      >
        该机器人有未结束的分析任务（#{{ staleBlockingRun.id }}，{{ staleBlockingRun.status }}）。
        <button type="button" class="btn-link" @click="cancelStaleRun">点击终止并释放机器人</button>
      </p>
    </section>

    <section v-if="run" class="card block">
      <div class="status-head">
        <h2>任务状态</h2>
        <span class="pill" :class="statusClass">{{ statusLabel }}</span>
      </div>
      <p v-if="run.output_message" class="muted">{{ run.output_message }}</p>
      <div class="metrics">
        <div class="metric"><span class="label">功能项</span><strong>{{ run.feature_count ?? 0 }}</strong></div>
        <div class="metric"><span class="label">访问页面</span><strong>{{ run.screens_visited ?? 0 }}</strong></div>
      </div>
      <div v-if="run.has_excel" class="download-row">
        <button type="button" class="btn" @click="downloadExcel">下载 Excel 草稿</button>
      </div>
    </section>

    <section v-if="showWorkbench" class="card block live-block">
      <div class="live-head">
        <h2>{{ running ? "分析过程（实时）" : "功能完备度分析结果" }}</h2>
        <div v-if="running || run?.status === 'pending'" class="live-progress" aria-label="分析进度">
          <span class="progress-label">预估进度</span>
          <span class="progress-pct">{{ progressPercent }}%</span>
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="{ done: progressPercent >= 100 }"
              :style="{ width: `${progressPercent}%` }"
            />
          </div>
        </div>
      </div>
      <p v-if="running" class="live-hint muted small">
        按界面深度优先遍历（DFS），记录每屏功能点并组装为 GIIC 层级功能树；右侧为真机投屏。
      </p>
      <div
        v-if="running && liveLocation"
        class="location-banner"
        :class="{ 'location-off': !liveLocation.inTarget }"
        role="status"
      >
        <div class="location-row">
          <span class="location-label">当前界面</span>
          <strong>{{ liveLocation.screenTitle || "识别中…" }}</strong>
        </div>
        <div class="location-row muted small">
          <span>遍历路径 {{ liveLocation.path }}</span>
          <span v-if="liveLocation.foreground"> · 前台 {{ liveLocation.foreground }}</span>
        </div>
        <p v-if="liveLocation.lastAction" class="location-action small">
          正在执行：{{ liveLocation.lastAction }}
        </p>
        <p v-if="!liveLocation.inTarget" class="location-warn small">
          设备已离开被测应用，正在尝试拉回；若投屏与日志不一致，请以投屏为准并等待恢复。
        </p>
      </div>
      <FeatureAnalysisWorkbench
        ref="workbenchRef"
        :feature-json="run?.feature_json || ''"
        :app-display-name="form.app_display_name || form.bundle_id"
        :editable="run?.status === 'success'"
        :show-mirror="running"
        :robot-instance-id="mirrorInstanceId"
        :device-platform="mirrorPlatform"
        :device-id="mirrorDeviceId"
        :mirror-active="screenMirrorActive"
      />
      <details v-if="liveLogEntries.length" class="log-fold">
        <summary class="muted small">探索步骤日志（{{ liveLogEntries.length }} 条）</summary>
        <div ref="liveLogScrollRef" class="exec-log-scroll compact">
          <div class="fa-log-list">
            <div
              v-for="(ev, idx) in liveLogEntries"
              :key="idx"
              class="fa-log-card"
              :class="ev.tone"
            >
              <div class="fa-log-meta">
                <span class="fa-log-title">{{ ev.title }}</span>
                <span v-if="ev.meta" class="fa-log-tag">{{ ev.meta }}</span>
              </div>
              <p v-if="ev.body" class="fa-log-body">{{ ev.body }}</p>
            </div>
          </div>
        </div>
      </details>
      <div v-if="run?.status === 'success'" class="confirm-row">
        <input v-model="confirmLabel" class="ver-input" placeholder="版本标签（可选，默认 vN）" />
        <button type="button" class="btn primary" :disabled="confirming" @click="confirmTree">
          {{ confirming ? "保存中…" : "确认并保存功能树" }}
        </button>
      </div>
      <p v-if="confirmErr" class="err">{{ confirmErr }}</p>
      <p v-if="confirmOk" class="ok-msg">{{ confirmOk }}</p>
    </section>

    <p v-if="actionErr" class="banner err">{{ actionErr }}</p>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";
import FeatureAnalysisWorkbench from "@/components/FeatureAnalysisWorkbench.vue";
import {
  analysisRobotUnselectableHint,
  isRobotRunnableForFeatureAnalysis,
} from "@/constants/robotCatalog";
import {
  estimateFeatureProgress,
  parseFeatureStepLog,
  summarizeFeatureAnalysisLocation,
} from "@/utils/featureAnalysisLive";
import { inferDevicePlatform, platformLabel } from "@/utils/packagePlatform";

const route = useRoute();
const router = useRouter();
const projectId = computed(() => Number(route.params.projectId));

const project = ref(null);
const pageErr = ref("");
const actionErr = ref("");
const robots = ref([]);
const detectedPlatform = ref("");
const parsedAppName = ref("");
const installedCatalog = ref([]);
const catalogLoading = ref(false);
const catalogError = ref("");
const activeInstalledPlatform = ref("");
const selectedByPlatform = reactive({});
const selectedDeviceByPlatform = reactive({});

const catalogByPlatform = computed(() => {
  const map = {};
  for (const block of installedCatalog.value) {
    map[block.platform] = block;
  }
  return map;
});

const activeCatalogBlock = computed(
  () => catalogByPlatform.value[activeInstalledPlatform.value] || null,
);

const activePlatformLabel = computed(() => {
  const block = activeCatalogBlock.value;
  if (block?.platform_label) return block.platform_label;
  if (activeInstalledPlatform.value) return platformLabel(activeInstalledPlatform.value);
  return "当前平台";
});

const summaryPlatformLabel = computed(() => {
  const block = catalogByPlatform.value[detectedPlatform.value];
  return block?.platform_label || (detectedPlatform.value ? platformLabel(detectedPlatform.value) : "");
});

const showSelectedAppSummary = computed(() => {
  if (!form.bundle_id.trim().includes(".")) return false;
  if (form.app_source === "installed") return hasInstalledAppSelected.value;
  return uploadInstallSucceeded.value;
});

const fileInstallBusy = computed(() => uploading.value || installingFromFile.value);

const hasInstalledAppSelected = computed(
  () => form.app_source === "installed" && form.bundle_id.trim().includes("."),
);
const uploadInstallSucceeded = ref(false);
const uploadInstallOk = ref("");
const uploadedDeviceId = ref("");
const uploadedArtifactMeta = ref(null);
const pickedFile = ref(null);
const fileInputRef = ref(null);
const uploading = ref(false);
const installingFromFile = ref(false);

const form = reactive({
  robot_instance_id: 0,
  app_source: "installed",
  app_artifact_id: null,
  bundle_id: "",
  app_display_name: "",
  max_screens: 30,
  max_depth: 4,
});

const run = ref(null);
const runId = ref(null);
const workbenchRef = ref(null);
const confirmLabel = ref("");
const confirming = ref(false);
const confirmErr = ref("");
const confirmOk = ref("");
const liveLogScrollRef = ref(null);
let pollTimer = null;

const apiBase = computed(() => `/api/projects/${projectId.value}/feature-analysis`);

const analysisRobots = computed(() =>
  (robots.value || []).filter((r) => String(r.catalog_robot_id || "") === "test_analysis"),
);

const running = computed(() => {
  const s = run.value?.status;
  return s === "pending" || s === "running";
});

const showWorkbench = computed(() => {
  if (!run.value) return false;
  const s = run.value.status;
  if (s === "pending" || s === "running") return true;
  if (s === "success") return true;
  return Boolean(run.value.feature_json || run.value.step_log);
});

const screenMirrorActive = computed(() => running.value);

const mirrorInstanceId = computed(() => {
  const fromRun = run.value?.robot_instance_id;
  if (fromRun != null) return fromRun;
  return form.robot_instance_id > 0 ? form.robot_instance_id : null;
});

const mirrorPlatform = computed(() => {
  const p = run.value?.device_platform || detectedPlatform.value || "harmonyos";
  return String(p).toLowerCase();
});

const mirrorDeviceId = computed(() => {
  const fromRun = (run.value?.device_id || "").trim();
  if (fromRun) return fromRun;
  if (form.app_source === "installed" && detectedPlatform.value) {
    return selectedDeviceByPlatform[detectedPlatform.value] || "";
  }
  if (form.app_source === "uploaded") return uploadedDeviceId.value || "";
  return "";
});

const liveLogEntries = computed(() => parseFeatureStepLog(run.value?.step_log));

const liveLocation = computed(() =>
  summarizeFeatureAnalysisLocation(run.value?.step_log),
);

const progressPercent = computed(() => estimateFeatureProgress(run.value));

function scrollLiveLogToBottom() {
  nextTick(() => {
    const el = liveLogScrollRef.value;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  });
}

watch(
  () => run.value?.step_log,
  () => {
    if (showWorkbench.value) scrollLiveLogToBottom();
  },
);

const recentRuns = ref([]);

const selectedRobot = computed(() =>
  analysisRobots.value.find((r) => r.id === form.robot_instance_id),
);

const staleBlockingRun = computed(() => {
  const rid = form.robot_instance_id;
  if (rid <= 0) return null;
  return (
    (recentRuns.value || []).find(
      (r) =>
        r.robot_instance_id === rid &&
        (r.status === "pending" || r.status === "running"),
    ) || null
  );
});

const startBlockedReason = computed(() => {
  if (running.value) return "";
  if (form.robot_instance_id <= 0) {
    return "请先选择测试分析机器人。";
  }
  const inst = selectedRobot.value;
  if (!inst) return "所选机器人无效，请重新选择。";
  if (!isRobotRunnableForFeatureAnalysis(inst)) {
    const hint = analysisRobotUnselectableHint(inst);
    if (staleBlockingRun.value) {
      return `测试分析机器人不可用${hint}：存在未结束的分析任务，请先终止。`;
    }
    return `测试分析机器人不可用${hint || "（非空闲）"}，请在「我的机器人」确认已启用且空闲。`;
  }
  if (form.app_source === "installed") {
    if (!form.bundle_id.trim().includes(".")) {
      return "请从已安装应用列表中选择应用（需包含有效包名）。";
    }
    return "";
  }
  if (!uploadInstallSucceeded.value || !form.bundle_id.trim().includes(".")) {
    return "请先上传安装包并完成安装，确保识别到应用包名。";
  }
  return "";
});

const canStart = computed(() => !startBlockedReason.value && form.robot_instance_id > 0);

const statusLabel = computed(() => {
  const m = {
    pending: "排队中",
    running: "分析中",
    success: "已完成",
    failed: "失败",
    cancelled: "已取消",
  };
  return m[run.value?.status] || run.value?.status || "—";
});

const statusClass = computed(() => {
  const s = run.value?.status;
  if (s === "success") return "ok";
  if (s === "failed") return "bad";
  if (s === "running" || s === "pending") return "warn";
  return "";
});

async function loadProject() {
  try {
    const { data } = await client.get(`/api/projects/${projectId.value}`);
    project.value = data;
    if (!form.app_display_name.trim()) {
      form.app_display_name = data.tested_app_name || "";
    }
  } catch (e) {
    pageErr.value = formatApiError(e);
  }
}

async function loadRecentRuns() {
  try {
    const { data } = await client.get(`${apiBase.value}/runs`);
    recentRuns.value = data || [];
    const active = (data || []).find(
      (r) =>
        (r.status === "pending" || r.status === "running") &&
        (!form.robot_instance_id || r.robot_instance_id === form.robot_instance_id),
    );
    if (active && !run.value) {
      run.value = active;
      runId.value = active.id;
      if (active.status === "pending" || active.status === "running") {
        pollTimer = setTimeout(pollRun, 500);
      }
    }
  } catch {
    recentRuns.value = [];
  }
}

async function loadRobots() {
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    robots.value = data || [];
    const current = analysisRobots.value.find((r) => r.id === form.robot_instance_id);
    if (current && isRobotRunnableForFeatureAnalysis(current)) return;
    const first = analysisRobots.value.find((r) => isRobotRunnableForFeatureAnalysis(r));
    if (first) form.robot_instance_id = first.id;
    else if (!form.robot_instance_id && analysisRobots.value.length) {
      form.robot_instance_id = analysisRobots.value[0].id;
    }
  } catch (e) {
    pageErr.value = formatApiError(e);
  }
}

async function cancelStaleRun() {
  const r = staleBlockingRun.value;
  if (!r) return;
  runId.value = r.id;
  await cancelRun();
  await loadRobots();
  await loadRecentRuns();
}

function setActiveInstalledPlatform(platform) {
  activeInstalledPlatform.value = platform;
}

function syncActiveInstalledPlatform() {
  const items = installedCatalog.value;
  if (!items.length) {
    activeInstalledPlatform.value = "";
    return;
  }
  if (items.some((b) => b.platform === activeInstalledPlatform.value)) return;
  activeInstalledPlatform.value = items[0].platform;
}

function clearOtherPlatformSelections(platform) {
  for (const block of installedCatalog.value) {
    if (block.platform === platform) continue;
    selectedByPlatform[block.platform] = "";
    selectedDeviceByPlatform[block.platform] = "";
  }
}

function clearInstalledSelection(platform) {
  selectedByPlatform[platform] = "";
  selectedDeviceByPlatform[platform] = "";
  if (detectedPlatform.value === platform) {
    form.bundle_id = "";
    detectedPlatform.value = "";
    parsedAppName.value = "";
    form.app_display_name = project.value?.tested_app_name || "";
  }
}

function applyInstalledBundleSelection(platform, bundleId) {
  const block = installedCatalog.value.find((b) => b.platform === platform);
  const app = block?.apps?.find((a) => a.bundle_id === bundleId);
  if (!bundleId || !app) {
    clearInstalledSelection(platform);
    return;
  }
  clearOtherPlatformSelections(platform);
  selectedByPlatform[platform] = bundleId;
  selectedDeviceByPlatform[platform] =
    block?.devices?.length ? block.devices[0].device_id : "";
  form.bundle_id = bundleId;
  activeInstalledPlatform.value = platform;
  detectedPlatform.value = platform;
  parsedAppName.value = app.label || bundleId;
  form.app_display_name = parsedAppName.value;
}

function onSelectInstalledApp(platform, bundleId) {
  if (!bundleId) {
    clearInstalledSelection(platform);
    return;
  }
  applyInstalledBundleSelection(platform, bundleId);
}

async function loadInstalledCatalog() {
  catalogLoading.value = true;
  catalogError.value = "";
  try {
    const { data } = await client.get(`${apiBase.value}/installed-apps-catalog`);
    installedCatalog.value = data?.items || [];
    syncActiveInstalledPlatform();
  } catch (e) {
    catalogError.value = formatApiError(e);
    installedCatalog.value = [];
  } finally {
    catalogLoading.value = false;
  }
}

function refreshDetectedPlatform() {
  if (form.app_source === "installed") return;
  parsedAppName.value = "";
  detectedPlatform.value = inferDevicePlatform({
    bundleId: form.bundle_id,
    filename: pickedFile.value?.name || uploadedArtifactMeta.value?.filename || "",
  });
}

function resetUploadInstallState() {
  uploadInstallSucceeded.value = false;
  uploadInstallOk.value = "";
  uploadedDeviceId.value = "";
  uploadedArtifactMeta.value = null;
  form.app_artifact_id = null;
  form.bundle_id = "";
  form.app_display_name = "";
  parsedAppName.value = "";
}

function clearInstalledSelectionState() {
  for (const block of installedCatalog.value) {
    selectedByPlatform[block.platform] = "";
    selectedDeviceByPlatform[block.platform] = "";
  }
  selectedByPlatform.harmonyos = "";
  selectedByPlatform.android = "";
  selectedDeviceByPlatform.harmonyos = "";
  selectedDeviceByPlatform.android = "";
  activeInstalledPlatform.value = "";
}

function resetOnAppSourceSwitch() {
  resetUploadInstallState();
  clearInstalledSelectionState();
  clearFileInput();
  detectedPlatform.value = "";
  actionErr.value = "";
}

function onPickFile(ev) {
  pickedFile.value = ev.target.files?.[0] || null;
  resetUploadInstallState();
  refreshDetectedPlatform();
}

function clearFileInput() {
  pickedFile.value = null;
  if (fileInputRef.value) fileInputRef.value.value = "";
}

function applyUploadInstallResult(data) {
  form.bundle_id = (data?.bundle_id || "").trim();
  form.app_display_name = (data?.app_display_name || "").trim();
  detectedPlatform.value = data?.device_platform || detectedPlatform.value;
  uploadedDeviceId.value = data?.device_id || "";
  parsedAppName.value = form.app_display_name;
  uploadInstallSucceeded.value = Boolean(form.bundle_id.includes("."));
  clearFileInput();
}

async function doUpload() {
  if (!pickedFile.value) return;
  uploading.value = true;
  actionErr.value = "";
  uploadInstallSucceeded.value = false;
  form.bundle_id = "";
  form.app_display_name = "";
  try {
    const fd = new FormData();
    fd.append("file", pickedFile.value);
    const { data } = await client.post(`${apiBase.value}/app-packages`, fd);
    form.app_artifact_id = data.id;
    uploadedArtifactMeta.value = { id: data.id, filename: data.filename || "" };
    refreshDetectedPlatform();
  } catch (e) {
    actionErr.value = formatApiError(e);
    form.app_artifact_id = null;
    uploadedArtifactMeta.value = null;
    throw e;
  } finally {
    uploading.value = false;
  }
}

async function doUploadAndInstall() {
  if (!pickedFile.value) return;
  actionErr.value = "";
  installingFromFile.value = true;
  try {
    await doUpload();
    await doInstall();
  } catch (e) {
    if (!actionErr.value) actionErr.value = formatApiError(e);
  } finally {
    installingFromFile.value = false;
  }
}

async function doInstall() {
  if (!form.app_artifact_id) {
    actionErr.value = "请先上传安装包";
    return;
  }
  actionErr.value = "";
  try {
    refreshDetectedPlatform();
    const { data } = await client.post(
      `${apiBase.value}/app-packages/${form.app_artifact_id}/install`,
      {
        device_platform: detectedPlatform.value || undefined,
        device_id: null,
      },
    );
    applyUploadInstallResult(data);
    if (!uploadInstallSucceeded.value) {
      throw new Error("安装完成，但未能识别应用包名");
    }
    await loadInstalledCatalog();
  } catch (e) {
    actionErr.value = formatApiError(e);
    resetUploadInstallState();
  }
}

async function pollRun() {
  if (!runId.value) return;
  try {
    const { data } = await client.get(`${apiBase.value}/runs/${runId.value}`);
    run.value = data;
    scrollLiveLogToBottom();
    if (data.status === "pending" || data.status === "running") {
      pollTimer = setTimeout(pollRun, 2000);
    } else {
      stopPoll();
    }
  } catch (e) {
    actionErr.value = formatApiError(e);
    stopPoll();
  }
}

function stopPoll() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

async function startAnalysis() {
  actionErr.value = "";
  confirmOk.value = "";
  stopPoll();
  try {
    refreshDetectedPlatform();
    const instDeviceId =
      form.app_source === "installed" && detectedPlatform.value
        ? selectedDeviceByPlatform[detectedPlatform.value] || null
        : form.app_source === "uploaded" && detectedPlatform.value
          ? uploadedDeviceId.value || null
          : null;
    const body = {
      robot_instance_id: form.robot_instance_id,
      device_platform: detectedPlatform.value || undefined,
      device_id: instDeviceId,
      app_source: form.app_source,
      platform_app_text: "",
      app_artifact_id: form.app_source === "uploaded" ? form.app_artifact_id : null,
      bundle_id: form.app_source === "installed" ? form.bundle_id.trim() : form.bundle_id.trim(),
      app_display_name:
        form.app_source === "installed"
          ? parsedAppName.value || form.app_display_name.trim()
          : form.app_display_name.trim() || form.bundle_id.trim(),
      max_screens: form.max_screens,
      max_depth: form.max_depth,
    };
    const { data } = await client.post(`${apiBase.value}/runs`, body);
    run.value = data;
    runId.value = data.id;
    pollTimer = setTimeout(pollRun, 1500);
  } catch (e) {
    actionErr.value = formatApiError(e);
  }
}

async function cancelRun() {
  if (!runId.value) return;
  try {
    const { data } = await client.post(`${apiBase.value}/runs/${runId.value}/cancel`);
    run.value = data;
    stopPoll();
  } catch (e) {
    actionErr.value = formatApiError(e);
  }
}

async function downloadExcel() {
  if (!runId.value) return;
  try {
    const { data } = await client.get(`${apiBase.value}/runs/${runId.value}/download`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${form.app_display_name || "APP"}-功能菜单树.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    actionErr.value = formatApiError(e);
  }
}

async function confirmTree() {
  if (!runId.value) return;
  confirming.value = true;
  confirmErr.value = "";
  confirmOk.value = "";
  try {
    const tree_json = workbenchRef.value?.getTreeJson?.() || { features: [] };
    const { data } = await client.post(`${apiBase.value}/runs/${runId.value}/confirm`, {
      tree_json,
      version_label: confirmLabel.value.trim(),
    });
    confirmOk.value = `已保存为 ${data.version_label}，可在功能树记录中查看。`;
    setTimeout(() => {
      router.push({
        name: "projectFeatureTreeDetail",
        params: { projectId: projectId.value, treeId: data.id },
      });
    }, 800);
  } catch (e) {
    confirmErr.value = formatApiError(e);
  } finally {
    confirming.value = false;
  }
}

watch(
  () => form.app_source,
  async (src, prev) => {
    if (prev !== undefined && prev !== src) {
      resetOnAppSourceSwitch();
    }
    if (src === "installed") {
      await loadInstalledCatalog();
    } else {
      refreshDetectedPlatform();
    }
  },
);

watch(
  () => form.robot_instance_id,
  async () => {
    if (form.app_source === "installed") {
      await loadInstalledCatalog();
    }
  },
);

onMounted(async () => {
  await loadProject();
  await loadRobots();
  await loadRecentRuns();
  if (form.app_source === "installed") {
    await loadInstalledCatalog();
  } else {
    refreshDetectedPlatform();
  }
});
onUnmounted(stopPoll);
</script>

<style scoped>
.fa-page {
  max-width: 1280px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
}
.live-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
  margin-bottom: 0.65rem;
}
.live-head h2 {
  margin: 0;
}
.live-progress {
  flex-shrink: 0;
  width: min(220px, 42%);
}
.live-progress .progress-label {
  display: block;
  font-size: 0.72rem;
  color: #64748b;
}
.live-progress .progress-pct {
  display: block;
  font-size: 0.88rem;
  font-weight: 600;
  text-align: right;
  margin-bottom: 0.35rem;
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
.live-hint {
  margin: 0 0 0.75rem;
}
.location-banner {
  margin: 0 0 0.85rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}
.location-banner.location-off {
  border-color: #fecaca;
  background: #fef2f2;
}
.location-row {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.location-label {
  font-size: 0.8rem;
  color: #64748b;
}
.location-action {
  margin: 0.35rem 0 0;
  color: #475569;
}
.location-warn {
  margin: 0.4rem 0 0;
  color: #b91c1c;
  font-weight: 500;
}
.log-fold {
  margin-top: 1rem;
}
.log-fold summary {
  cursor: pointer;
  margin-bottom: 0.5rem;
}
.exec-log-scroll.compact {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 0.65rem 0.75rem;
}
.fa-log-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.fa-log-card {
  padding: 0.5rem 0.65rem;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e2e8f0;
  font-size: 0.85rem;
}
.fa-log-card.page {
  border-left: 3px solid #2563eb;
}
.fa-log-card.feature {
  border-left: 3px solid #16a34a;
}
.fa-log-card.step {
  border-left: 3px solid #7c3aed;
}
.fa-log-card.error {
  border-left: 3px solid #dc2626;
  background: #fef2f2;
}
.fa-log-card.done {
  border-left: 3px solid #0d9488;
}
.fa-log-meta {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.fa-log-title {
  font-weight: 600;
  color: #0f172a;
}
.fa-log-tag {
  font-size: 0.75rem;
  color: #64748b;
}
.fa-log-body {
  margin: 0.25rem 0 0;
  color: #334155;
  word-break: break-word;
}
.back-row {
  display: flex;
  gap: 1rem;
  margin: 0 0 0.5rem;
}
.back-link {
  font-size: 0.9rem;
  color: #2563eb;
  text-decoration: none;
}
.back-link:hover {
  text-decoration: underline;
}
.page-head h1 {
  margin: 0 0 0.35rem;
}
.project-sub,
.hint {
  color: #64748b;
  font-size: 0.92rem;
}
.block {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1rem 1.15rem;
  margin-bottom: 1rem;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.85rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.88rem;
}
.field input,
.field select {
  padding: 0.45rem 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.field-wide {
  grid-column: 1 / -1;
}
.btn-link {
  margin-left: 0.5rem;
  border: none;
  background: none;
  color: #2563eb;
  cursor: pointer;
  text-decoration: underline;
  font-size: 0.82rem;
}
.btn-link.danger {
  color: #b91c1c;
}
.app-source {
  margin: 1rem 0 0.75rem;
}
.radio-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.sub-block {
  margin-top: 0.75rem;
}
.platform-hint {
  margin: 0.25rem 0 0.75rem;
  grid-column: 1 / -1;
}
.platform-hint.err {
  color: #b91c1c;
}
.catalog-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}
.device-hint {
  font-weight: normal;
  font-size: 0.82rem;
}
.installed-panel {
  margin-top: 0.5rem;
}
.dim-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0 0.85rem;
}
.dim-tab {
  padding: 0.35rem 0.9rem;
  border: 1px solid #cbd5e1;
  border-radius: 999px;
  background: #f8fafc;
  color: #334155;
  font-size: 0.86rem;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.dim-tab:hover:not(:disabled) {
  border-color: #94a3b8;
  background: #f1f5f9;
}
.dim-tab.active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}
.dim-tab.disabled:not(.active) {
  opacity: 0.55;
}
.dim-panel {
  padding: 0.85rem 0.95rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fafbfc;
}
.dim-panel-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 0.75rem;
  margin: 0 0 0.65rem;
  font-size: 0.88rem;
}
.dim-platform {
  font-weight: 600;
  color: #0f172a;
}
.dim-empty {
  margin: 0.5rem 0 0;
  padding: 0.65rem 0.85rem;
  border: 1px dashed #e2e8f0;
  border-radius: 8px;
}
.uploaded-panel {
  margin-top: 0.5rem;
}
.upload-file-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.upload-file-input {
  flex: 1;
  min-width: 0;
  padding: 0.4rem 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.88rem;
  background: #fff;
}
.btn-install-inline {
  flex-shrink: 0;
  padding: 0.42rem 1.1rem;
  font-size: 0.88rem;
  line-height: 1.25;
  white-space: nowrap;
}
.selected-app-readonly {
  margin-top: 1rem;
  padding: 0.85rem 0.95rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.readonly-row {
  display: grid;
  grid-template-columns: 5.5rem 1fr;
  gap: 0.5rem 0.75rem;
  align-items: center;
  margin-bottom: 0.55rem;
  font-size: 0.88rem;
}
.readonly-row:last-of-type {
  margin-bottom: 0.35rem;
}
.readonly-label {
  color: #64748b;
}
.readonly-value {
  color: #0f172a;
  font-weight: 500;
  word-break: break-all;
}
.readonly-hint {
  margin: 0.35rem 0 0;
}
.form-actions,
.start-hint {
  margin: 0.5rem 0 0;
}
.warn-banner {
  margin: 0.65rem 0 0;
  padding: 0.55rem 0.75rem;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  color: #92400e;
}
.confirm-row {
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 1rem;
}
.status-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.pill {
  font-size: 0.78rem;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
  background: #e2e8f0;
}
.pill.ok {
  background: #dcfce7;
  color: #166534;
}
.pill.bad {
  background: #fee2e2;
  color: #991b1b;
}
.pill.warn {
  background: #fef9c3;
  color: #854d0e;
}
.metrics {
  display: flex;
  gap: 1.5rem;
  margin: 0.75rem 0;
}
.metric .label {
  display: block;
  font-size: 0.78rem;
  color: #64748b;
}
.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.tbl th,
.tbl td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.4rem 0.5rem;
  text-align: left;
}
.cell-input {
  width: 100%;
  padding: 0.35rem 0.45rem;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
}
.ver-input {
  min-width: 160px;
  padding: 0.45rem 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}
.banner.err {
  background: #fef2f2;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
}
.err {
  color: #b91c1c;
}
.ok-msg {
  color: #166534;
}
.muted {
  color: #64748b;
}
.small {
  font-size: 0.85rem;
}
</style>

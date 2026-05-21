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

    <section v-if="editableFeatures.length && run?.status === 'success'" class="card block">
      <h2>功能菜单树（可编辑）</h2>
      <p class="muted small">确认后将保存为新版本，可在「功能树记录」中查看。</p>
      <div class="table-wrap">
        <table class="tbl">
          <thead>
            <tr>
              <th>路径</th>
              <th>区域</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in editableFeatures" :key="row._key">
              <td>
                <input v-model="row.pathText" class="cell-input" type="text" />
              </td>
              <td><input v-model="row.region" class="cell-input" type="text" /></td>
              <td>
                <button type="button" class="btn-link danger" @click="removeRow(i)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <button type="button" class="btn" @click="addRow">添加一行</button>
      <div class="confirm-row">
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
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";
import {
  analysisRobotUnselectableHint,
  isRobotRunnableForFeatureAnalysis,
} from "@/constants/robotCatalog";
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
const editableFeatures = ref([]);
const confirmLabel = ref("");
const confirming = ref(false);
const confirmErr = ref("");
const confirmOk = ref("");
let pollTimer = null;

const apiBase = computed(() => `/api/projects/${projectId.value}/feature-analysis`);

const analysisRobots = computed(() =>
  (robots.value || []).filter((r) => String(r.catalog_robot_id || "") === "test_analysis"),
);

const running = computed(() => {
  const s = run.value?.status;
  return s === "pending" || s === "running";
});

const canStart = computed(() => {
  if (form.robot_instance_id <= 0) return false;
  if (
    !isRobotRunnableForFeatureAnalysis(
      analysisRobots.value.find((r) => r.id === form.robot_instance_id),
    )
  ) {
    return false;
  }
  if (form.app_source === "installed") {
    return form.bundle_id.trim().includes(".");
  }
  return uploadInstallSucceeded.value && form.bundle_id.trim().includes(".");
});

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

function parseTreeToRows(tree) {
  const feats = tree?.features || [];
  return feats.map((f, i) => ({
    _key: f.id || `f-${i}`,
    pathText: Array.isArray(f.path) ? f.path.join(" > ") : f.name || "",
    region: f.region || "",
    name: f.name || "",
  }));
}

function rowsToTreeJson() {
  const base = run.value?.feature_json ? JSON.parse(run.value.feature_json) : { features: [] };
  base.features = editableFeatures.value.map((row, i) => {
    const parts = row.pathText.split(">").map((s) => s.trim()).filter(Boolean);
    const name = parts.length ? parts[parts.length - 1] : row.pathText.trim();
    return {
      id: String(i + 1),
      name,
      path: parts.length ? parts : [name],
      depth: parts.length || 1,
      region: row.region || "other",
      status: "listed",
    };
  });
  return base;
}

function syncEditableFromRun() {
  if (!run.value?.feature_json) {
    editableFeatures.value = [];
    return;
  }
  try {
    const tree = JSON.parse(run.value.feature_json);
    editableFeatures.value = parseTreeToRows(tree);
  } catch {
    editableFeatures.value = [];
  }
}

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

async function loadRobots() {
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    robots.value = data || [];
    const first = analysisRobots.value.find((r) => isRobotRunnableForFeatureAnalysis(r));
    if (first && !form.robot_instance_id) form.robot_instance_id = first.id;
  } catch (e) {
    pageErr.value = formatApiError(e);
  }
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
    if (data.status === "success") syncEditableFromRun();
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

function addRow() {
  editableFeatures.value.push({ _key: `new-${Date.now()}`, pathText: "", region: "other", name: "" });
}

function removeRow(i) {
  editableFeatures.value.splice(i, 1);
}

async function confirmTree() {
  if (!runId.value) return;
  confirming.value = true;
  confirmErr.value = "";
  confirmOk.value = "";
  try {
    const tree_json = rowsToTreeJson();
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
  max-width: 1000px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
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

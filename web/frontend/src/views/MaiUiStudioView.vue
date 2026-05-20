<template>
  <div class="mai-ui-studio">
    <header class="page-head">
      <h1>MAI-UI 识图</h1>
      <p class="hint">
        上传 APP 截图，自动识别<strong>当前页面全部菜单</strong>（顶部标题栏/顶栏 Tab、底部 Tab、侧栏等），无需手动指定。请先启动
        <code>mai_ui_tech/scripts/serve_grounding_mlx.sh</code>。
      </p>
    </header>

    <section class="card block status-block">
      <div class="status-head">
        <h2>模型运行情况</h2>
        <button type="button" class="btn" :disabled="statusLoading" @click="loadStatus">
          {{ statusLoading ? "刷新中…" : "刷新" }}
        </button>
      </div>
      <p v-if="statusError" class="banner err">{{ statusError }}</p>
      <div v-else-if="status" class="status-grid">
        <div class="metric">
          <span class="label">服务状态</span>
          <strong :class="status.reachable ? 'ok' : 'bad'">
            {{ status.reachable ? "正常" : "不可用" }}
          </strong>
        </div>
        <div v-if="status.backend === 'mlx_vlm'" class="metric">
          <span class="label">模型加载</span>
          <strong :class="status.grounding_worker_ready ? 'ok' : 'bad'">
            {{ status.grounding_worker_ready ? "已加载" : "未启动" }}
          </strong>
        </div>
        <div class="metric">
          <span class="label">推理后端</span>
          <strong>{{ status.backend || "—" }}</strong>
        </div>
        <div class="metric">
          <span class="label">Grounding 服务</span>
          <strong class="mono small">{{ status.grounding_url || "—" }}</strong>
        </div>
        <p class="muted small full">{{ status.message }}</p>
      </div>
      <p v-else class="muted">点击刷新检查推理服务。</p>
    </section>

    <section class="card block work-block">
      <h2>页面菜单识别</h2>

      <div class="form-panel">
        <label class="field">
          <span>上传截图</span>
          <input type="file" accept="image/png,image/jpeg,image/webp" @change="onFileChange" />
        </label>
        <div class="form-actions">
          <button
            type="button"
            class="btn primary"
            :disabled="!previewUrl || detectLoading || !status?.reachable"
            @click="runMenuDetect"
          >
            {{ detectLoading ? "识别中…" : "识别全部菜单" }}
          </button>
          <p v-if="!status?.reachable" class="muted small">
            请先启动 Grounding 服务并刷新状态。
          </p>
        </div>
      </div>

      <p v-if="detectError" class="banner err">{{ detectError }}</p>

      <div class="preview-results-layout">
        <div class="preview-col">
          <h3 class="col-title">截图预览</h3>
          <div v-if="previewUrl" class="preview-wrap">
            <img ref="imgRef" :src="previewUrl" class="preview-img" alt="截图预览" @load="onImgLoad" />
            <template v-for="(m, i) in successMenus" :key="i">
              <span
                v-if="m.coordinate_px"
                class="marker"
                :style="markerStyle(m)"
                :title="m.name"
              />
            </template>
          </div>
          <p v-else class="muted preview-placeholder">上传截图后在此预览，识别到的菜单位置会标在图上。</p>
        </div>

        <div class="results-col">
          <h3 class="col-title">识别结果</h3>
          <div v-if="detectLoading" class="results-empty muted">识别中，请稍候…</div>
          <template v-else-if="menuResponse">
            <p class="muted small results-meta">
              图尺寸 {{ menuResponse.image_width }} × {{ menuResponse.image_height }} ·
              共 {{ menuRows.length }} 项
            </p>
            <div v-if="menuRows.length" class="table-wrap">
              <table class="menu-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>区域</th>
                    <th>菜单名称</th>
                    <th>像素坐标</th>
                    <th>0–999</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(m, i) in menuRows" :key="i" :class="{ 'row-fail': !m.ok }">
                    <td>{{ i + 1 }}</td>
                    <td>{{ regionLabel(m.region) }}</td>
                    <td>{{ m.name || "—" }}</td>
                    <td class="mono">
                      {{ m.ok && m.coordinate_px ? m.coordinate_px.join(", ") : "—" }}
                    </td>
                    <td class="mono">
                      {{ m.ok && m.coordinate_999 ? m.coordinate_999.join(", ") : "—" }}
                    </td>
                    <td>
                      <span :class="m.ok ? 'tag ok' : 'tag bad'">
                        {{ m.ok ? "成功" : m.error || "失败" }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="results-empty muted">未识别到菜单项。</p>
            <details v-if="menuResponse.thinking" class="thinking-block">
              <summary>推理过程</summary>
              <pre>{{ menuResponse.thinking }}</pre>
            </details>
          </template>
          <p v-else class="results-empty muted">上传截图并点击「识别全部菜单」后，结果将显示在表格中。</p>
        </div>
      </div>
    </section>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import client, { formatApiError } from "@/api/client";

const status = ref(null);
const statusLoading = ref(false);
const statusError = ref("");
let statusTimer = null;

const previewUrl = ref("");
const selectedFile = ref(null);
const imgRef = ref(null);
const displaySize = ref({ w: 0, h: 0 });

const detectLoading = ref(false);
const detectError = ref("");
const menuResponse = ref(null);

const REGION_ORDER = { top: 0, bottom: 1, left: 2, right: 3, other: 4 };

const menuRows = computed(() => {
  const rows = menuResponse.value?.menus ?? [];
  return [...rows].sort(
    (a, b) =>
      (REGION_ORDER[a.region] ?? 9) - (REGION_ORDER[b.region] ?? 9) ||
      String(a.name).localeCompare(String(b.name), "zh"),
  );
});
const successMenus = computed(() =>
  menuRows.value.filter((m) => m.ok && m.coordinate_px)
);

async function loadStatus() {
  statusLoading.value = true;
  statusError.value = "";
  try {
    const { data } = await client.get("/api/mai-ui/status");
    status.value = data;
  } catch (e) {
    statusError.value = formatApiError(e);
    status.value = null;
  } finally {
    statusLoading.value = false;
  }
}

function onFileChange(ev) {
  const f = ev.target.files?.[0];
  if (!f) return;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  selectedFile.value = f;
  previewUrl.value = URL.createObjectURL(f);
  menuResponse.value = null;
  detectError.value = "";
}

function onImgLoad() {
  const el = imgRef.value;
  if (!el) return;
  displaySize.value = { w: el.clientWidth, h: el.clientHeight };
}

const REGION_LABELS = {
  top: "顶部",
  bottom: "底部",
  left: "左侧",
  right: "右侧",
  other: "其他",
};

function regionLabel(region) {
  if (!region) return "—";
  return REGION_LABELS[region] || region;
}

function markerStyle(m) {
  const iw = menuResponse.value?.image_width || 1;
  const ih = menuResponse.value?.image_height || 1;
  const [px, py] = m.coordinate_px;
  const dw = displaySize.value.w || imgRef.value?.clientWidth || iw;
  const dh = displaySize.value.h || imgRef.value?.clientHeight || ih;
  return {
    left: `${(px / iw) * dw}px`,
    top: `${(py / ih) * dh}px`,
  };
}

async function runMenuDetect() {
  if (!selectedFile.value) return;
  detectLoading.value = true;
  detectError.value = "";
  menuResponse.value = null;
  const fd = new FormData();
  fd.append("file", selectedFile.value);

  try {
    const { data } = await client.post("/api/mai-ui/detect-menus", fd, {
      timeout: 300000,
    });
    menuResponse.value = data;
    requestAnimationFrame(onImgLoad);
  } catch (e) {
    if (e.response?.status === 404) {
      detectError.value =
        "接口 /api/mai-ui/detect-menus 不存在，请重启 Web 后端（uvicorn）以加载最新代码后重试。";
    } else {
      detectError.value = formatApiError(e);
    }
  } finally {
    detectLoading.value = false;
  }
}

function onPreviewResize() {
  requestAnimationFrame(onImgLoad);
}

onMounted(() => {
  loadStatus();
  statusTimer = setInterval(loadStatus, 20000);
  window.addEventListener("resize", onPreviewResize);
});

onUnmounted(() => {
  if (statusTimer) clearInterval(statusTimer);
  window.removeEventListener("resize", onPreviewResize);
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
});
</script>

<style scoped>
.mai-ui-studio {
  max-width: 1280px;
  margin: 0 auto;
  padding: 1rem 1.25rem 2rem;
}
.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}
.hint {
  color: var(--text-muted);
  margin: 0 0 1.25rem;
  font-size: 0.92rem;
  line-height: 1.5;
}
.hint code {
  font-size: 0.85em;
  background: var(--bg-subtle);
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.block {
  margin-bottom: 1.25rem;
  padding: 1rem 1.15rem;
}
.status-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.75rem;
}
.status-head h2 {
  margin: 0;
  font-size: 1.1rem;
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem 1rem;
}
.metric .label {
  display: block;
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}
.metric strong.ok {
  color: #15803d;
}
.metric strong.bad {
  color: #b91c1c;
}
.mono {
  font-family: ui-monospace, monospace;
  font-size: 0.85em;
}
.small {
  font-size: 0.88rem;
}
.full {
  grid-column: 1 / -1;
}
.form-panel {
  margin-bottom: 1rem;
}
.form-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1rem;
}
.form-actions .muted {
  margin: 0;
}
.field {
  display: block;
  margin-bottom: 0.85rem;
}
.field span {
  display: block;
  font-size: 0.88rem;
  margin-bottom: 0.35rem;
  color: var(--text-secondary);
}
.btn.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.btn.primary:hover:not(:disabled) {
  background: var(--accent-strong);
}
.btn.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.preview-results-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1.25rem;
  align-items: start;
}
@media (max-width: 900px) {
  .preview-results-layout {
    grid-template-columns: 1fr;
  }
}
.col-title {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-secondary);
}
.preview-col {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.results-col {
  min-width: 0;
}
.results-empty {
  margin: 0;
  padding: 1rem;
  border: 1px dashed var(--border-tech);
  border-radius: var(--radius-md);
  font-size: 0.9rem;
  line-height: 1.5;
}
.results-meta {
  margin: 0 0 0.65rem;
}
.preview-wrap {
  position: relative;
  display: inline-block;
  width: fit-content;
  max-width: 100%;
  line-height: 0;
  border: 1px solid var(--border-tech);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: #f1f5f9;
}
.preview-img {
  display: block;
  width: auto;
  height: auto;
  max-width: 100%;
  max-height: min(72vh, 640px);
  object-fit: contain;
  object-position: center;
}
.preview-placeholder {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed var(--border-tech);
  border-radius: var(--radius-md);
  padding: 1rem;
  text-align: center;
}
.marker {
  position: absolute;
  width: 14px;
  height: 14px;
  margin: -7px 0 0 -7px;
  border-radius: 50%;
  background: #ef4444;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.25);
  pointer-events: none;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border-tech);
  border-radius: var(--radius-md);
  max-height: min(72vh, 640px);
}
.menu-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.menu-table th,
.menu-table td {
  padding: 0.5rem 0.65rem;
  text-align: left;
  border-bottom: 1px solid var(--border-subtle);
}
.menu-table th {
  background: var(--bg-subtle);
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
}
.menu-table tbody tr:last-child td {
  border-bottom: none;
}
.menu-table tbody tr:hover {
  background: rgba(0, 0, 0, 0.02);
}
.row-fail {
  background: #fef2f2;
}
.tag {
  display: inline-block;
  padding: 0.1em 0.45em;
  border-radius: 4px;
  font-size: 0.8rem;
}
.tag.ok {
  background: #dcfce7;
  color: #15803d;
}
.tag.bad {
  background: #fee2e2;
  color: #b91c1c;
}
.thinking-block {
  margin-top: 0.75rem;
  font-size: 0.88rem;
}
.thinking-block pre {
  margin: 0.35rem 0 0;
  font-size: 0.8rem;
  white-space: pre-wrap;
  max-height: 120px;
  overflow: auto;
}
.back {
  margin-top: 1rem;
}
</style>

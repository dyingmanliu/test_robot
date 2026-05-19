<template>
  <div class="cases-shell">
    <p class="br-line muted">
      <router-link to="/">工作台</router-link>
      · 用例归属<strong>项目空间</strong>（绑定被测应用与测试目标）；不同客户/应用独立项目，便于协作与隔离。
      <router-link to="/projects">管理项目空间</router-link>
    </p>
    <p v-if="auth.companyInternalShare" class="banner share-hint">
      公司已开启<strong>项目与用例公司内部共享</strong>：可查看同事项目与用例；编辑、删除与导入仍仅限本人创建的用例。
    </p>

    <div v-if="projectsLoaded && !projects.length" class="banner warn">
      尚未创建项目空间。请先到
      <router-link to="/projects">项目空间</router-link>
      新建并绑定被测应用与测试目标。
    </div>
    <div class="toolbar">
      <div class="toolbar-left">
        <h1 class="title">测试用例</h1>
        <label v-if="projects.length" class="proj-picker">
          <span class="picker-label">当前项目空间</span>
          <select v-model.number="selectedProjectId" @change="onProjectChange">
            <option v-for="p in projects" :key="p.id" :value="p.id">
              {{ p.name }} · {{ p.tested_app_name }}
            </option>
          </select>
        </label>
      </div>
      <div class="actions">
        <router-link
          v-if="selectedProjectId"
          class="btn"
          :to="{ name: 'projectDashboard', params: { projectId: selectedProjectId } }"
        >
          项目看板
        </router-link>
        <div ref="createMenuRef" class="create-case-wrap">
          <button
            type="button"
            class="btn primary create-case-trigger"
            :disabled="!selectedProjectId"
            :aria-expanded="createMenuOpen"
            aria-haspopup="menu"
            @click.stop="toggleCreateMenu"
          >
            创建用例
            <span class="create-case-caret" aria-hidden="true">▾</span>
          </button>
          <div v-if="createMenuOpen && selectedProjectId" class="create-case-menu" role="menu">
            <button type="button" class="create-case-item" role="menuitem" @click="startManualCreate">
              手工创建
            </button>
            <button
              type="button"
              class="create-case-item"
              role="menuitem"
              :disabled="genDialog.loading"
              @click="startAutoCreate"
            >
              自动生成
            </button>
          </div>
        </div>
        <label class="btn import-label">
          导入 CSV/Excel
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            class="hidden-file"
            :disabled="!selectedProjectId"
            @change="onImportFile"
          />
        </label>
        <button
          type="button"
          class="btn"
          :disabled="!selectedProjectId || !selectedIds.length || running || !canStartExecution"
          @click="runSelected"
        >
          {{ running ? "执行中…" : "执行测试" }}
        </button>
      </div>
    </div>

    <div v-if="projectsLoaded && !robotInstances.length" class="banner warn">
      执行用例需绑定已租用的机器人实例。请先到
      <router-link to="/marketplace">机器人商城</router-link>
      提交租用申请，管理员审批通过后到
      <router-link to="/my-robots">我的机器人</router-link>
      查看编号与属性，再回到本页选择实例后执行。
    </div>
    <div
      v-else-if="projectsLoaded && needsMidsceneForSelection && !midsceneRobotInstances.length"
      class="banner warn"
    >
      已选 YAML 用例须使用 <strong>Midscene（HarmonyOS / HDC）</strong> 机器人执行。当前公司下尚无 Midscene 实例，请到
      <router-link to="/my-robots">我的机器人</router-link>
      打开任一实例，将「测试执行引擎」改为 Midscene 后保存；或联系管理员审批新租用单时选择 Midscene 引擎。
    </div>
    <div v-else-if="projectsLoaded && robotInstances.length" class="robot-pick">
      <div class="robot-pick-row">
        <label class="robot-pick-inner">
          <span class="picker-label">执行用例使用的机器人实例</span>
          <select v-model.number="selectedRobotInstanceId" class="robot-select" @change="onRobotInstanceChange">
            <option
              v-for="ins in robotsForExecution"
              :key="ins.id"
              :value="ins.id"
              :disabled="robotOptionDisabled(ins)"
            >
              {{ ins.instance_code }} · {{ (ins.display_name || "").trim() || ins.catalog_robot_id }} ·
              {{ agentEngineLabel(ins.test_agent_backend) }}
              <template v-if="robotOptionDisabled(ins)">（不可用于 YAML）</template>
            </option>
          </select>
        </label>
        <label class="robot-pick-inner">
          <span class="picker-label">本次执行设备</span>
          <select v-model="selectedDevicePlatform" class="robot-select">
            <option value="android">Android / ADB</option>
            <option value="harmonyos">鸿蒙 HarmonyOS / HDC</option>
          </select>
        </label>
        <label class="robot-pick-inner robot-pick-inner--device">
          <span class="picker-label">
            目标终端
            <button
              type="button"
              class="link-btn"
              :disabled="devicesLoading"
              @click="loadConnectedDevices"
            >
              {{ devicesLoading ? "刷新中…" : "刷新" }}
            </button>
          </span>
          <select
            v-model="selectedDeviceId"
            class="robot-select"
            :disabled="devicesLoading || !onlineDevices.length"
          >
            <option v-if="!onlineDevices.length" value="">
              {{ devicesError || "未检测到在线设备" }}
            </option>
            <option v-for="d in onlineDevices" :key="d.device_id" :value="d.device_id">
              {{ d.label }}
              <template v-if="d.state !== 'device'">（{{ d.state }}）</template>
            </option>
          </select>
        </label>
      </div>
      <p class="robot-hint muted small">
        同一机器人可在执行前选择平台与具体终端（ADB 序列号 / HDC target）；默认平台取自「我的机器人」（当前：
        <strong>{{ defaultPlatformLabel }}</strong>）。
      </p>
      <p v-if="needsMidsceneForSelection" class="robot-hint muted small">
        已选 YAML 用例，请选用标注为 <strong>Midscene</strong> 的机器人（如 DR-000008 · 机器人贾维斯）。
      </p>
    </div>

    <div v-if="loadError" class="banner err">{{ loadError }}</div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th class="narrow">
              <input type="checkbox" :checked="allSelected" @change="toggleAll" />
            </th>
            <th>标题</th>
            <th>优先级</th>
            <th>格式</th>
            <th>步骤</th>
            <th>执行说明</th>
            <th class="narrow">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cases" :key="c.id">
            <td>
              <input type="checkbox" :value="c.id" v-model="selectedIds" />
            </td>
            <td>{{ c.title }}</td>
            <td>{{ c.priority || "—" }}</td>
            <td class="muted small">{{ formatLabel(c.case_format) }}</td>
            <td class="muted small">{{ stepPreview(c) }}</td>
            <td class="task">{{ truncate(c.task_text, 80) }}</td>
            <td class="ops">
              <button type="button" class="linkish" @click="openEdit(c)">编辑</button>
              <button type="button" class="linkish" @click="openVersions(c)">版本</button>
              <button type="button" class="linkish danger" @click="remove(c)">删除</button>
            </td>
          </tr>
          <tr v-if="!cases.length && !loading">
            <td colspan="7" class="empty">暂无数据，点击「创建用例」开始。</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="loading" class="muted">加载中…</p>

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
            :robot-instance-id="selectedRobotInstanceId"
            :device-platform="selectedDevicePlatform"
            :device-id="selectedDeviceId"
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

    <div v-if="resultRuns.length" class="panel">
      <h2>执行结果</h2>
      <div v-for="r in resultRuns" :key="r.id" class="run-block">
        <div class="run-head">
          <span class="badge" :class="r.status">{{ statusLabel(r.status) }}</span>
          <span class="muted small">运行 ID: {{ r.id }} · 用例 ID: {{ r.case_id }}</span>
        </div>
        <div v-if="r.step_log" class="exec-console exec-console--result">
          <aside class="exec-screen-pane">
            <DeviceScreenMirror
              :robot-instance-id="selectedRobotInstanceId"
              :device-platform="selectedDevicePlatform"
              :device-id="selectedDeviceId"
              :active="false"
            />
          </aside>
          <div class="exec-log-pane">
            <h3 class="exec-log-title">执行过程</h3>
            <div class="exec-log-scroll">
              <div class="steps">
                <div
                  v-for="(st, idx) in parseStepLog(r.step_log)"
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
        <pre v-if="r.output_message" class="out summary">{{ r.output_message }}</pre>
        <pre v-if="r.error_trace" class="out err">{{ r.error_trace }}</pre>
        <div v-if="r.id" class="report-download">
          <p class="report-desc">
            测试执行已结束。可下载 Midscene 可视化测试报告（HTML），查看步骤截图与详细执行过程。
          </p>
          <button
            v-if="r.has_report"
            type="button"
            class="report-link"
            @click="downloadReport(r.id)"
          >
            下载测试报告
          </button>
          <p v-else class="muted small report-none">
            本次执行未生成可下载报告（非 Midscene 引擎或执行未产出报告文件）。
          </p>
        </div>
      </div>
    </div>

    <p v-if="importMsg" class="banner ok">{{ importMsg }}</p>

    <div v-if="genDialog.open" class="modal-overlay" @click.self="closeGenerate">
      <div class="modal">
        <h3>自动生成用例</h3>
        <p class="muted small">
          用一句话描述要测什么；LLM 先生成结构化步骤，若选择 YAML 将自动转为 Midscene 脚本。保存前可在编辑页核对或切换格式。
        </p>
        <fieldset class="field format-field">
          <span class="format-label">生成格式</span>
          <label class="format-opt">
            <input v-model="genDialog.case_format" type="radio" value="structured" :disabled="genDialog.loading" />
            结构化（步骤 + 执行说明）
          </label>
          <label class="format-opt">
            <input v-model="genDialog.case_format" type="radio" value="yaml" :disabled="genDialog.loading" />
            Midscene YAML（须使用 Midscene 机器人执行）
          </label>
        </fieldset>
        <label class="field">
          <span>测试描述</span>
          <textarea
            v-model="genDialog.prompt"
            rows="4"
            maxlength="2000"
            placeholder="例如：已登录用户从首页进入购物车并完成结算"
            :disabled="genDialog.loading"
          ></textarea>
        </label>
        <p v-if="genDialog.error" class="err">{{ genDialog.error }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" :disabled="genDialog.loading" @click="closeGenerate">
            取消
          </button>
          <button type="button" class="btn primary" :disabled="genDialog.loading" @click="submitGenerate">
            {{ genDialog.loading ? "生成中…" : "生成" }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="dialog.open" class="modal-overlay" @click.self="dialog.open = false">
      <div class="modal modal-wide">
        <h3>{{ dialog.editing ? "编辑用例" : "新建用例" }}</h3>
        <label class="field">
          <span>标题</span>
          <input v-model="dialog.title" maxlength="256" />
        </label>
        <label class="field">
          <span>优先级</span>
          <select v-model="dialog.priority">
            <option value="P0">P0 — 最高</option>
            <option value="P1">P1</option>
            <option value="P2">P2 — 默认</option>
            <option value="P3">P3</option>
          </select>
        </label>
        <fieldset class="field format-field">
          <span class="format-label">用例格式</span>
          <label class="format-opt">
            <input
              :checked="dialog.case_format === 'structured'"
              type="radio"
              value="structured"
              :disabled="dialog.formatConverting"
              @change="switchCaseFormat('structured')"
            />
            结构化（步骤 + 执行说明）
          </label>
          <label class="format-opt">
            <input
              :checked="dialog.case_format === 'yaml'"
              type="radio"
              value="yaml"
              :disabled="dialog.formatConverting"
              @change="switchCaseFormat('yaml')"
            />
            Midscene YAML（须使用 Midscene 机器人执行）
          </label>
          <span v-if="dialog.formatConverting" class="muted small">格式转换中…</span>
        </fieldset>
        <template v-if="dialog.case_format === 'yaml'">
          <label class="field">
            <span>Midscene YAML 脚本</span>
            <textarea
              v-model="dialog.case_yaml"
              class="yaml-editor"
              rows="16"
              spellcheck="false"
              placeholder="须包含 tasks: 段"
            ></textarea>
          </label>
          <p class="muted small">
            参考
            <a href="https://midscenejs.com/automate-with-scripts-in-yaml" target="_blank" rel="noopener"
              >Midscene YAML 文档</a
            >。设备由服务端 HDC 连接。
          </p>
          <button type="button" class="btn ghost mini" @click="fillYamlTemplate">填入示例模板</button>
        </template>
        <template v-else>
        <label class="field">
          <span>前置条件</span>
          <textarea v-model="dialog.preconditions" rows="2" placeholder="环境、账号、数据准备等"></textarea>
        </label>
        <div class="field">
          <span>测试步骤与预期结果</span>
          <div v-for="(s, idx) in dialog.steps" :key="idx" class="step-row">
            <span class="step-no">{{ idx + 1 }}</span>
            <input v-model="s.description" placeholder="步骤说明" />
            <input v-model="s.expected" placeholder="预期结果" />
            <button type="button" class="btn ghost mini" @click="removeStep(idx)">删</button>
          </div>
          <button type="button" class="btn" @click="addStep">添加步骤</button>
        </div>
        <label class="field">
          <span>执行说明（交给自动化 Agent，可与步骤合并）</span>
          <textarea v-model="dialog.task_text" rows="4"></textarea>
        </label>
        <p class="muted small">保存时至少需要「执行说明」或一条有效步骤。</p>
        </template>
        <p v-if="dialog.error" class="err">{{ dialog.error }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="dialog.open = false">取消</button>
          <button type="button" class="btn primary" @click="saveDialog">保存</button>
        </div>
      </div>
    </div>

    <div v-if="verDialog.open" class="modal-overlay" @click.self="verDialog.open = false">
      <div class="modal modal-wide">
        <h3>版本历史 · {{ verDialog.caseTitle }}</h3>
        <p v-if="verDialog.err" class="err">{{ verDialog.err }}</p>
        <div v-if="verDialog.loading" class="muted">加载中…</div>
        <table v-else class="ver-table">
          <thead>
            <tr>
              <th>版本号</th>
              <th>标题</th>
              <th>优先级</th>
              <th>保存时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="v in verDialog.items" :key="v.id">
              <td>v{{ v.revision_no }}</td>
              <td>{{ v.title }}</td>
              <td>{{ v.priority }}</td>
              <td>{{ fmtTime(v.created_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button type="button" class="btn ghost" @click="verDialog.open = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from "axios";
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";
import DeviceScreenMirror from "@/components/DeviceScreenMirror.vue";
import { useAuthStore } from "@/stores/auth";

/** 轮询时短暂断网、502 等不应立刻当作「执行失败」；401 等仍应立即失败 */
function isTransientPollError(e) {
  if (!axios.isAxiosError(e)) return false;
  if (!e.response) return true;
  const s = e.response.status;
  return s >= 500 || s === 408 || s === 429;
}

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const projects = ref([]);
const projectsLoaded = ref(false);
const selectedProjectId = ref(null);

const cases = ref([]);
const loading = ref(false);
const loadError = ref("");
const selectedIds = ref([]);
const running = ref(false);
const stopBusy = ref(false);
const liveRun = ref(null);
const resultRuns = ref([]);

const robotInstances = ref([]);
const selectedRobotInstanceId = ref(null);
const selectedDevicePlatform = ref("android");
const selectedDeviceId = ref("");
const connectedDevices = ref([]);
const devicesLoading = ref(false);
const devicesError = ref("");

const PLATFORM_STORAGE_PREFIX = "tcm_exec_platform_";
const DEVICE_ID_STORAGE_PREFIX = "tcm_exec_device_";

function normalizeDevicePlatform(value) {
  const p = String(value || "android").toLowerCase();
  return p === "harmonyos" ? "harmonyos" : "android";
}

function platformStorageKey(instanceId) {
  return `${PLATFORM_STORAGE_PREFIX}${instanceId}`;
}

function deviceIdStorageKey(instanceId, platform) {
  return `${DEVICE_ID_STORAGE_PREFIX}${instanceId}_${normalizeDevicePlatform(platform)}`;
}

const onlineDevices = computed(() =>
  connectedDevices.value.filter((d) => String(d.state || "").toLowerCase() === "device"),
);

const canStartExecution = computed(() => {
  if (!selectedRobotInstanceId.value) return false;
  if (devicesLoading.value) return false;
  return onlineDevices.value.length > 0 && !!selectedDeviceId.value;
});

function syncDevicePlatformFromInstance() {
  const ins = robotInstances.value.find((i) => i.id === selectedRobotInstanceId.value);
  if (!ins) return;
  const saved = sessionStorage.getItem(platformStorageKey(ins.id));
  selectedDevicePlatform.value = saved
    ? normalizeDevicePlatform(saved)
    : normalizeDevicePlatform(ins.device_platform);
}

async function loadConnectedDevices() {
  devicesLoading.value = true;
  devicesError.value = "";
  try {
    const { data } = await client.get("/api/devices/connected", {
      params: { platform: normalizeDevicePlatform(selectedDevicePlatform.value) },
    });
    connectedDevices.value = Array.isArray(data.devices) ? data.devices : [];
    const online = connectedDevices.value.filter(
      (d) => String(d.state || "").toLowerCase() === "device",
    );
    const insId = selectedRobotInstanceId.value;
    const saved =
      insId != null
        ? sessionStorage.getItem(deviceIdStorageKey(insId, selectedDevicePlatform.value))
        : null;
    if (saved && online.some((d) => d.device_id === saved)) {
      selectedDeviceId.value = saved;
    } else if (online.length) {
      selectedDeviceId.value = online[0].device_id;
    } else {
      selectedDeviceId.value = "";
    }
  } catch (e) {
    connectedDevices.value = [];
    selectedDeviceId.value = "";
    devicesError.value =
      typeof e.response?.data?.detail === "string"
        ? e.response.data.detail
        : "无法枚举设备，请确认 ADB/HDC 已安装且设备已连接";
  } finally {
    devicesLoading.value = false;
  }
}

function onRobotInstanceChange() {
  syncDevicePlatformFromInstance();
  loadConnectedDevices();
}

const defaultPlatformLabel = computed(() => {
  const ins = robotInstances.value.find((i) => i.id === selectedRobotInstanceId.value);
  return devicePlatformLabel(ins?.device_platform || selectedDevicePlatform.value);
});

const canStopRun = computed(() => {
  const r = liveRun.value;
  return !!(r && (r.status === "pending" || r.status === "running"));
});

const screenMirrorActive = computed(() => {
  const r = liveRun.value;
  return !!(r && (r.status === "pending" || r.status === "running"));
});

const liveLogScrollRef = ref(null);

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

const importMsg = ref("");

const DEFAULT_YAML_TEMPLATE = `# Midscene HarmonyOS 用例（runYaml 仅执行 tasks 段；设备由服务端 HDC 连接）
tasks:
  - name: 示例任务
    flow:
      - ai: 打开设置应用
      - sleep: 1000
      - aiAssert: 页面显示设置项列表
`;

const dialog = reactive({
  open: false,
  editing: false,
  id: null,
  title: "",
  task_text: "",
  preconditions: "",
  priority: "P2",
  case_format: "structured",
  case_yaml: "",
  steps: [],
  error: "",
  formatConverting: false,
});

const genDialog = reactive({
  open: false,
  prompt: "",
  case_format: "structured",
  loading: false,
  error: "",
});

const createMenuOpen = ref(false);
const createMenuRef = ref(null);

const verDialog = reactive({
  open: false,
  loading: false,
  err: "",
  items: [],
  caseTitle: "",
});

const allSelected = computed(() => {
  return cases.value.length > 0 && selectedIds.value.length === cases.value.length;
});

function isMidsceneBackend(backend) {
  return String(backend || "autoglm").toLowerCase() === "midscene";
}

const needsMidsceneForSelection = computed(() => {
  const idSet = new Set(selectedIds.value);
  return cases.value.some(
    (c) => idSet.has(c.id) && String(c.case_format || "").toLowerCase() === "yaml",
  );
});

const midsceneRobotInstances = computed(() =>
  robotInstances.value.filter((ins) => isMidsceneBackend(ins.test_agent_backend)),
);

const robotsForExecution = computed(() => robotInstances.value);

function robotOptionDisabled(ins) {
  return needsMidsceneForSelection.value && !isMidsceneBackend(ins.test_agent_backend);
}

function syncRobotSelection() {
  if (!robotInstances.value.length) {
    selectedRobotInstanceId.value = null;
    return;
  }
  const current = robotInstances.value.find((ins) => ins.id === selectedRobotInstanceId.value);
  if (needsMidsceneForSelection.value) {
    const midscene = midsceneRobotInstances.value;
    if (!midscene.length) {
      selectedRobotInstanceId.value = null;
      return;
    }
    if (!current || !isMidsceneBackend(current.test_agent_backend)) {
      selectedRobotInstanceId.value = midscene[0].id;
    }
    return;
  }
  if (!current) {
    selectedRobotInstanceId.value = robotInstances.value[0].id;
  }
  syncDevicePlatformFromInstance();
  loadConnectedDevices();
}

watch([selectedIds, cases], () => syncRobotSelection(), { deep: true });

watch(selectedRobotInstanceId, () => syncDevicePlatformFromInstance());

watch(selectedDevicePlatform, (p) => {
  if (!selectedRobotInstanceId.value) return;
  sessionStorage.setItem(platformStorageKey(selectedRobotInstanceId.value), normalizeDevicePlatform(p));
  loadConnectedDevices();
});

watch(selectedDeviceId, (id) => {
  if (!selectedRobotInstanceId.value || !id) return;
  sessionStorage.setItem(
    deviceIdStorageKey(selectedRobotInstanceId.value, selectedDevicePlatform.value),
    id,
  );
});

async function loadProjects() {
  try {
    const { data } = await client.get("/api/projects");
    projects.value = data;
  } catch {
    projects.value = [];
  }
}

async function load() {
  loading.value = true;
  loadError.value = "";
  if (!selectedProjectId.value) {
    cases.value = [];
    loading.value = false;
    return;
  }
  try {
    const { data } = await client.get("/api/test-cases", {
      params: { project_id: selectedProjectId.value },
    });
    cases.value = data;
    selectedIds.value = selectedIds.value.filter((id) => data.some((c) => c.id === id));
  } catch (e) {
    loadError.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

function onProjectChange() {
  router.replace({ path: "/cases", query: { project: String(selectedProjectId.value) } });
  load();
  loadRobotInstances();
}

async function loadRobotInstances() {
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    robotInstances.value = Array.isArray(data) ? data : [];
    syncRobotSelection();
  } catch {
    robotInstances.value = [];
    selectedRobotInstanceId.value = null;
  }
}

async function bootstrapProjectContext() {
  await loadProjects();
  projectsLoaded.value = true;
  const raw = route.query.project;
  const want = raw ? parseInt(String(raw), 10) : NaN;
  if (projects.value.length) {
    if (!Number.isNaN(want) && projects.value.some((p) => p.id === want)) {
      selectedProjectId.value = want;
    } else {
      selectedProjectId.value = projects.value[0].id;
      router.replace({ path: "/cases", query: { project: String(selectedProjectId.value) } });
    }
  } else {
    selectedProjectId.value = null;
  }
  await load();
  await loadRobotInstances();
  if (selectedRobotInstanceId.value) {
    await loadConnectedDevices();
  }
}

function toggleAll(e) {
  if (e.target.checked) {
    selectedIds.value = cases.value.map((c) => c.id);
  } else {
    selectedIds.value = [];
  }
}

function truncate(s, n) {
  if (!s) return "—";
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function formatLabel(fmt) {
  return String(fmt || "structured").toLowerCase() === "yaml" ? "YAML" : "结构化";
}

function stepPreview(c) {
  if (String(c.case_format || "").toLowerCase() === "yaml") return "YAML";
  const n = Array.isArray(c.steps) ? c.steps.length : 0;
  return n ? `${n} 步` : "—";
}

function fillYamlTemplate() {
  if (!dialog.case_yaml.trim()) {
    dialog.case_yaml = DEFAULT_YAML_TEMPLATE;
  }
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function addStep() {
  dialog.steps.push({ description: "", expected: "" });
}

function removeStep(idx) {
  dialog.steps.splice(idx, 1);
}

function closeCreateMenu() {
  createMenuOpen.value = false;
}

function toggleCreateMenu() {
  if (!selectedProjectId.value) return;
  createMenuOpen.value = !createMenuOpen.value;
}

function startManualCreate() {
  closeCreateMenu();
  openCreate();
}

function startAutoCreate() {
  closeCreateMenu();
  openGenerate();
}

function onDocumentClick(ev) {
  if (!createMenuOpen.value) return;
  const el = createMenuRef.value;
  if (el && !el.contains(ev.target)) {
    closeCreateMenu();
  }
}

function openCreate() {
  if (!selectedProjectId.value) return;
  dialog.open = true;
  dialog.editing = false;
  dialog.id = null;
  dialog.title = "";
  dialog.task_text = "";
  dialog.preconditions = "";
  dialog.priority = "P2";
  dialog.case_format = "structured";
  dialog.case_yaml = "";
  dialog.steps = [{ description: "", expected: "" }];
  dialog.error = "";
}

function openGenerate() {
  if (!selectedProjectId.value) return;
  genDialog.open = true;
  genDialog.prompt = "";
  genDialog.case_format = "structured";
  genDialog.loading = false;
  genDialog.error = "";
}

function closeGenerate() {
  if (genDialog.loading) return;
  genDialog.open = false;
  genDialog.error = "";
}

function applyDraftToDialog(draft) {
  const fmt = String(draft.case_format || "structured").toLowerCase();
  dialog.title = draft.title || "";
  dialog.task_text = draft.task_text || "";
  dialog.preconditions = draft.preconditions || "";
  dialog.priority = draft.priority || "P2";
  dialog.case_format = fmt === "yaml" ? "yaml" : "structured";
  dialog.case_yaml = draft.case_yaml || "";
  const st = Array.isArray(draft.steps) ? draft.steps : [];
  dialog.steps = st.length
    ? st.map((x) => ({
        description: x.description || "",
        expected: x.expected || "",
      }))
    : [{ description: "", expected: "" }];
}

function openCreateWithDraft(draft) {
  if (!selectedProjectId.value) return;
  dialog.open = true;
  dialog.editing = false;
  dialog.id = null;
  applyDraftToDialog(draft);
  dialog.error = "";
  dialog.formatConverting = false;
}

async function switchCaseFormat(target) {
  if (!dialog.open || dialog.formatConverting) return;
  const current = dialog.case_format;
  if (current === target) return;
  const ok = window.confirm(
    `将用例从「${formatLabel(current)}」转为「${formatLabel(target)}」，会按规则转换当前内容（可再手动修改）。是否继续？`,
  );
  if (!ok) return;
  dialog.formatConverting = true;
  dialog.error = "";
  try {
    const { data } = await client.post("/api/test-cases/convert-format", {
      target_format: target,
      title: dialog.title.trim(),
      preconditions: (dialog.preconditions || "").trim(),
      steps: buildStepsPayload(),
      task_text: dialog.task_text.trim(),
      case_yaml: dialog.case_yaml || "",
    });
    applyDraftToDialog(data);
    dialog.case_format = target;
  } catch (e) {
    dialog.error = formatApiError(e);
  } finally {
    dialog.formatConverting = false;
  }
}

async function submitGenerate() {
  genDialog.error = "";
  const prompt = (genDialog.prompt || "").trim();
  if (!prompt) {
    genDialog.error = "请填写测试描述";
    return;
  }
  if (!selectedProjectId.value) {
    genDialog.error = "请先选择项目空间";
    return;
  }
  genDialog.loading = true;
  try {
    const { data } = await client.post("/api/test-cases/generate", {
      project_id: selectedProjectId.value,
      prompt,
      case_format: genDialog.case_format || "structured",
    });
    genDialog.open = false;
    openCreateWithDraft(data);
  } catch (e) {
    genDialog.error = formatApiError(e);
  } finally {
    genDialog.loading = false;
  }
}

function openEdit(c) {
  dialog.open = true;
  dialog.editing = true;
  dialog.id = c.id;
  dialog.title = c.title;
  dialog.task_text = c.task_text || "";
  dialog.preconditions = c.preconditions || "";
  dialog.priority = c.priority || "P2";
  dialog.case_format = c.case_format || "structured";
  dialog.case_yaml = c.case_yaml || "";
  const st = Array.isArray(c.steps) && c.steps.length ? c.steps : [];
  dialog.steps = st.length
    ? st.map((x) => ({
        description: x.description || "",
        expected: x.expected || "",
      }))
    : [{ description: "", expected: "" }];
  dialog.error = "";
}

async function openVersions(c) {
  verDialog.open = true;
  verDialog.caseTitle = c.title;
  verDialog.err = "";
  verDialog.loading = true;
  verDialog.items = [];
  try {
    const { data } = await client.get(`/api/test-cases/${c.id}/versions`);
    verDialog.items = data;
  } catch (e) {
    verDialog.err = formatApiError(e);
  } finally {
    verDialog.loading = false;
  }
}

function buildStepsPayload() {
  return dialog.steps
    .map((s, i) => ({
      order: i + 1,
      description: (s.description || "").trim(),
      expected: (s.expected || "").trim(),
    }))
    .filter((s) => s.description || s.expected);
}

async function saveDialog() {
  dialog.error = "";
  if (!dialog.title.trim()) {
    dialog.error = "请填写标题";
    return;
  }
  const stepsPayload = buildStepsPayload();
  if (dialog.case_format === "yaml") {
    if (!dialog.case_yaml.trim()) {
      dialog.error = "请填写 Midscene YAML 脚本";
      return;
    }
  } else if (!dialog.task_text.trim() && stepsPayload.length === 0) {
    dialog.error = "请填写执行说明或至少一条步骤";
    return;
  }
  try {
    const body = {
      title: dialog.title.trim(),
      task_text: dialog.task_text.trim(),
      preconditions: (dialog.preconditions || "").trim(),
      priority: dialog.priority,
      case_format: dialog.case_format,
      case_yaml: dialog.case_format === "yaml" ? dialog.case_yaml : "",
      steps: stepsPayload,
    };
    if (dialog.editing && dialog.id) {
      await client.patch(`/api/test-cases/${dialog.id}`, body);
    } else {
      await client.post("/api/test-cases", {
        project_id: selectedProjectId.value,
        ...body,
      });
    }
    dialog.open = false;
    await load();
  } catch (e) {
    dialog.error = formatApiError(e);
  }
}

async function onImportFile(ev) {
  const f = ev.target.files?.[0];
  importMsg.value = "";
  if (!f || !selectedProjectId.value) return;
  try {
    const fd = new FormData();
    fd.append("project_id", String(selectedProjectId.value));
    fd.append("file", f);
    const { data } = await client.post("/api/test-cases/import", fd);
    const errs = (data.errors || []).slice(0, 5).join("；");
    importMsg.value = `导入完成：新建 ${data.created} 条，跳过 ${data.skipped} 条${errs ? `。提示：${errs}` : ""}`;
    await load();
  } catch (e) {
    importMsg.value = formatApiError(e);
  } finally {
    ev.target.value = "";
  }
}

async function remove(c) {
  if (!confirm(`确定删除「${c.title}」？`)) return;
  await client.delete(`/api/test-cases/${c.id}`);
  selectedIds.value = selectedIds.value.filter((id) => id !== c.id);
  await load();
}

function agentEngineLabel(backend) {
  const b = String(backend || "autoglm").toLowerCase();
  if (b === "midscene") return "Midscene";
  return "AutoGLM";
}

function devicePlatformLabel(platform) {
  const p = String(platform || "android").toLowerCase();
  return p === "harmonyos" ? "鸿蒙" : "Android";
}

function statusLabel(s) {
  const m = {
    pending: "排队",
    running: "执行中",
    success: "成功",
    failed: "失败",
    cancelled: "已终止",
  };
  return m[s] || s;
}

function stepCount(run) {
  return parseStepLog(run?.step_log).length;
}

/** 根据状态与 step_log 条数估算进度（执行中最高约 95%，结束后 100%） */
function estimateRunProgress(run) {
  if (!run) return 0;
  const status = run.status;
  if (status === "success" || status === "failed" || status === "cancelled") {
    return 100;
  }
  if (status === "pending") return 8;
  const n = stepCount(run);
  if (n <= 0) return 12;
  const base = 12;
  const span = 83;
  const estimated = base + span * (1 - Math.exp(-n / 10));
  return Math.min(95, Math.round(estimated));
}

const runProgressPercent = computed(() => estimateRunProgress(liveRun.value));

async function stopRun() {
  const id = liveRun.value?.id;
  if (!id) return;
  stopBusy.value = true;
  try {
    await client.post(`/api/test-cases/runs/${id}/cancel`);
  } catch (e) {
    window.alert(e.response?.data?.detail || String(e.message || e));
  } finally {
    stopBusy.value = false;
  }
}

function parseStepLog(raw) {
  if (!raw || typeof raw !== "string") return [];
  return raw
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return { step: "?", thinking: line, action: null, message: "无法解析本行日志" };
      }
    });
}

function formatJson(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

async function downloadReport(runId) {
  if (!runId) return;
  try {
    const { data } = await client.get(`/api/test-cases/runs/${runId}/report`, {
      responseType: "blob",
    });
    const blob = new Blob([data], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `midscene-report-run-${runId}.html`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    window.alert(formatApiError(e));
  }
}

async function pollRun(runId, onTick) {
  const deadline = Date.now() + 2 * 60 * 60 * 1000;
  let transientStreak = 0;
  while (Date.now() < deadline) {
    try {
      const { data } = await client.get(`/api/test-cases/runs/${runId}`);
      transientStreak = 0;
      if (typeof onTick === "function") onTick(data);
      if (data.status === "success" || data.status === "failed" || data.status === "cancelled") {
        return data;
      }
    } catch (e) {
      if (isTransientPollError(e)) {
        transientStreak++;
        if (transientStreak > 120) {
          throw new Error(
            "长时间无法连接后端（网络或服务异常）。若正在使用 uvicorn --reload，保存文件会重启进程并中断未完成的自动化任务；长时间跑测时请去掉 --reload。"
          );
        }
      } else {
        throw e;
      }
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error("等待执行结果超时（超过 2 小时）");
}

async function runSelected() {
  if (!selectedIds.value.length) return;
  if (!selectedRobotInstanceId.value) {
    loadError.value = needsMidsceneForSelection.value
      ? "YAML 用例须选择 Midscene 机器人；请到「我的机器人」将实例引擎改为 Midscene"
      : "请先选择要使用的机器人实例";
    return;
  }
  if (!selectedDeviceId.value) {
    loadError.value = devicesError.value || "请先选择已连接的目标终端，或点击「刷新」重新扫描设备";
    return;
  }
  const picked = robotInstances.value.find((ins) => ins.id === selectedRobotInstanceId.value);
  if (needsMidsceneForSelection.value && picked && !isMidsceneBackend(picked.test_agent_backend)) {
    loadError.value = "YAML 用例须绑定 Midscene 机器人实例执行，请在下拉框中选择 Midscene 引擎的机器人";
    return;
  }
  running.value = true;
  liveRun.value = null;
  resultRuns.value = [];
  try {
    for (const caseId of selectedIds.value) {
      liveRun.value = null;
      const { data: started } = await client.post(`/api/test-cases/${caseId}/run`, {
        robot_instance_id: selectedRobotInstanceId.value,
        device_platform: normalizeDevicePlatform(selectedDevicePlatform.value),
        device_id: selectedDeviceId.value,
      });
      liveRun.value = { ...started };
      scrollLiveLogToBottom();
      const final = await pollRun(started.id, (data) => {
        liveRun.value = data;
        scrollLiveLogToBottom();
      });
      liveRun.value = final;
      if (["success", "failed", "cancelled"].includes(final.status)) {
        await new Promise((r) => setTimeout(r, 500));
      }
      resultRuns.value.push(final);
    }
  } catch (e) {
    resultRuns.value.push({
      id: 0,
      case_id: 0,
      owner_id: 0,
      status: "failed",
      step_log: null,
      output_message: null,
      error_trace: e.response?.data?.detail || String(e.message || e),
      started_at: null,
      finished_at: null,
    });
  } finally {
    liveRun.value = null;
    running.value = false;
  }
}

onMounted(() => {
  bootstrapProjectContext();
  document.addEventListener("click", onDocumentClick);
});

onUnmounted(() => {
  document.removeEventListener("click", onDocumentClick);
});
</script>

<style scoped>
.br-line {
  margin: 0 0 1rem;
  font-size: 0.88rem;
  line-height: 1.45;
}

.banner.warn {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  background: #fffbeb;
  color: #92400e;
  font-size: 0.9rem;
}

.banner.share-hint {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
  font-size: 0.88rem;
}

.robot-pick {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}

.robot-hint {
  margin: 0.5rem 0 0;
}

.robot-pick-row {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
}

.robot-pick-inner {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 14rem;
  max-width: 32rem;
  flex: 1 1 14rem;
}

.robot-select {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font-size: 0.9rem;
}

.robot-pick-inner--device .picker-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.link-btn {
  border: none;
  background: none;
  color: #2563eb;
  font-size: 0.78rem;
  cursor: pointer;
  padding: 0;
}

.link-btn:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.proj-picker {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.picker-label {
  font-size: 0.8rem;
  color: #64748b;
}

.proj-picker select {
  padding: 0.4rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
  font: inherit;
  max-width: min(420px, 100%);
}

.title {
  margin: 0;
  font-size: 1.35rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.create-case-wrap {
  position: relative;
}

.create-case-trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.create-case-caret {
  font-size: 0.75rem;
  opacity: 0.85;
}

.create-case-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  min-width: 9.5rem;
  padding: 0.35rem 0;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}

.create-case-item {
  display: block;
  width: 100%;
  padding: 0.5rem 0.85rem;
  border: none;
  background: transparent;
  text-align: left;
  font-size: 0.9rem;
  color: #0f172a;
  cursor: pointer;
}

.create-case-item:hover:not(:disabled) {
  background: #f1f5f9;
}

.create-case-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.table-wrap {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  overflow: auto;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

.table th,
.table td {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  vertical-align: top;
}

.table th {
  background: #f8fafc;
  font-weight: 600;
}

.narrow {
  width: 42px;
}

.task {
  max-width: 420px;
  white-space: pre-wrap;
  word-break: break-word;
}

.ops {
  white-space: nowrap;
}

.linkish {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  padding: 0 0.35rem;
}

.linkish.danger {
  color: #b91c1c;
}

.empty {
  text-align: center;
  color: #64748b;
  padding: 2rem !important;
}

.banner {
  padding: 0.65rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.banner.err {
  background: #fef2f2;
  color: #991b1b;
}

.panel {
  margin-top: 1.5rem;
  padding: 1.25rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.panel h2 {
  margin-top: 0;
  font-size: 1.1rem;
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
  border-color: #dc2626;
  color: #b91c1c;
  background: #fff;
}

.btn.stop:hover:not(:disabled) {
  background: #fef2f2;
}

.run-block {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e2e8f0;
}

.run-block:first-of-type {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.run-head {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
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

.out {
  margin: 0;
  padding: 0.75rem;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 8px;
  overflow: auto;
  font-size: 0.85rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.out.err {
  background: #450a0a;
  color: #fecaca;
}

.out.summary {
  margin-top: 0.75rem;
}

.report-download {
  margin-top: 1rem;
  padding: 0.85rem 1rem;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 10px;
}

.report-desc {
  margin: 0 0 0.6rem;
  font-size: 0.9rem;
  color: #0c4a6e;
  line-height: 1.5;
}

.report-link {
  display: inline-flex;
  align-items: center;
  padding: 0;
  border: none;
  background: none;
  color: #2563eb;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.report-link:hover {
  color: #1d4ed8;
}

.report-none {
  margin: 0;
}

.exec-console {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 1rem;
  margin-top: 0.75rem;
  height: 520px;
  min-height: 480px;
}

.exec-console--result {
  margin-top: 0.65rem;
}

.exec-screen-pane {
  min-height: 0;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
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

@media (max-width: 900px) {
  .exec-console {
    grid-template-columns: 1fr;
    height: auto;
    min-height: 0;
  }

  .exec-screen-pane {
    min-height: 280px;
  }

  .exec-log-scroll {
    max-height: 420px;
  }
}

.step-pre.action {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.step-msg {
  margin-top: 0.45rem;
  font-size: 0.85rem;
  color: #166534;
}

.small {
  font-size: 0.8rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 50;
}

.modal {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
}

.modal h3 {
  margin-top: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.field span {
  font-size: 0.85rem;
  color: #475569;
}

input,
textarea {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
}

.muted {
  color: #64748b;
}

.banner.ok {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  background: #ecfdf5;
  color: #065f46;
  font-size: 0.9rem;
}

.modal-wide {
  max-width: 720px;
  max-height: 90vh;
  overflow-y: auto;
}

.format-field {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.65rem 0.75rem;
}

.format-label {
  display: block;
  font-size: 0.82rem;
  color: #64748b;
  margin-bottom: 0.4rem;
}

.format-opt {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  font-size: 0.88rem;
  color: #334155;
  margin-bottom: 0.35rem;
  cursor: pointer;
}

.yaml-editor {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.82rem;
  line-height: 1.45;
  width: 100%;
  box-sizing: border-box;
}

.step-row {
  display: grid;
  grid-template-columns: 28px 1fr 1fr auto;
  gap: 0.35rem;
  align-items: center;
  margin-bottom: 0.35rem;
}

.step-no {
  font-size: 0.8rem;
  color: #64748b;
  text-align: right;
}

.hidden-file {
  display: none;
}

.import-label {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.mini {
  padding: 0.2rem 0.45rem;
  font-size: 0.78rem;
}

.ver-table {
  width: 100%;
  font-size: 0.88rem;
  border-collapse: collapse;
}

.ver-table th,
.ver-table td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.45rem 0.35rem;
  text-align: left;
}
</style>

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
          :disabled="!selectedProjectId || !selectedCaseId || startBusy || !canStartExecution"
          @click="runSelected"
        >
          {{ startBusy ? "提交中…" : "执行测试" }}
        </button>
      </div>
    </div>

    <div v-if="projectsLoaded && !robotInstances.length" class="banner warn">
      执行用例或自动生成用例需先租用机器人实例。请先到
      <router-link to="/marketplace">机器人商城</router-link>
      提交租用申请（执行类选「功能执行」、生成类选「测试分析」），管理员审批通过后到
      <router-link to="/my-robots">我的机器人</router-link>
      查看编号与属性。
    </div>
    <div
      v-else-if="projectsLoaded && robotInstances.length && !executionRobotInstances.length"
      class="banner warn"
    >
      当前仅有测试分析机器人，无法执行用例。请在商城租用<strong>功能执行</strong>或<strong>专项执行</strong>类机器人后再执行测试。
    </div>
    <div v-else-if="projectsLoaded && executionRobotInstances.length" class="robot-pick">
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
              {{ robotOptionHint(ins) }}
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
      <div v-if="busyExecutionRobots.length" class="banner warn small busy-robots-banner">
        <p v-for="ins in busyExecutionRobots" :key="ins.id" class="busy-robot-line">
          <strong>{{ ins.instance_code }}</strong>
          显示为执行中
          <template v-if="ins.active_run_id">（运行 #{{ ins.active_run_id }}）</template>
          。若设备上已无自动化操作，可能是残留任务：
          <button
            v-if="ins.active_run_id"
            type="button"
            class="link-btn"
            :disabled="cancelStaleBusy"
            @click="cancelStaleRun(ins.active_run_id)"
          >
            {{ cancelStaleBusy ? "终止中…" : "终止残留任务" }}
          </button>
        </p>
      </div>
      <p v-if="!runnableRobotCount && !busyExecutionRobots.length" class="robot-hint warn small">
        当前没有可执行用例的机器人：须为<strong>已启动</strong>且<strong>运行状态空闲</strong>。可在
        <router-link v-if="auth.role === 'platform_admin'" to="/admin/robot-instances">机器人实例管理</router-link>
        <template v-else>「我的机器人」</template>
        中启用实例或等待执行结束。
      </p>
      <p v-else-if="!runnableRobotCount && busyExecutionRobots.length" class="robot-hint warn small">
        暂无<strong>空闲</strong>机器人；可先终止上方残留任务，或等待执行结束后再点「执行测试」。
      </p>
      <p v-else class="robot-hint muted small">
        已启动的机器人均可选择并配置设备；<strong>运行空闲</strong>的实例才能点「执行测试」，执行中的实例须先结束或终止残留任务。
      </p>
      <p v-if="activeRunStore.isActive" class="robot-hint muted small">
        已有任务执行中时，可为其它空闲机器人再点「执行测试」；<strong>每个机器人须绑定不同物理终端</strong>，勿共用同一 ADB/HDC 设备。
      </p>
    </div>

    <div v-if="loadError" class="banner err">{{ loadError }}</div>

    <div class="table-wrap">
      <table class="table">
        <thead>
          <tr>
            <th class="col-select">选择</th>
            <th class="col-title">标题</th>
            <th class="col-priority">优先级</th>
            <th class="col-steps">步骤</th>
            <th class="col-desc">执行说明</th>
            <th class="col-ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in cases" :key="c.id">
            <td class="col-select">
              <input
                type="radio"
                name="case-run-select"
                :value="c.id"
                v-model.number="selectedCaseId"
              />
            </td>
            <td class="col-title" :title="c.title">{{ c.title }}</td>
            <td class="col-priority">{{ c.priority || "—" }}</td>
            <td class="col-steps muted small">{{ stepPreview(c) }}</td>
            <td class="col-desc task">{{ truncate(c.task_text, 80) }}</td>
            <td class="col-ops ops">
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

    <p v-if="showResumeHint && liveRunVisible" class="banner share-hint">
      已恢复进行中的执行任务（运行 ID {{ liveRun.id }}）。离开本页后后台仍会继续拉取进度，返回即可继续查看。
    </p>

    <p v-if="parallelRunNotice" class="banner warn small">{{ parallelRunNotice }}</p>

    <div
      v-if="workspaceRunTabs.length > 0"
      class="run-tabs"
      role="tablist"
      aria-label="执行任务"
    >
      <button
        v-for="tab in workspaceRunTabs"
        :key="tab.id"
        type="button"
        role="tab"
        class="run-tab"
        :class="{
          'run-tab--active': isWorkspaceTabActive(tab),
          'run-tab--ended': tab.kind === 'result',
        }"
        :aria-selected="isWorkspaceTabActive(tab)"
        :title="runTabTitle(tab)"
        @click="focusWorkspaceTab(tab)"
      >
        {{ tab.kind === "result" ? runResultTabLabel(tab) : runTabLabel(tab) }}
      </button>
    </div>

    <p v-if="showLivePanel && watchContextLine" class="watch-context muted small">
      <strong>当前观看：</strong>{{ watchContextLine }}
    </p>

    <div v-if="showLivePanel" class="panel live-panel">
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
          <div class="status-meta-line">
            <span class="status-meta-label">执行任务：</span>
            <span class="exec-task-name">{{ liveRunCaseTitle }}</span>
          </div>
          <div class="status-meta-line">
            <span class="status-meta-label">执行状态：</span>
            <span class="badge inline" :class="liveRun.status">{{ statusLabel(liveRun.status) }}</span>
          </div>
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
            :key="mirrorKey"
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

    <div v-if="projectResultRuns.length && workspaceViewingResult" class="panel result-panel">
      <h2>执行结果</h2>
      <p v-if="focusedResultRun" class="watch-context muted small">
        <strong>当前查看：</strong>{{ runTabTitle(focusedResultRun) }}
      </p>
      <div v-if="focusedResultRun" :key="focusedResultRun.id" class="run-block">
        <div class="status-strip status-strip--result">
          <div class="status-strip-main">
            <div class="status-meta-line">
              <span class="status-meta-label">执行任务：</span>
              <span class="exec-task-name">{{ caseTitleForRun(focusedResultRun) }}</span>
            </div>
            <div class="status-meta-line">
              <span class="status-meta-label">执行状态：</span>
              <span class="badge inline" :class="focusedResultRun.status">{{
                statusLabel(focusedResultRun.status)
              }}</span>
            </div>
            <span class="muted small">
              运行 ID {{ focusedResultRun.id }} · 用例 ID {{ focusedResultRun.case_id }}
            </span>
          </div>
        </div>
        <div v-if="focusedResultRun.step_log" class="exec-console exec-console--result">
          <aside class="exec-screen-pane">
            <DeviceScreenMirror
              v-if="focusedResultRun.robot_instance_id"
              :key="`result-${focusedResultRun.id}-${focusedResultRun.robot_instance_id}-${focusedResultRun.device_platform}-${focusedResultRun.device_id}`"
              :robot-instance-id="focusedResultRun.robot_instance_id"
              :device-platform="normalizeDevicePlatform(focusedResultRun.device_platform)"
              :device-id="focusedResultRun.device_id || ''"
              :active="false"
            />
          </aside>
          <div class="exec-log-pane">
            <h3 class="exec-log-title">执行过程</h3>
            <div class="exec-log-scroll">
              <div class="steps">
                <div
                  v-for="(st, idx) in parseStepLog(focusedResultRun.step_log)"
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
        <pre v-if="focusedResultRun.output_message" class="out summary">{{
          focusedResultRun.output_message
        }}</pre>
        <pre v-if="focusedResultRun.error_trace" class="out err">{{ focusedResultRun.error_trace }}</pre>
        <div v-if="focusedResultRun.id" class="report-download">
          <p class="report-desc">
            测试执行已结束。可下载 Midscene 可视化测试报告（HTML），查看步骤截图与详细执行过程。
          </p>
          <button
            v-if="focusedResultRun.has_report"
            type="button"
            class="report-link"
            @click="downloadReport(focusedResultRun.id)"
          >
            下载测试报告
          </button>
          <p v-else class="muted small report-none">
            本次执行未生成可下载报告（非 Midscene 引擎、执行过短未落盘，或报告文件已被清理）。
          </p>
        </div>
      </div>
    </div>

    <p v-if="importMsg" class="banner ok">{{ importMsg }}</p>

    <div v-if="genDialog.open" class="modal-overlay" @click.self="closeGenerate">
      <div class="modal">
        <h3>自动生成用例</h3>
        <p class="muted small">
          须选择已租用的<strong>测试分析</strong>机器人实例；用一句话描述要测什么，由分析机器人生成草稿。保存前可在编辑页核对或切换格式。
        </p>
        <div v-if="!analysisRobotInstances.length" class="banner warn small">
          尚无测试分析机器人实例。请到
          <router-link to="/marketplace">机器人商城</router-link>
          租用「测试分析数字机器人」，审批通过后再试。
        </div>
        <label v-else class="field">
          <span>测试分析机器人实例</span>
          <select
            v-model.number="selectedAnalysisRobotInstanceId"
            class="robot-select"
            :disabled="genDialog.loading"
          >
            <option
              v-for="ins in analysisRobotInstances"
              :key="ins.id"
              :value="ins.id"
              :disabled="analysisOptionDisabled(ins)"
            >
              {{ ins.instance_code }} · {{ (ins.display_name || "").trim() || ins.catalog_robot_id }}
              {{ analysisOptionHint(ins) }}
            </option>
          </select>
        </label>
        <p v-if="analysisRobotInstances.length && !runnableAnalysisCount" class="robot-hint warn small">
          当前没有可用的测试分析机器人：须<strong>已启动</strong>且<strong>运行空闲</strong>。可在
          <router-link v-if="auth.role === 'platform_admin'" to="/admin/robot-instances">机器人实例管理</router-link>
          <template v-else>「我的机器人」</template>
          中启用或等待生成结束。
        </p>
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
          <button
            type="button"
            class="btn primary"
            :disabled="genDialog.loading || !canSubmitGenerate"
            @click="submitGenerate"
          >
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
        <p v-if="dialog.error" class="err">{{ dialog.error }}</p>
        <div class="modal-actions">
          <button type="button" class="btn ghost" :disabled="dialog.saving" @click="dialog.open = false">
            取消
          </button>
          <button type="button" class="btn primary" :disabled="dialog.saving" @click="saveDialog(false)">
            {{ dialog.saving ? "保存中…" : "保存" }}
          </button>
          <button
            type="button"
            class="btn primary btn-run"
            :disabled="dialog.saving || startBusy"
            @click="saveDialog(true)"
          >
            {{ dialog.saving ? "处理中…" : "保存并执行" }}
          </button>
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
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useRoute, useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";
import DeviceScreenMirror from "@/components/DeviceScreenMirror.vue";
import {
  useActiveTestRunStore,
  getActiveRunProjectId,
  isLiveRunStatus,
} from "@/stores/activeTestRun";
import { useAuthStore } from "@/stores/auth";
import {
  analysisRobotUnselectableHint,
  isAnalysisInstance,
  isExecutionInstance,
  isRobotRunnableForAnalysis,
  isInstanceStarted,
  isRobotRunnableForCase,
  robotUnselectableHint,
} from "@/constants/robotCatalog";

/** 轮询时短暂断网、502 等不应立刻当作「执行失败」；401 等仍应立即失败 */
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const activeRunStore = useActiveTestRunStore();
const { liveRun, focusedRunId } = storeToRefs(activeRunStore);

const projects = ref([]);
const projectsLoaded = ref(false);
const selectedProjectId = ref(null);

const cases = ref([]);
const loading = ref(false);
const loadError = ref("");
const selectedCaseId = ref(null);
const stopBusy = ref(false);
const startBusy = ref(false);
const cancelStaleBusy = ref(false);
const showResumeHint = ref(false);
const resultRuns = ref([]);
const focusedResultRunId = ref(null);
const absorbedRunIds = ref(new Set());
const parallelRunNotice = ref("");

function runBelongsToCurrentProject(run) {
  if (!selectedProjectId.value || !run) return false;
  const pid =
    run.project_id != null
      ? Number(run.project_id)
      : activeRunStore.projectId != null
        ? Number(activeRunStore.projectId)
        : Number(getActiveRunProjectId()) || NaN;
  if (Number.isFinite(pid) && pid === selectedProjectId.value) return true;
  return cases.value.some((c) => c.id === run.case_id);
}

const liveRunVisible = computed(() => {
  if (!liveRun.value) return false;
  if (!runBelongsToCurrentProject(liveRun.value)) return false;
  return isLiveRunStatus(liveRun.value.status);
});

const projectExecutingRuns = computed(() =>
  activeRunStore.executingRuns.filter((r) => runBelongsToCurrentProject(r)),
);

const projectResultRuns = computed(() =>
  resultRuns.value
    .filter((r) => runBelongsToCurrentProject(r))
    .sort((a, b) => b.id - a.id),
);

const focusedResultRun = computed(() => {
  const runs = projectResultRuns.value;
  if (!runs.length) return null;
  const id = focusedResultRunId.value;
  return runs.find((r) => r.id === id) || runs[0];
});

/** 工作台面板：实时进度 vs 已结束结果 */
const workspacePanel = ref("live");

const workspaceRunTabs = computed(() => {
  const byId = new Map();
  for (const r of projectExecutingRuns.value) {
    byId.set(r.id, { ...r, kind: "live" });
  }
  for (const r of projectResultRuns.value) {
    if (!byId.has(r.id)) {
      byId.set(r.id, { ...r, kind: "result" });
    }
  }
  return [...byId.values()].sort((a, b) => b.id - a.id);
});

const workspaceViewingResult = computed(() => workspacePanel.value === "result");

const showLivePanel = computed(
  () => liveRunVisible.value && workspacePanel.value === "live",
);

const mirrorInstanceId = computed(() => {
  const id = liveRun.value?.robot_instance_id;
  return id != null ? Number(id) : null;
});

const mirrorPlatform = computed(() =>
  normalizeDevicePlatform(liveRun.value?.device_platform || "android"),
);

const mirrorDeviceId = computed(() => liveRun.value?.device_id || "");

const mirrorKey = computed(() => {
  const r = liveRun.value;
  if (!r?.id) return "mirror-none";
  return `live-${r.id}-${mirrorInstanceId.value}-${mirrorPlatform.value}-${mirrorDeviceId.value}`;
});

const liveRunCaseTitle = computed(() => (liveRun.value ? caseTitleForRun(liveRun.value) : ""));

const watchContextLine = computed(() => {
  const r = liveRun.value;
  if (!r?.robot_instance_id) return "";
  const ins = robotInstances.value.find((i) => i.id === r.robot_instance_id);
  const code = ins?.instance_code || `机器人#${r.robot_instance_id}`;
  const engine = agentEngineLabel(ins?.test_agent_backend);
  const plat = devicePlatformLabel(r.device_platform);
  const dev = r.device_id ? ` · ${r.device_id}` : "";
  return `${code} · ${engine} · ${plat}${dev} · 运行 #${r.id}`;
});

const robotInstances = ref([]);
const selectedRobotInstanceId = ref(null);
const selectedAnalysisRobotInstanceId = ref(null);
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

const selectedRobotInstance = computed(() =>
  robotInstances.value.find((i) => i.id === selectedRobotInstanceId.value),
);

const runnableRobotCount = computed(() =>
  executionRobotInstances.value.filter((ins) =>
    isRobotRunnableForCase(ins),
  ).length,
);

/** 后端标记为执行中（可能为残留任务，设备实际已空闲） */
const busyExecutionRobots = computed(() =>
  executionRobotInstances.value.filter((ins) => {
    if (!isInstanceStarted(ins.status)) return false;
    return String(ins.runtime_status || "").toLowerCase() === "executing";
  }),
);

const canStartExecution = computed(() => {
  if (!selectedRobotInstanceId.value) return false;
  if (!isRobotRunnableForCase(selectedRobotInstance.value)) {
    return false;
  }
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
    if (liveRunVisible.value) scrollLiveLogToBottom();
  },
);

function isTerminalRunStatus(status) {
  return status === "success" || status === "failed" || status === "cancelled";
}

function absorbTerminalRun(run) {
  if (!run || absorbedRunIds.value.has(run.id)) return;
  if (!runBelongsToCurrentProject(run)) {
    activeRunStore.removeRun(run.id);
    return;
  }
  if (!isTerminalRunStatus(run.status)) return;
  absorbedRunIds.value = new Set([...absorbedRunIds.value, run.id]);

  const ins = robotInstances.value.find((i) => i.id === run.robot_instance_id);
  const code = ins?.instance_code || `机器人#${run.robot_instance_id}`;
  const wasFocused = focusedRunId.value === run.id;

  const others = resultRuns.value.filter((r) => r.id !== run.id);
  resultRuns.value = [run, ...others].slice(0, 5);
  if (wasFocused || focusedResultRunId.value == null) {
    focusedResultRunId.value = run.id;
  }

  if (!wasFocused) {
    parallelRunNotice.value = `并行任务已结束：${code} · 运行 #${run.id}（${statusLabel(run.status)}）。可在下方「执行结果」查看详情。`;
  } else {
    parallelRunNotice.value = "";
    showResumeHint.value = false;
    syncRunQuery(null);
  }

  activeRunStore.removeRun(run.id);
  const next = projectExecutingRuns.value[0];
  if (next && wasFocused) {
    workspacePanel.value = "live";
    focusRunTab(next.id);
  } else if (wasFocused) {
    workspacePanel.value = "result";
    focusedResultRunId.value = run.id;
  }
}

watch(
  () => activeRunStore.runsById,
  (map) => {
    for (const run of Object.values(map || {})) {
      if (isTerminalRunStatus(run.status)) {
        absorbTerminalRun(run);
      }
    }
  },
  { deep: true },
);

function caseTitleForRun(run) {
  const c = cases.value.find((x) => x.id === run.case_id);
  return (c?.title || "").trim() || `用例 #${run.case_id}`;
}

function runTabTitle(run) {
  const ins = robotInstances.value.find((i) => i.id === run.robot_instance_id);
  const code = ins?.instance_code || `#${run.robot_instance_id}`;
  return `${code} · ${caseTitleForRun(run)} · 运行 #${run.id}`;
}

function runTabLabel(run) {
  const ins = robotInstances.value.find((i) => i.id === run.robot_instance_id);
  const code = ins?.instance_code || `#${run.robot_instance_id}`;
  return `${code} · ${truncate(caseTitleForRun(run), 22)}`;
}

function focusRunTab(runId) {
  activeRunStore.focusRun(runId);
  syncRunQuery(runId);
  scrollLiveLogToBottom();
  parallelRunNotice.value = "";
}

function focusResultRunTab(runId) {
  focusedResultRunId.value = runId;
  parallelRunNotice.value = "";
}

function isWorkspaceTabActive(tab) {
  if (tab.kind === "live") {
    return workspacePanel.value === "live" && focusedRunId.value === tab.id;
  }
  return workspacePanel.value === "result" && focusedResultRunId.value === tab.id;
}

function focusWorkspaceTab(tab) {
  if (tab.kind === "live") {
    workspacePanel.value = "live";
    focusRunTab(tab.id);
  } else {
    workspacePanel.value = "result";
    focusResultRunTab(tab.id);
  }
}

function runResultTabLabel(run) {
  const base = runTabLabel(run);
  const st = statusLabel(run.status);
  return `${base} · ${st}`;
}

watch(
  projectResultRuns,
  (runs) => {
    if (!runs.length) {
      focusedResultRunId.value = null;
      return;
    }
    if (!runs.some((r) => r.id === focusedResultRunId.value)) {
      focusedResultRunId.value = runs[0].id;
    }
  },
  { immediate: true },
);

watch(projectExecutingRuns, (executing) => {
  if (!executing.length && projectResultRuns.value.length) {
    workspacePanel.value = "result";
    if (!projectResultRuns.value.some((r) => r.id === focusedResultRunId.value)) {
      focusedResultRunId.value = projectResultRuns.value[0].id;
    }
  }
});

const importMsg = ref("");

const dialog = reactive({
  open: false,
  editing: false,
  id: null,
  title: "",
  task_text: "",
  preconditions: "",
  priority: "P2",
  steps: [],
  error: "",
  saving: false,
});

const genDialog = reactive({
  open: false,
  prompt: "",
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

const analysisRobotInstances = computed(() =>
  robotInstances.value.filter((ins) => isAnalysisInstance(ins)),
);

const executionRobotInstances = computed(() =>
  robotInstances.value.filter((ins) => isExecutionInstance(ins)),
);

const robotsForExecution = computed(() => executionRobotInstances.value);

const runnableAnalysisCount = computed(() =>
  analysisRobotInstances.value.filter((ins) => isRobotRunnableForAnalysis(ins)).length,
);

const canSubmitGenerate = computed(() => {
  if (!analysisRobotInstances.value.length) return false;
  if (!selectedAnalysisRobotInstanceId.value) return false;
  const ins = analysisRobotInstances.value.find((i) => i.id === selectedAnalysisRobotInstanceId.value);
  return isRobotRunnableForAnalysis(ins);
});

function analysisOptionDisabled(ins) {
  return !isRobotRunnableForAnalysis(ins);
}

function analysisOptionHint(ins) {
  return analysisRobotUnselectableHint(ins);
}

function robotOptionDisabled(ins) {
  if (!ins || !isInstanceStarted(ins.status)) return true;
  return false;
}

function robotOptionHint(ins) {
  return robotUnselectableHint(ins);
}

function syncAnalysisRobotSelection() {
  const runnable = analysisRobotInstances.value.filter((ins) => isRobotRunnableForAnalysis(ins));
  if (!runnable.length) {
    selectedAnalysisRobotInstanceId.value = null;
    return;
  }
  const current = analysisRobotInstances.value.find(
    (ins) => ins.id === selectedAnalysisRobotInstanceId.value,
  );
  if (!current || !isRobotRunnableForAnalysis(current)) {
    selectedAnalysisRobotInstanceId.value = runnable[0].id;
  }
}

/** 新建执行配置：保留用户已选的已启动实例（含「执行中」），仅在不合法时改选空闲机器人 */
function syncDraftRobotSelection() {
  const runnable = executionRobotInstances.value.filter((ins) =>
    isRobotRunnableForCase(ins),
  );
  const current = executionRobotInstances.value.find((ins) => ins.id === selectedRobotInstanceId.value);
  const currentDraftOk =
    current &&
    isInstanceStarted(current.status);

  if (currentDraftOk) {
    syncAnalysisRobotSelection();
    return;
  }

  if (!runnable.length) {
    selectedRobotInstanceId.value = null;
    syncAnalysisRobotSelection();
    return;
  }

  selectedRobotInstanceId.value = runnable[0].id;
  syncDevicePlatformFromInstance();
  loadConnectedDevices();
  syncAnalysisRobotSelection();
}

watch([selectedCaseId, cases], () => syncDraftRobotSelection());

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
    if (selectedCaseId.value && !data.some((c) => c.id === selectedCaseId.value)) {
      selectedCaseId.value = null;
    }
  } catch (e) {
    loadError.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function onProjectChange() {
  showResumeHint.value = false;
  const q = { project: String(selectedProjectId.value) };
  router.replace({ path: "/cases", query: q });
  await load();
  await loadRobotInstances();
  await tryResumeActiveRun();
}

async function loadRobotInstances() {
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    robotInstances.value = Array.isArray(data) ? data : [];
    syncDraftRobotSelection();
    await activeRunStore.syncRunsFromRobots(robotInstances.value, selectedProjectId.value);
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
  await tryResumeActiveRun();
}

function truncate(s, n) {
  if (!s) return "—";
  return s.length <= n ? s : `${s.slice(0, n)}…`;
}

function stepPreview(c) {
  const n = Array.isArray(c.steps) ? c.steps.length : 0;
  return n ? `${n} 步` : "—";
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
  dialog.steps = [{ description: "", expected: "" }];
  dialog.error = "";
  dialog.saving = false;
}

function openGenerate() {
  if (!selectedProjectId.value) return;
  syncAnalysisRobotSelection();
  genDialog.open = true;
  genDialog.prompt = "";
  genDialog.loading = false;
  genDialog.error = "";
}

function closeGenerate() {
  if (genDialog.loading) return;
  genDialog.open = false;
  genDialog.error = "";
}

function applyDraftToDialog(draft) {
  dialog.title = draft.title || "";
  dialog.task_text = draft.task_text || "";
  dialog.preconditions = draft.preconditions || "";
  dialog.priority = draft.priority || "P2";
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
  dialog.saving = false;
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
  if (!selectedAnalysisRobotInstanceId.value) {
    genDialog.error = "请选择测试分析机器人实例";
    return;
  }
  if (!canSubmitGenerate.value) {
    genDialog.error = "当前测试分析机器人不可用，请选用已启动且空闲的实例";
    return;
  }
  genDialog.loading = true;
  try {
    const { data } = await client.post("/api/test-cases/generate", {
      project_id: selectedProjectId.value,
      robot_instance_id: selectedAnalysisRobotInstanceId.value,
      prompt,
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
  const st = Array.isArray(c.steps) && c.steps.length ? c.steps : [];
  dialog.steps = st.length
    ? st.map((x) => ({
        description: x.description || "",
        expected: x.expected || "",
      }))
    : [{ description: "", expected: "" }];
  dialog.error = "";
  dialog.saving = false;
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

function validateDialogForm() {
  if (!dialog.title.trim()) return "请填写标题";
  const stepsPayload = buildStepsPayload();
  if (!dialog.task_text.trim() && stepsPayload.length === 0) {
    return "请填写执行说明或至少一条步骤";
  }
  return null;
}

function validateExecutionReady() {
  if (!selectedRobotInstanceId.value) {
    return "请先选择要使用的机器人实例";
  }
  const picked = robotInstances.value.find((ins) => ins.id === selectedRobotInstanceId.value);
  if (!picked || !isInstanceStarted(picked.status)) {
    return "请选择已启动的机器人实例";
  }
  const rt = String(picked.runtime_status || "").toLowerCase();
  if (rt === "executing") {
    const rid = picked.active_run_id;
    return (
      `机器人 ${picked.instance_code} 显示执行中${rid ? `（运行 #${rid}）` : ""}。` +
      "若设备实际空闲，请点击上方「终止残留任务」，或在下方执行 Tab 中停止该任务。"
    );
  }
  if (!selectedDeviceId.value) {
    return devicesError.value || "请先选择已连接的目标终端，或点击「刷新」重新扫描设备";
  }
  const platform = normalizeDevicePlatform(selectedDevicePlatform.value);
  const conflict = activeRunStore.findLiveRunOnDevice(platform, selectedDeviceId.value);
  if (conflict) {
    const ins = robotInstances.value.find((i) => i.id === conflict.robot_instance_id);
    const code = ins?.instance_code || `#${conflict.robot_instance_id}`;
    const devLabel = selectedDeviceId.value || "（默认设备）";
    return (
      `目标终端 ${devLabel} 已被进行中的任务占用（${code} · 运行 #${conflict.id}）。` +
      "并行执行须为每个机器人选择不同的物理设备，或等待当前任务结束。"
    );
  }
  return null;
}

function buildSaveBody() {
  return {
    title: dialog.title.trim(),
    task_text: dialog.task_text.trim(),
    preconditions: (dialog.preconditions || "").trim(),
    priority: dialog.priority,
    steps: buildStepsPayload(),
  };
}

async function persistCase() {
  const body = buildSaveBody();
  if (dialog.editing && dialog.id) {
    const { data } = await client.patch(`/api/test-cases/${dialog.id}`, body);
    return data;
  }
  const { data } = await client.post("/api/test-cases", {
    project_id: selectedProjectId.value,
    ...body,
  });
  return data;
}

async function saveDialog(andRun = false) {
  dialog.error = "";
  const formErr = validateDialogForm();
  if (formErr) {
    dialog.error = formErr;
    return;
  }
  if (andRun) {
    const runErr = validateExecutionReady();
    if (runErr) {
      dialog.error = runErr;
      return;
    }
  }
  dialog.saving = true;
  try {
    const saved = await persistCase();
    dialog.open = false;
    await load();
    if (saved?.id) {
      selectedCaseId.value = saved.id;
    }
    if (andRun && saved?.id) {
      loadError.value = "";
      await runCaseById(saved.id);
    }
  } catch (e) {
    dialog.error = formatApiError(e);
  } finally {
    dialog.saving = false;
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
  try {
    await client.delete(`/api/test-cases/${c.id}`);
    if (selectedCaseId.value === c.id) {
      selectedCaseId.value = null;
    }
    const related = Object.values(activeRunStore.runsById).filter((r) => r.case_id === c.id);
    for (const r of related) {
      activeRunStore.removeRun(r.id);
    }
    await load();
  } catch (e) {
    window.alert(formatApiError(e));
  }
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
    await activeRunStore.cancelRunById(id);
    try {
      const { data } = await client.get(`/api/test-cases/runs/${id}`);
      absorbTerminalRun(data);
    } catch {
      /* 轮询或 watcher 可能稍后 absorb */
    }
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

function syncRunQuery(runId) {
  const q = { ...route.query };
  if (runId) {
    q.run = String(runId);
  } else {
    delete q.run;
  }
  router.replace({ path: route.path, query: q });
}

async function tryResumeActiveRun() {
  const qRun = route.query.run ? Number(route.query.run) : null;
  const preferred = Number.isFinite(qRun) && qRun > 0 ? qRun : null;
  const hadStored = !!(preferred || sessionStorage.getItem("tcm_active_run_id"));
  await activeRunStore.syncRunsFromRobots(robotInstances.value, selectedProjectId.value);
  const data = preferred
    ? await activeRunStore.resumeIfNeeded(preferred)
    : await activeRunStore.resumeIfNeeded();
  if (!data) return;
  if (!runBelongsToCurrentProject(data)) {
    showResumeHint.value = false;
    if (route.query.run) syncRunQuery(null);
    return;
  }
  selectedCaseId.value = data.case_id;
  if (isTerminalRunStatus(data.status)) {
    resultRuns.value = [data];
    activeRunStore.removeRun(data.id);
    return;
  }
  if (hadStored && isLiveRunStatus(data.status)) {
    showResumeHint.value = true;
    if (preferred !== data.id) {
      activeRunStore.focusRun(data.id);
    }
    syncRunQuery(data.id);
  }
  await nextTick();
  scrollLiveLogToBottom();
}

async function cancelStaleRun(runId) {
  if (!runId) return;
  cancelStaleBusy.value = true;
  try {
    await activeRunStore.cancelRunById(runId);
    parallelRunNotice.value = "";
    await loadRobotInstances();
  } catch (e) {
    window.alert(e.response?.data?.detail || String(e.message || e));
  } finally {
    cancelStaleBusy.value = false;
  }
}

async function runCaseById(caseId) {
  if (!activeRunStore.isActive) {
    resultRuns.value = [];
    absorbedRunIds.value = new Set();
    parallelRunNotice.value = "";
  }
  loadError.value = "";
  showResumeHint.value = false;
  activeRunStore.pollError = null;
  startBusy.value = true;
  try {
    const started = await activeRunStore.executeCase({
      caseId,
      projectId: selectedProjectId.value,
      robotInstanceId: selectedRobotInstanceId.value,
      devicePlatform: normalizeDevicePlatform(selectedDevicePlatform.value),
      deviceId: selectedDeviceId.value,
    });
    workspacePanel.value = "live";
    selectedCaseId.value = caseId;
    await loadRobotInstances();
    syncRunQuery(started.id);
    await nextTick();
    scrollLiveLogToBottom();
  } catch (e) {
    const msg =
      activeRunStore.pollError ||
      e.response?.data?.detail ||
      String(e.message || e);
    loadError.value = typeof msg === "string" ? msg : formatApiError(e);
    resultRuns.value.push({
      id: activeRunStore.runId || 0,
      case_id: caseId,
      owner_id: 0,
      status: "failed",
      step_log: activeRunStore.liveRun?.step_log || null,
      output_message: null,
      error_trace: loadError.value,
      started_at: null,
      finished_at: null,
    });
  } finally {
    startBusy.value = false;
  }
}

async function runSelected() {
  const caseId = selectedCaseId.value;
  if (!caseId) return;
  const pickedCase = cases.value.find((c) => c.id === caseId);
  const runErr = validateExecutionReady();
  if (runErr) {
    loadError.value = runErr;
    return;
  }
  loadError.value = "";
  await runCaseById(caseId);
}

let robotRefreshTimer = null;

onMounted(() => {
  bootstrapProjectContext();
  document.addEventListener("click", onDocumentClick);
  robotRefreshTimer = setInterval(() => loadRobotInstances(), 5000);
});

onUnmounted(() => {
  document.removeEventListener("click", onDocumentClick);
  if (robotRefreshTimer) clearInterval(robotRefreshTimer);
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

.robot-hint.warn {
  color: #92400e;
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
  min-width: 52rem;
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
  white-space: nowrap;
}

.col-select {
  width: 3.25rem;
  min-width: 3.25rem;
  text-align: center;
  white-space: nowrap;
}

.col-select input {
  vertical-align: middle;
}

.col-title {
  min-width: 12rem;
  max-width: 22rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.col-priority {
  width: 4.5rem;
  min-width: 4.5rem;
  white-space: nowrap;
}

.col-format {
  width: 4.5rem;
  min-width: 4.5rem;
  white-space: nowrap;
}

.col-steps {
  width: 4rem;
  min-width: 4rem;
  white-space: nowrap;
}

.col-desc {
  min-width: 10rem;
}

.col-ops {
  width: 1%;
  min-width: 9rem;
  white-space: nowrap;
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

.status-meta-line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.35rem 0.5rem;
  margin: 0 0 0.4rem;
  font-size: 0.88rem;
  line-height: 1.5;
  color: #0f172a;
}

.status-meta-label {
  flex-shrink: 0;
  font-size: inherit;
  font-weight: 600;
  color: #334155;
}

.status-meta-line .exec-task-name {
  font-weight: 500;
  min-width: 0;
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

.status-strip--result {
  margin-bottom: 0.75rem;
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

.run-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin: 0.75rem 0 0.35rem;
}

.run-tabs--result {
  margin-top: 0.5rem;
}

.run-tab {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  border-radius: 999px;
  padding: 0.35rem 0.85rem;
  font-size: 0.82rem;
  max-width: min(100%, 320px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s,
    color 0.15s;
}

.run-tab:hover {
  border-color: #93c5fd;
  color: #1d4ed8;
}

.run-tab--active {
  border-color: #2563eb;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 600;
}

.run-tab--ended:not(.run-tab--active) {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #64748b;
}

.watch-context {
  margin: 0.35rem 0 0.65rem;
  padding: 0.5rem 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.busy-robots-banner {
  margin-top: 0.5rem;
}

.busy-robot-line {
  margin: 0.25rem 0;
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

.exec-console--result {
  margin-top: 0.65rem;
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
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.btn-run {
  background: #0d9488;
  border-color: #0d9488;
}

.btn-run:hover:not(:disabled) {
  background: #0f766e;
  border-color: #0f766e;
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

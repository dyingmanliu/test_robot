<template>
  <div class="wizard-page">
    <header class="page-head">
      <h1>功能测试任务下发</h1>
      <p class="hint">
        项目空间内依次完成：<strong>安装包</strong> → <strong>用例集</strong>（可自建或由 AI 占位草稿）→ <strong>设备池</strong> →
        <strong>下发</strong>。下发后调度层将任务写入 Kafka，供 Agent 管理服务分配给「功能测试执行数字机器人」。
      </p>
    </header>

    <nav class="steps">
      <span :class="{ on: step >= 1 }">1 安装包</span>
      <span class="sep">→</span>
      <span :class="{ on: step >= 2 }">2 用例集</span>
      <span class="sep">→</span>
      <span :class="{ on: step >= 3 }">3 设备池</span>
      <span class="sep">→</span>
      <span :class="{ on: step >= 4 }">4 下发</span>
    </nav>

    <p v-if="pageErr" class="banner err">{{ pageErr }}</p>

    <!-- Step 1 -->
    <section v-show="step === 1" class="panel card">
      <h2>上传或选择 App 安装包</h2>
      <label class="field">
        <span>上传 APK / AAB</span>
        <input type="file" accept=".apk,.aab,.zip" @change="onPickFile" />
      </label>
      <p v-if="uploadErr" class="err">{{ uploadErr }}</p>
      <button type="button" class="btn" :disabled="uploading" @click="doUpload">
        {{ uploading ? "上传中…" : "上传安装包" }}
      </button>

      <div v-if="artifacts.length" class="list-block">
        <h3>已上传的包（勾选其一）</h3>
        <label v-for="a in artifacts" :key="a.id" class="radio-row">
          <input v-model="artifactId" type="radio" :value="a.id" />
          <span>{{ a.filename }} · {{ fmtSize(a.size_bytes) }} · {{ fmtDate(a.created_at) }}</span>
        </label>
      </div>
      <p v-else class="muted">暂无安装包，请先上传。</p>

      <div class="nav-actions">
        <router-link class="btn ghost" :to="{ name: 'projects' }">返回项目空间</router-link>
        <button type="button" class="btn primary" :disabled="!artifactId" @click="step = 2">下一步</button>
      </div>
    </section>

    <!-- Step 2 -->
    <section v-show="step === 2" class="panel card">
      <h2>测试用例集</h2>
      <p class="muted small">可从当前项目用例中勾选并新建集合，或使用占位 AI 草稿填充名称后再勾选创建。</p>

      <div class="row-actions">
        <button type="button" class="btn" :disabled="draftLoading" @click="loadAiDraft">
          {{ draftLoading ? "请求中…" : "AI 生成草稿（占位）" }}
        </button>
      </div>
      <p v-if="draftHint" class="hint-ai">{{ draftHint }}</p>

      <label class="field">
        <span>新建用例集名称</span>
        <input v-model="newSetName" maxlength="256" placeholder="例如：登录回归 · P1" />
      </label>

      <div v-if="cases.length" class="cases-box">
        <h3>勾选纳入集合的用例</h3>
        <label v-for="c in cases" :key="c.id" class="check-row">
          <input v-model="pickedCaseIds" type="checkbox" :value="c.id" />
          <span>{{ c.title }}</span>
        </label>
      </div>
      <p v-else class="muted">该项目暂无自动化用例，请先到「测试用例」页创建。</p>

      <button type="button" class="btn primary" :disabled="creatingSet || pickedCaseIds.length === 0" @click="createSet">
        {{ creatingSet ? "创建中…" : "保存为用例集" }}
      </button>
      <p v-if="setErr" class="err">{{ setErr }}</p>

      <div v-if="caseSets.length" class="list-block">
        <h3>已有用例集（也可直接选用）</h3>
        <label v-for="s in caseSets" :key="s.id" class="radio-row">
          <input v-model="caseSetId" type="radio" :value="s.id" />
          <span>{{ s.name }}（{{ s.case_ids.length }} 条）</span>
        </label>
      </div>

      <div class="nav-actions">
        <button type="button" class="btn ghost" @click="step = 1">上一步</button>
        <button type="button" class="btn primary" :disabled="!caseSetId" @click="step = 3">下一步</button>
      </div>
    </section>

    <!-- Step 3 -->
    <section v-show="step === 3" class="panel card">
      <h2>测试设备池</h2>
      <div v-if="pools.length">
        <label v-for="p in pools" :key="p.id" class="radio-row">
          <input v-model="devicePoolId" type="radio" :value="p.id" />
          <span><strong>{{ p.name }}</strong> · {{ p.region }} — {{ p.description }}</span>
        </label>
      </div>
      <p v-else class="muted">加载设备池…</p>

      <div class="nav-actions">
        <button type="button" class="btn ghost" @click="step = 2">上一步</button>
        <button type="button" class="btn primary" :disabled="!devicePoolId" @click="step = 4">下一步</button>
      </div>
    </section>

    <!-- Step 4 -->
    <section v-show="step === 4" class="panel card">
      <h2>确认并下发</h2>
      <ul class="sum">
        <li><strong>安装包</strong>：{{ artifactLabel }}</li>
        <li><strong>用例集</strong>：{{ caseSetLabel }}</li>
        <li><strong>设备池</strong>：{{ devicePoolLabel }}</li>
      </ul>
      <button type="button" class="btn primary" :disabled="dispatching" @click="dispatch">
        {{ dispatching ? "下发中…" : "下发任务" }}
      </button>
      <p v-if="dispatchMsg" class="ok-msg">{{ dispatchMsg }}</p>
      <p v-if="dispatchErr" class="err">{{ dispatchErr }}</p>

      <div v-if="history.length" class="hist">
        <h3>最近下发记录</h3>
        <table class="tbl">
          <thead>
            <tr>
              <th>ID</th>
              <th>状态</th>
              <th>设备池</th>
              <th>时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.id">
              <td>{{ h.id }}</td>
              <td>{{ h.status }}</td>
              <td>{{ h.device_pool_id }}</td>
              <td>{{ fmtDate(h.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="nav-actions">
        <button type="button" class="btn ghost" @click="step = 3">上一步</button>
        <router-link class="btn" :to="{ name: 'projects' }">返回项目空间</router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";

const route = useRoute();
const projectId = computed(() => Number(route.params.projectId));

const step = ref(1);
const pageErr = ref("");
const artifacts = ref([]);
const artifactId = ref(null);
const fileToUpload = ref(null);
const uploading = ref(false);
const uploadErr = ref("");

const cases = ref([]);
const caseSets = ref([]);
const newSetName = ref("");
const pickedCaseIds = ref([]);
const caseSetId = ref(null);
const creatingSet = ref(false);
const setErr = ref("");
const draftLoading = ref(false);
const draftHint = ref("");

const pools = ref([]);
const devicePoolId = ref("");

const dispatching = ref(false);
const dispatchMsg = ref("");
const dispatchErr = ref("");
const history = ref([]);

function fmtSize(n) {
  if (!n && n !== 0) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

const artifactLabel = computed(() => {
  const a = artifacts.value.find((x) => x.id === artifactId.value);
  return a ? a.filename : "—";
});

const caseSetLabel = computed(() => {
  const s = caseSets.value.find((x) => x.id === caseSetId.value);
  return s ? `${s.name}（${s.case_ids.length} 条）` : "—";
});

const devicePoolLabel = computed(() => {
  const p = pools.value.find((x) => x.id === devicePoolId.value);
  return p ? p.name : "—";
});

async function loadArtifacts() {
  const { data } = await client.get(`/api/projects/${projectId.value}/app-packages`);
  artifacts.value = data;
}

async function loadCasesAndSets() {
  const [tc, ts] = await Promise.all([
    client.get("/api/test-cases", { params: { project_id: projectId.value } }),
    client.get(`/api/projects/${projectId.value}/case-sets`),
  ]);
  cases.value = tc.data;
  caseSets.value = ts.data;
}

async function loadPools() {
  const { data } = await client.get("/api/device-pools");
  pools.value = data.pools || [];
}

async function loadHistory() {
  try {
    const { data } = await client.get(`/api/projects/${projectId.value}/functional-dispatches`);
    history.value = data;
  } catch {
    history.value = [];
  }
}

function onPickFile(ev) {
  const f = ev.target.files?.[0];
  fileToUpload.value = f || null;
  uploadErr.value = "";
}

async function doUpload() {
  if (!fileToUpload.value) {
    uploadErr.value = "请选择文件";
    return;
  }
  uploading.value = true;
  uploadErr.value = "";
  try {
    const fd = new FormData();
    fd.append("file", fileToUpload.value);
    await client.post(`/api/projects/${projectId.value}/app-packages`, fd);
    fileToUpload.value = null;
    await loadArtifacts();
  } catch (e) {
    uploadErr.value = formatApiError(e);
  } finally {
    uploading.value = false;
  }
}

async function loadAiDraft() {
  draftLoading.value = true;
  draftHint.value = "";
  try {
    const { data } = await client.post(`/api/projects/${projectId.value}/case-sets/ai-draft`);
    newSetName.value = data.suggested_name || "";
    draftHint.value = data.message || "";
  } catch (e) {
    draftHint.value = formatApiError(e);
  } finally {
    draftLoading.value = false;
  }
}

async function createSet() {
  if (!newSetName.value.trim()) {
    setErr.value = "请填写用例集名称";
    return;
  }
  if (!pickedCaseIds.value.length) {
    setErr.value = "请至少勾选一条用例";
    return;
  }
  creatingSet.value = true;
  setErr.value = "";
  try {
    const { data } = await client.post(`/api/projects/${projectId.value}/case-sets`, {
      name: newSetName.value.trim(),
      description: "",
      case_ids: [...pickedCaseIds.value],
    });
    await loadCasesAndSets();
    caseSetId.value = data.id;
  } catch (e) {
    setErr.value = formatApiError(e);
  } finally {
    creatingSet.value = false;
  }
}

async function dispatch() {
  dispatching.value = true;
  dispatchMsg.value = "";
  dispatchErr.value = "";
  try {
    const { data } = await client.post(`/api/projects/${projectId.value}/functional-dispatches`, {
      app_artifact_id: artifactId.value,
      case_set_id: caseSetId.value,
      device_pool_id: devicePoolId.value,
    });
    dispatchMsg.value = data.message || "已下发";
    await loadHistory();
  } catch (e) {
    dispatchErr.value = formatApiError(e);
  } finally {
    dispatching.value = false;
  }
}

onMounted(async () => {
  pageErr.value = "";
  try {
    await Promise.all([loadArtifacts(), loadCasesAndSets(), loadPools(), loadHistory()]);
    if (artifacts.value.length && artifactId.value == null) {
      artifactId.value = artifacts.value[0].id;
    }
    if (caseSets.value.length && caseSetId.value == null) {
      caseSetId.value = caseSets.value[0].id;
    }
  } catch (e) {
    pageErr.value = formatApiError(e);
  }
});

watch(step, (s) => {
  if (s === 4) loadHistory();
});
</script>

<style scoped>
.wizard-page {
  max-width: 720px;
  margin: 0 auto;
}

.page-head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
}

.hint {
  margin: 0 0 1rem;
  color: #475569;
  font-size: 0.92rem;
  line-height: 1.55;
}

.steps {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  margin-bottom: 1rem;
  font-size: 0.88rem;
  color: #94a3b8;
}

.steps .on {
  color: #2563eb;
  font-weight: 600;
}

.sep {
  opacity: 0.6;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.6rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.panel.card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.1rem 1.2rem 1.25rem;
}

.panel h2 {
  margin: 0 0 0.75rem;
  font-size: 1.05rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 0.75rem;
}

.field span {
  font-size: 0.85rem;
  color: #475569;
}

.field input[type="text"],
.field input:not([type="checkbox"]):not([type="radio"]) {
  padding: 0.45rem 0.55rem;
  border-radius: 8px;
  border: 1px solid #cbd5e1;
}

.list-block {
  margin-top: 1rem;
}

.list-block h3 {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
}

.radio-row,
.check-row {
  display: flex;
  gap: 0.45rem;
  align-items: flex-start;
  margin: 0.35rem 0;
  font-size: 0.9rem;
  cursor: pointer;
}

.cases-box {
  max-height: 220px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 0.5rem 0.65rem;
  margin: 0.75rem 0;
}

.cases-box h3 {
  margin: 0 0 0.35rem;
  font-size: 0.88rem;
}

.nav-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  margin-top: 1.25rem;
}

.err {
  color: #b91c1c;
  font-size: 0.88rem;
}

.ok-msg {
  color: #047857;
  margin-top: 0.65rem;
}

.hint-ai {
  font-size: 0.85rem;
  color: #0369a1;
  margin: 0.35rem 0 0.75rem;
}

.row-actions {
  margin-bottom: 0.75rem;
}

.sum {
  margin: 0 0 1rem;
  padding-left: 1.1rem;
  line-height: 1.6;
}

.hist {
  margin-top: 1.25rem;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.tbl th,
.tbl td {
  border-bottom: 1px solid #e2e8f0;
  padding: 0.35rem 0.45rem;
  text-align: left;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.85rem;
}
</style>

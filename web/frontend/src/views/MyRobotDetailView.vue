<template>
  <div class="page">
    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <template v-else-if="inst">
      <header class="head">
        <router-link class="crumb" :to="{ name: 'myRobots' }">← 我的机器人</router-link>
        <div class="head-row">
          <div>
            <h1>{{ inst.instance_code }}</h1>
            <p class="sub">
              {{ inst.display_name || "未命名展示名称" }} ·
              <span class="pill">{{ robotTypeLabel(inst.catalog_robot_id) }}</span>
              <span class="runtime-pill" :class="`runtime-pill--${inst.runtime_status || 'idle'}`">
                {{ runtimeStatusLabel(inst.runtime_status) }}
              </span>
            </p>
          </div>
          <RobotMascotAvatar class="mascot" inline :robot-id="inst.catalog_robot_id" />
        </div>
      </header>

      <section
        v-if="inst.runtime_status === 'executing' && (featureAnalysisLiveRoute(inst) || testRunLiveRoute(inst))"
        class="card detail active-task"
      >
        <h2>进行中的任务</h2>
        <p class="hint">离开分析/执行页后，可由此继续查看实时过程。</p>
        <div class="task-links">
          <router-link
            v-if="featureAnalysisLiveRoute(inst)"
            class="btn primary"
            :to="featureAnalysisLiveRoute(inst)"
          >
            分析详情
          </router-link>
          <router-link
            v-if="testRunLiveRoute(inst)"
            class="btn primary"
            :to="testRunLiveRoute(inst)"
          >
            执行详情
          </router-link>
        </div>
      </section>

      <section class="card detail">
        <h2>基础信息</h2>
        <dl class="kv">
          <dt>实例编号</dt>
          <dd class="mono">{{ inst.instance_code }}</dd>
          <dt>机器人类型</dt>
          <dd>{{ robotTypeLabel(inst.catalog_robot_id) }}</dd>
          <dt>目录机器人 ID</dt>
          <dd class="muted small mono">{{ inst.catalog_robot_id }}</dd>
          <dt>关联租用单</dt>
          <dd class="mono">#{{ inst.rental_order_id }}</dd>
          <dt>提交租用用户 ID</dt>
          <dd class="mono">{{ inst.leasing_user_id }}</dd>
          <dt>测试执行引擎</dt>
          <dd>{{ agentEngineLabel(inst.test_agent_backend) }}（{{ inst.test_agent_backend || "autoglm" }}）</dd>
          <dt>默认执行设备</dt>
          <dd>{{ devicePlatformLabel(inst.device_platform) }}</dd>
          <dt>运行状态</dt>
          <dd>{{ runtimeStatusLabel(inst.runtime_status) }}</dd>
          <dt>实例状态</dt>
          <dd>
            <span class="instance-pill" :class="`instance-pill--${instanceStatusClass(inst.status)}`">
              {{ instanceStatusLabel(inst.status) }}
            </span>
          </dd>
          <dt>创建时间</dt>
          <dd>{{ fmt(inst.created_at) }}</dd>
        </dl>
      </section>

      <section v-if="canEdit" class="card detail">
        <h2>展示属性</h2>
        <p class="hint">用于用例执行与监控中的展示；可随时修改并保存。</p>
        <label class="field">
          <span>展示名称</span>
          <input v-model="draft.display_name" type="text" maxlength="128" />
        </label>
        <label class="field">
          <span>简介</span>
          <textarea v-model="draft.display_bio" rows="5" maxlength="2000" />
        </label>
        <label class="field">
          <span>测试执行引擎</span>
          <select v-model="draft.test_agent_backend" class="select-full">
            <option value="autoglm">AutoGLM（智谱 AutoGLM-Phone）</option>
            <option value="midscene">Midscene（视觉自动化 / 千问等）</option>
          </select>
        </label>
        <label class="field">
          <span>默认执行设备</span>
          <select v-model="draft.device_platform" class="select-full">
            <option value="android">Android / ADB</option>
            <option value="harmonyos">鸿蒙 HarmonyOS / HDC</option>
          </select>
        </label>
        <p class="hint small">
          此为用例页的默认设备；执行前仍可在「测试用例」页临时切换 Android / 鸿蒙。
        </p>
        <button type="button" class="btn primary" :disabled="saving" @click="save">
          {{ saving ? "保存中…" : "保存修改" }}
        </button>
      </section>

      <section v-if="canEdit" class="card detail">
        <h2>知识库与 Skill</h2>
        <p class="hint">绑定项目知识库集合与 Skill 配置，供 Agentic RAG 检索（用例生成 / 功能分析 / 测试执行）。</p>
        <label class="field">
          <span>Skill 配置</span>
          <select v-model.number="kbDraft.skill_profile_id" class="select-full">
            <option :value="null">（默认）</option>
            <option v-for="sp in skillProfiles" :key="sp.id" :value="sp.id">
              {{ sp.name }} — {{ (sp.skill_names || []).join(", ") }}
            </option>
          </select>
        </label>
        <div class="field">
          <div class="kb-coll-head">
            <span>知识库集合</span>
            <button
              v-if="kbDraft.collection_ids.length"
              type="button"
              class="btn ghost mini"
              @click="kbDraft.collection_ids = []"
            >
              清空选择
            </button>
          </div>
          <p v-if="!allCollections.length" class="hint small">暂无集合，请先在项目「知识库」页创建。</p>
          <ul v-else class="kb-coll-list">
            <li v-for="c in allCollections" :key="c.id">
              <label class="kb-coll-item">
                <input v-model="kbDraft.collection_ids" type="checkbox" :value="c.id" />
                <span>[项目 {{ c.project_id }}] {{ c.name }}</span>
              </label>
            </li>
          </ul>
        </div>
        <p v-if="kbBinding.skill_names?.length" class="hint small">
          当前可用 Skill：{{ kbBinding.skill_names.join(", ") }}
        </p>
        <button type="button" class="btn" :disabled="kbSaving" @click="saveKbBinding">
          {{ kbSaving ? "保存中…" : "保存知识库绑定" }}
        </button>
      </section>
      <section v-else class="card detail">
        <h2>展示属性</h2>
        <p class="hint muted">您不是该实例的租用提交人，仅可查看。</p>
        <p><strong>展示名称：</strong>{{ inst.display_name || "—" }}</p>
        <p><strong>简介：</strong>{{ inst.display_bio || "—" }}</p>
        <p><strong>测试执行引擎：</strong>{{ agentEngineLabel(inst.test_agent_backend) }}</p>
        <p><strong>默认执行设备：</strong>{{ devicePlatformLabel(inst.device_platform) }}</p>
      </section>
    </template>

    <div v-else-if="!loading" class="empty card">未找到该机器人实例。</div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import client, { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import RobotMascotAvatar from "@/components/RobotMascotAvatar.vue";
import {
  featureAnalysisLiveRoute,
  instanceStatusClass,
  instanceStatusLabel,
  robotTypeLabel,
  runtimeStatusLabel,
  testRunLiveRoute,
} from "@/constants/robotCatalog";

const route = useRoute();
const auth = useAuthStore();
const inst = ref(null);
const loading = ref(true);
const error = ref("");
const saving = ref(false);
const kbSaving = ref(false);
const skillProfiles = ref([]);
const allCollections = ref([]);
const kbBinding = ref({});
const draft = reactive({
  display_name: "",
  display_bio: "",
  test_agent_backend: "autoglm",
  device_platform: "android",
});
const kbDraft = reactive({
  skill_profile_id: null,
  collection_ids: [],
});

const canEdit = computed(() => {
  if (!inst.value || auth.userId == null) return false;
  return Number(inst.value.leasing_user_id) === Number(auth.userId);
});

function fmt(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function agentEngineLabel(backend) {
  const b = String(backend || "autoglm").toLowerCase();
  if (b === "midscene") return "Midscene";
  return "AutoGLM";
}

function devicePlatformLabel(platform) {
  const p = String(platform || "android").toLowerCase();
  return p === "harmonyos" ? "鸿蒙 / HDC" : "Android / ADB";
}

function applyDraft() {
  const r = inst.value;
  if (!r) return;
  draft.display_name = r.display_name || "";
  draft.display_bio = r.display_bio || "";
  draft.test_agent_backend = r.test_agent_backend || "autoglm";
  draft.device_platform = r.device_platform || "android";
}

async function loadKbBinding() {
  if (!inst.value) return;
  try {
    const { data: ctx } = await client.get(
      `/api/knowledge/robot-instances/${inst.value.id}/knowledge-binding`,
    );
    kbBinding.value = ctx;
    kbDraft.skill_profile_id = ctx.skill_profile_id ?? null;
    kbDraft.collection_ids = [...(ctx.knowledge_collection_ids || [])];
    const { data: prof } = await client.get("/api/knowledge/skill-profiles", {
      params: { catalog_robot_id: inst.value.catalog_robot_id },
    });
    skillProfiles.value = prof.items || [];
    const { data: projects } = await client.get("/api/projects");
    const cols = [];
    for (const p of projects || []) {
      try {
        const { data: cList } = await client.get(`/api/knowledge/projects/${p.id}/collections`);
        for (const c of cList || []) {
          cols.push({ ...c, project_id: p.id });
        }
      } catch {
        /* ignore unreadable project */
      }
    }
    allCollections.value = cols;
  } catch (e) {
    /* non-fatal */
    console.warn("loadKbBinding", e);
  }
}

async function load() {
  const raw = route.params.instanceId;
  const id = Number(Array.isArray(raw) ? raw[0] : raw);
  if (!Number.isFinite(id) || id < 1) {
    loading.value = false;
    inst.value = null;
    error.value = "无效的实例 ID";
    return;
  }
  loading.value = true;
  error.value = "";
  inst.value = null;
  try {
    const { data } = await client.get(`/api/robot-instances/${id}`);
    inst.value = data;
    applyDraft();
    await loadKbBinding();
  } catch (e) {
    error.value = formatApiError(e);
    inst.value = null;
  } finally {
    loading.value = false;
  }
}

async function saveKbBinding() {
  if (!inst.value) return;
  kbSaving.value = true;
  error.value = "";
  try {
    const ids = (kbDraft.collection_ids || []).map((x) => Number(x)).filter((n) => n > 0);
    await client.patch(`/api/knowledge/robot-instances/${inst.value.id}/knowledge-binding`, {
      skill_profile_id: kbDraft.skill_profile_id || null,
      knowledge_collection_ids: ids,
      rag_policy_override: {},
    });
    await loadKbBinding();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    kbSaving.value = false;
  }
}

async function save() {
  if (!inst.value) return;
  saving.value = true;
  error.value = "";
  try {
    await client.patch(`/api/robot-instances/${inst.value.id}`, {
      display_name: (draft.display_name || "").trim(),
      display_bio: (draft.display_bio || "").trim(),
      test_agent_backend: draft.test_agent_backend || "autoglm",
      device_platform: draft.device_platform || "android",
    });
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    saving.value = false;
  }
}

onMounted(load);
watch(
  () => route.params.instanceId,
  () => load(),
);
</script>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
}

.crumb {
  display: inline-block;
  margin-bottom: 0.75rem;
  font-size: 0.88rem;
  color: #2563eb;
  text-decoration: none;
}

.crumb:hover {
  text-decoration: underline;
}

.head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.45rem;
  font-family: ui-monospace, monospace;
  color: #1d4ed8;
}

.sub {
  margin: 0;
  color: #64748b;
  font-size: 0.92rem;
}

.head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
}

.mascot {
  flex-shrink: 0;
}

.pill {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e40af;
  margin-right: 0.35rem;
}

.pill--muted {
  background: #f1f5f9;
  color: #475569;
}

.runtime-pill {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
  margin-right: 0.35rem;
}

.runtime-pill--executing {
  background: #dbeafe;
  color: #1d4ed8;
}

.runtime-pill--idle {
  background: #f1f5f9;
  color: #475569;
}

.runtime-pill--abnormal {
  background: #fee2e2;
  color: #b91c1c;
}

.instance-pill {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-weight: 600;
}

.instance-pill--started {
  background: #dcfce7;
  color: #166534;
}

.instance-pill--stopped {
  background: #f1f5f9;
  color: #64748b;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 1.1rem 1.2rem;
  background: #fff;
  margin-top: 1rem;
}

.detail h2 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
  color: #0f172a;
}

.hint {
  margin: 0 0 0.85rem;
  font-size: 0.85rem;
  color: #64748b;
}

.kv {
  display: grid;
  grid-template-columns: 8rem 1fr;
  gap: 0.35rem 1rem;
  margin: 0;
  font-size: 0.9rem;
}

.kv dt {
  margin: 0;
  color: #64748b;
}

.kv dd {
  margin: 0;
  color: #0f172a;
}

.mono {
  font-family: ui-monospace, monospace;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
  font-size: 0.82rem;
  color: #64748b;
}

.field input,
.field textarea,
.field select.select-full {
  font-size: 0.95rem;
  padding: 0.5rem 0.6rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.field select.select-full {
  width: 100%;
  max-width: 100%;
}

.kb-coll-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}
.kb-coll-list {
  list-style: none;
  margin: 0;
  padding: 0.5rem 0.65rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
}
.kb-coll-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.35rem 0;
  cursor: pointer;
  font-size: 0.92rem;
}
.kb-coll-item input {
  margin-top: 0.2rem;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.empty {
  padding: 1.25rem;
  color: #64748b;
}

.muted {
  color: #64748b;
}

.active-task .task-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
}

.active-task .btn {
  display: inline-block;
  text-decoration: none;
  text-align: center;
}
</style>

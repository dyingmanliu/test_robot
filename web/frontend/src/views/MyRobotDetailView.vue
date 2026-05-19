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
              <span class="pill">{{ inst.catalog_robot_id }}</span>
              <span class="pill pill--muted">{{ inst.status }}</span>
            </p>
          </div>
          <RobotMascotAvatar class="mascot" inline :robot-id="inst.catalog_robot_id" />
        </div>
      </header>

      <section class="card detail">
        <h2>基础信息</h2>
        <dl class="kv">
          <dt>实例编号</dt>
          <dd class="mono">{{ inst.instance_code }}</dd>
          <dt>目录机器人 ID</dt>
          <dd>{{ inst.catalog_robot_id }}</dd>
          <dt>关联租用单</dt>
          <dd class="mono">#{{ inst.rental_order_id }}</dd>
          <dt>提交租用用户 ID</dt>
          <dd class="mono">{{ inst.leasing_user_id }}</dd>
          <dt>测试执行引擎</dt>
          <dd>{{ agentEngineLabel(inst.test_agent_backend) }}（{{ inst.test_agent_backend || "autoglm" }}）</dd>
          <dt>默认执行设备</dt>
          <dd>{{ devicePlatformLabel(inst.device_platform) }}</dd>
          <dt>运行状态</dt>
          <dd>{{ inst.status }}</dd>
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
          YAML 用例仅支持 Midscene 引擎。
        </p>
        <button type="button" class="btn primary" :disabled="saving" @click="save">
          {{ saving ? "保存中…" : "保存修改" }}
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

const route = useRoute();
const auth = useAuthStore();
const inst = ref(null);
const loading = ref(true);
const error = ref("");
const saving = ref(false);
const draft = reactive({
  display_name: "",
  display_bio: "",
  test_agent_backend: "autoglm",
  device_platform: "android",
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
  } catch (e) {
    error.value = formatApiError(e);
    inst.value = null;
  } finally {
    loading.value = false;
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
</style>

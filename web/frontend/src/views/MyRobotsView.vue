<template>
  <div class="page">
    <header class="head">
      <h1>我的机器人</h1>
      <p class="sub">
        审批通过后展示本公司全部已实例化机器人；同一公司成员均可查看。仅<strong>提交租用申请的用户</strong>可修改展示名称、简介与测试执行引擎。
      </p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <div v-else-if="!instances.length" class="empty card">
      <p>暂无已实例化的机器人。</p>
      <p class="muted small">
        请先在「机器人商城」提交租用申请，并在
        <router-link :to="{ name: 'myRentalApplications' }">租用申请清单</router-link>
        中查看审批进度。
      </p>
    </div>

    <div v-else class="table-wrap card">
      <table class="tbl">
        <thead>
          <tr>
            <th>实例编号</th>
            <th>展示名称</th>
            <th>目录类型</th>
            <th>执行引擎</th>
            <th>状态</th>
            <th>提交人（用户 ID）</th>
            <th>创建时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in instances"
            :key="r.id"
            class="row-click"
            @click="goDetail(r.id)"
          >
            <td class="mono strong">{{ r.instance_code }}</td>
            <td>{{ r.display_name || "—" }}</td>
            <td><span class="pill">{{ r.catalog_robot_id }}</span></td>
            <td class="muted small">{{ engineLabel(r.test_agent_backend) }}</td>
            <td>{{ r.status }}</td>
            <td class="muted small mono">{{ r.leasing_user_id }}</td>
            <td class="muted small">{{ fmt(r.created_at) }}</td>
            <td class="link-cell">
              <router-link
                class="row-link"
                :to="{ name: 'myRobotDetail', params: { instanceId: String(r.id) } }"
                @click.stop
              >
                详情
              </router-link>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import client, { formatApiError } from "@/api/client";

const router = useRouter();
const instances = ref([]);
const loading = ref(true);
const error = ref("");

function engineLabel(backend) {
  const b = String(backend || "autoglm").toLowerCase();
  if (b === "midscene") return "Midscene";
  return "AutoGLM";
}

function fmt(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function goDetail(id) {
  const n = Number(id);
  if (!Number.isFinite(n) || n < 1) return;
  router.push({ name: "myRobotDetail", params: { instanceId: String(n) } }).catch(() => {});
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/robot-instances/mine");
    instances.value = data || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.page {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 1rem 2rem;
}

.head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.5rem;
}

.sub {
  margin: 0 0 1rem;
  color: #64748b;
  font-size: 0.92rem;
}

.banner.err {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
}

.card {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
}

.empty {
  padding: 1.25rem;
  color: #334155;
}

.empty .small {
  margin-top: 0.5rem;
}

.table-wrap {
  overflow-x: auto;
}

.tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.tbl th,
.tbl td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid #f1f5f9;
}

.tbl th {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #64748b;
  font-weight: 600;
}

.row-click {
  cursor: pointer;
}

.row-click:hover {
  background: #f8fafc;
}

.mono {
  font-family: ui-monospace, monospace;
}

.strong {
  font-weight: 700;
  color: #1d4ed8;
}

.pill {
  font-size: 0.72rem;
  padding: 0.15rem 0.45rem;
  border-radius: 6px;
  background: #eff6ff;
  color: #1e40af;
}

.link-cell {
  text-align: right;
  width: 4rem;
}

.row-link {
  color: #2563eb;
  font-size: 0.88rem;
  text-decoration: none;
}

.row-link:hover {
  text-decoration: underline;
}

.small {
  font-size: 0.82rem;
}

.muted {
  color: #64748b;
}

.back {
  margin-top: 1.5rem;
}
</style>

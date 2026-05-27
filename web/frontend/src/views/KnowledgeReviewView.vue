<template>
  <div class="review-page">
    <header class="head">
      <h1>知识库审核</h1>
      <p class="sub">平台管理员审核待发布文档（规范、策略等上传内容）</p>
    </header>

    <p v-if="error" class="banner err">{{ error }}</p>
    <p v-if="msg" class="banner ok">{{ msg }}</p>
    <p v-if="loading" class="muted">加载中…</p>

    <section v-else class="card">
      <div v-if="items.length" class="section-head">
        <span class="queue-hint">共 {{ items.length }} 条待审核</span>
      </div>
      <ul v-if="items.length" class="review-list">
        <li v-for="row in items" :key="row.id" class="review-item">
          <div class="review-main">
            <div class="review-title">{{ row.title }}</div>
            <div class="review-meta">
              <span class="type-tag">{{ docTypeLabel(row.doc_type) }}</span>
              <span class="status-tag">待审核</span>
              <span class="meta-text">项目 #{{ row.project_id }}</span>
              <span class="meta-text">{{ fmt(row.updated_at) }}</span>
            </div>
          </div>
          <div class="review-actions">
            <button type="button" class="review-btn review-btn--pass" @click="review(row.id, true)">
              通过
            </button>
            <button type="button" class="review-btn review-btn--reject" @click="openReject(row)">
              驳回
            </button>
          </div>
        </li>
      </ul>
      <div v-else class="empty">
        <p class="muted">暂无待审核文档</p>
      </div>
    </section>

    <Teleport to="body">
      <div v-if="rejectDialog.open" class="review-modal-overlay" @click.self="rejectDialog.open = false">
        <div class="review-modal" role="dialog" aria-modal="true">
          <h3>驳回文档</h3>
          <p class="modal-doc-title">{{ rejectDialog.title }}</p>
          <label class="field">
            <span>备注（可选）</span>
            <textarea v-model="rejectDialog.note" rows="3" placeholder="说明驳回原因，便于上传者修改" />
          </label>
          <div class="modal-actions">
            <button type="button" class="review-modal-btn" @click="rejectDialog.open = false">取消</button>
            <button type="button" class="review-modal-btn review-modal-btn--danger" @click="confirmReject">
              确认驳回
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import client, { formatApiError } from "@/api/client";
import { docTypeLabel } from "@/utils/knowledgeLabels";

const items = ref([]);
const loading = ref(true);
const error = ref("");
const msg = ref("");

const rejectDialog = reactive({ open: false, id: null, title: "", note: "" });

function fmt(iso) {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await client.get("/api/knowledge/review-queue");
    items.value = data.items || [];
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}

async function review(docId, approve) {
  error.value = "";
  msg.value = "";
  try {
    await client.post(`/api/knowledge/documents/${docId}/review`, { approve, note: "" });
    msg.value = approve ? "已通过，文档将自动索引" : "已驳回";
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  }
}

function openReject(row) {
  rejectDialog.open = true;
  rejectDialog.id = row.id;
  rejectDialog.title = row.title;
  rejectDialog.note = "";
}

async function confirmReject() {
  try {
    await client.post(`/api/knowledge/documents/${rejectDialog.id}/review`, {
      approve: false,
      note: rejectDialog.note,
    });
    rejectDialog.open = false;
    msg.value = "已驳回";
    await load();
  } catch (e) {
    error.value = formatApiError(e);
  }
}

onMounted(load);
</script>

<style scoped>
.review-page {
  max-width: 880px;
  margin: 0 auto;
  padding: 1.5rem 1rem 3rem;
}
.head h1 {
  margin: 0 0 0.35rem;
  font-size: 1.35rem;
}
.sub {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
}
.card {
  background: #fff;
  border: 1px solid #e8edf3;
  border-radius: 10px;
  padding: 1rem 1.15rem;
}
.section-head {
  margin-bottom: 0.75rem;
  padding-bottom: 0.65rem;
  border-bottom: 1px solid #f1f5f9;
}
.queue-hint {
  font-size: 0.8125rem;
  color: #64748b;
  font-weight: 500;
}
.review-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.review-item {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.25rem;
  padding: 0.85rem 1rem;
  background: #fff;
  border: 1px solid #e8edf3;
  border-left: 3px solid #f59e0b;
  border-radius: 8px;
  transition: box-shadow 0.15s ease, border-color 0.15s ease;
}
.review-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.06);
}
.review-main {
  flex: 1;
  min-width: 0;
}
.review-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #0f172a;
  margin-bottom: 0.45rem;
  line-height: 1.35;
}
.review-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem 0.55rem;
}
.type-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 0.5rem;
  font-size: 0.72rem;
  border-radius: 4px;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
}
.status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 0.5rem;
  font-size: 0.72rem;
  font-weight: 500;
  border-radius: 999px;
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fde68a;
}
.meta-text {
  font-size: 0.75rem;
  color: #94a3b8;
  line-height: 22px;
}
.review-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 0.4rem;
}
.review-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 28px;
  min-width: 52px;
  padding: 0 12px;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.12s, border-color 0.12s, color 0.12s;
}
.review-btn--pass {
  background: #2563eb;
  border: 1px solid #2563eb;
  color: #fff;
}
.review-btn--pass:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
}
.review-btn--reject {
  background: #fff;
  border: 1px solid #fecaca;
  color: #dc2626;
}
.review-btn--reject:hover {
  background: #fef2f2;
  border-color: #fca5a5;
}
.empty {
  text-align: center;
  padding: 2.5rem 1rem;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px dashed #e2e8f0;
}
.banner {
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
}
.banner.err {
  background: #fdecea;
  color: #b42318;
}
.banner.ok {
  background: #e8f5e9;
  color: #1b5e20;
}

@media (max-width: 640px) {
  .review-item {
    flex-direction: column;
    align-items: stretch;
  }
  .review-actions {
    justify-content: flex-end;
    align-self: flex-end;
  }
}
</style>

<style>
.review-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  z-index: 1000;
}
.review-modal {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.2);
  border: 1px solid #e2e8f0;
}
.review-modal h3 {
  margin: 0 0 0.35rem;
}
.review-modal .modal-doc-title {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: #475569;
  font-weight: 500;
}
.review-modal .field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}
.review-modal .field span {
  font-size: 0.85rem;
  color: #475569;
}
.review-modal textarea {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font: inherit;
  resize: vertical;
}
.review-modal .modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.review-modal-btn {
  height: 30px;
  padding: 0 14px;
  font-size: 0.8125rem;
  font-weight: 500;
  font-family: inherit;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  cursor: pointer;
}
.review-modal-btn:hover {
  background: #f8fafc;
}
.review-modal-btn--danger {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
}
.review-modal-btn--danger:hover {
  background: #b91c1c;
  border-color: #b91c1c;
}
</style>

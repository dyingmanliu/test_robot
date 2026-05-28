/** 知识库 doc_type / status 中文展示 */

export const DOC_TYPE_LABELS = {
  standard: "测试规范",
  strategy: "测试策略",
  feature_list: "功能清单",
  page_model: "页面模型",
  ui_element: "UI 元素",
  glossary: "术语表",
  app_screenshot: "应用截图",
  case: "测试用例",
  feature_tree: "功能树",
  execution_hint: "执行经验",
  other: "其他",
};

export const DOC_STATUS_LABELS = {
  draft: "草稿",
  pending_parse: "待解析",
  parsing: "索引中",
  pending_review: "待审核",
  active: "已发布",
  rejected: "已驳回",
  archived: "已归档",
};

/** @type {Record<string, string>} */
export const DOC_STATUS_CLASS = {
  draft: "status--draft",
  pending_parse: "status--pending",
  parsing: "status--parsing",
  pending_review: "status--review",
  active: "status--active",
  rejected: "status--rejected",
  archived: "status--archived",
};

export const COLLECTION_STATUS_LABELS = {
  active: "可用",
};

/** 侧边栏 / 标题区展示顺序（需关注的排前） */
export const DOC_STATUS_SUMMARY_ORDER = [
  "parsing",
  "pending_parse",
  "pending_review",
  "draft",
  "rejected",
  "active",
  "archived",
];

export function collectionStatusLabel(status) {
  return COLLECTION_STATUS_LABELS[status] || status || "—";
}

export function collectionStatusClass(status) {
  return status === "active" ? "status--active" : "status--default";
}

/** @param {Record<string, number> | null | undefined} counts */
export function docStatusSummaryItems(counts) {
  const src = counts || {};
  return DOC_STATUS_SUMMARY_ORDER.filter((s) => (src[s] || 0) > 0).map((s) => ({
    status: s,
    label: docStatusLabel(s),
    class: docStatusClass(s),
    count: src[s],
  }));
}

export function docTypeLabel(type) {
  return DOC_TYPE_LABELS[type] || type || "—";
}

export function docStatusLabel(status) {
  return DOC_STATUS_LABELS[status] || status || "—";
}

export function docStatusClass(status) {
  return DOC_STATUS_CLASS[status] || "status--default";
}

/** 与后端 REINDEXABLE_STATUSES 一致 */
export function canReindex(status) {
  return status === "active" || status === "draft" || status === "pending_parse";
}

export function reindexBlockHint(status) {
  const hints = {
    parsing: "索引进行中",
    pending_review: "待审核后自动索引",
    rejected: "修改后提交审核",
    archived: "已归档",
  };
  return hints[status] || "";
}

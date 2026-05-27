/** 子串或按序字符匹配（便于包名/应用名快速筛选） */
export function fuzzyMatch(query, text) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return true;
  const t = String(text || "").toLowerCase();
  if (t.includes(q)) return true;
  let i = 0;
  for (const c of q) {
    const j = t.indexOf(c, i);
    if (j < 0) return false;
    i = j + 1;
  }
  return true;
}

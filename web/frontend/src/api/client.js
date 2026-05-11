import axios from "axios";

/**
 * 开发环境默认走同源 `/api`，由 Vite 代理到后端。
 * 部署在 API 网关后时，设置 `VITE_API_BASE` 为网关地址（含协议与域名），请求将发往用户服务等后端。
 */
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || "",
  timeout: 0,
});

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("tcm_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** 管理员变更角色后 JWT 内 role 与数据库不一致时，自动刷新令牌后重试一次 */
client.interceptors.response.use(
  (r) => r,
  async (error) => {
    const cfg = error.config;
    const detail = error.response?.data?.detail;
    const stale =
      error.response?.status === 403 &&
      typeof detail === "string" &&
      detail.includes("角色已变更") &&
      cfg &&
      !cfg.__roleRetry;
    if (stale) {
      cfg.__roleRetry = true;
      try {
        const { data } = await client.post("/api/auth/refresh");
        localStorage.setItem("tcm_token", data.access_token);
        const { useAuthStore } = await import("@/stores/auth");
        const auth = useAuthStore();
        auth.token = data.access_token;
        await auth.fetchMe();
        cfg.headers = cfg.headers || {};
        cfg.headers.Authorization = `Bearer ${data.access_token}`;
        return client(cfg);
      } catch {
        /* 刷新失败则返回原错误 */
      }
    }
    return Promise.reject(error);
  },
);

/** 解析 FastAPI / Axios 错误信息供页面展示 */
export function formatApiError(error) {
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((x) => (typeof x === "string" ? x : x.msg || JSON.stringify(x)))
      .join("；");
  }
  return error.message || "请求失败";
}

export default client;

import { defineStore } from "pinia";
import client from "@/api/client";

/** 与后端 `app/rbac.py` 一致 */
export const ROLE_PLATFORM_ADMIN = "platform_admin";
export const ROLE_TSE = "tse";
export const ROLE_ENTERPRISE = "enterprise";

export const ROLE_LABELS = {
  [ROLE_PLATFORM_ADMIN]: "平台管理员",
  [ROLE_TSE]: "内部测试工程师（TSE）",
  [ROLE_ENTERPRISE]: "外部企业用户",
};

function maskPhone(p) {
  if (!p || p.length < 7) return p || "";
  if (p.length === 11) return `${p.slice(0, 3)}****${p.slice(-4)}`;
  return `${p.slice(0, 2)}****${p.slice(-2)}`;
}

function displayFromUser(data) {
  const nick = data.nickname && String(data.nickname).trim();
  if (nick) return nick;
  if (data.phone) return maskPhone(data.phone);
  if (data.email) return data.email;
  return data.username || "";
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: localStorage.getItem("tcm_token") || "",
    /** RBAC 角色，来自 GET /api/auth/me */
    role: localStorage.getItem("tcm_role") || "",
    /** 顶栏展示：昵称优先，否则手机号脱敏 / 邮箱 / 用户名 */
    displayLabel:
      localStorage.getItem("tcm_display") ||
      localStorage.getItem("tcm_username") ||
      "",
  }),
  actions: {
    setSession(token, displayLabel) {
      this.token = token;
      this.displayLabel = displayLabel || "";
      localStorage.setItem("tcm_token", token);
      if (displayLabel) localStorage.setItem("tcm_display", displayLabel);
      localStorage.removeItem("tcm_username");
    },
    clear() {
      this.token = "";
      this.role = "";
      this.displayLabel = "";
      localStorage.removeItem("tcm_token");
      localStorage.removeItem("tcm_role");
      localStorage.removeItem("tcm_display");
      localStorage.removeItem("tcm_username");
    },
    async fetchMe() {
      const { data } = await client.get("/api/auth/me");
      const label = displayFromUser(data);
      this.displayLabel = label;
      this.role = data.role || "";
      localStorage.setItem("tcm_display", label);
      localStorage.setItem("tcm_role", this.role);
      localStorage.removeItem("tcm_username");
      return data;
    },
    /** @param {string} account 手机号、邮箱或历史用户名 */
    async login(account, password) {
      const { data } = await client.post("/api/auth/login", { account, password });
      this.setSession(data.access_token, "");
      await this.fetchMe();
    },
    /** @param {{ phone?: string, email?: string, password: string }} body */
    async register(body) {
      const payload = { password: body.password };
      if (body.phone) payload.phone = body.phone;
      if (body.email) payload.email = body.email;
      await client.post("/api/auth/register", payload);
      const account = body.phone || body.email || "";
      await this.login(account, body.password);
    },
    /** @param {{ nickname?: string|null, avatar_url?: string|null, company?: string|null }} patch */
    async updateProfile(patch) {
      const { data } = await client.patch("/api/auth/profile", patch);
      const label = displayFromUser(data);
      this.displayLabel = label;
      localStorage.setItem("tcm_display", label);
      return data;
    },
    async changePassword(old_password, new_password, new_password_confirm) {
      await client.post("/api/auth/change-password", {
        old_password,
        new_password,
        new_password_confirm,
      });
    },
  },
});

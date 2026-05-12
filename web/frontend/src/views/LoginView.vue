<template>
  <div class="login-shell">
    <div class="login-backdrop" aria-hidden="true" />
    <div class="login-inner">
      <header class="login-brand">
        <p class="platform-name">识图技术数字机器人</p>
        <p class="platform-tag">数字机器人编排 · 自动化执行 · 租户隔离</p>
      </header>
      <div class="card tech-panel">
        <h1>登录</h1>
        <p class="gateway-hint">
          客户端请求将经 API 网关路由至用户服务；登录成功后颁发 JWT，后续接口携带 Bearer Token 鉴权。
        </p>
        <form @submit.prevent="submit">
          <label class="field">
            <span>手机号或邮箱</span>
            <input
              v-model="account"
              type="text"
              autocomplete="username"
              placeholder="11 位手机号或注册邮箱"
              required
            />
          </label>
          <label class="field">
            <span>密码</span>
            <input v-model="password" type="password" autocomplete="current-password" required />
          </label>
          <p v-if="error" class="err">{{ error }}</p>
          <button type="submit" class="btn primary glow btn-block" :disabled="loading">
            {{ loading ? "登录中…" : "登录" }}
          </button>
        </form>
        <p class="muted foot">
          <router-link :to="{ name: 'platformIntro' }">平台介绍</router-link>
          · 没有账号？
          <router-link to="/register">注册</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const account = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");
const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    await auth.login(account.value.trim(), password.value);
    const redirect = route.query.redirect || "/";
    router.replace(typeof redirect === "string" ? redirect : "/");
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  position: relative;
}

.login-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: #f8fafc;
}

.login-backdrop::after {
  content: "";
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
    ellipse 70% 45% at 50% 0%,
    rgba(59, 130, 246, 0.08),
    transparent 55%
  );
  pointer-events: none;
}

.login-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
}

.login-brand {
  text-align: center;
  margin-bottom: 1.5rem;
}

.platform-name {
  margin: 0 0 0.5rem;
  font-size: clamp(0.95rem, 2.8vw, 1.05rem);
  font-weight: 700;
  letter-spacing: 0.03em;
  line-height: 1.45;
  color: #0f172a;
}

.platform-tag {
  margin: 0;
  font-size: 0.82rem;
  color: #64748b;
  letter-spacing: 0.06em;
}

.card {
  padding: 2rem 1.75rem;
  border-radius: var(--radius-lg);
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
}

.card h1 {
  margin-top: 0;
  margin-bottom: 0.35rem;
  font-size: 1.35rem;
  color: #0f172a;
}

.gateway-hint {
  margin: 0 0 1.25rem;
  font-size: 0.8rem;
  line-height: 1.45;
  color: #64748b;
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

input {
  padding: 0.6rem 0.7rem;
  border: 1px solid #cbd5e1;
  border-radius: var(--radius-md);
  background: #ffffff;
  color: #0f172a;
}

input::placeholder {
  color: #64748b;
}

input:focus {
  outline: none;
  border-color: rgba(96, 165, 250, 0.65);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
}

.btn-block {
  width: 100%;
  margin-top: 0.25rem;
}

.muted.foot {
  margin-top: 1.25rem;
  font-size: 0.9rem;
  color: #64748b;
  text-align: center;
}
</style>

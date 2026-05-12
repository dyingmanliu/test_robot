<template>
  <div class="register-shell">
    <div class="register-backdrop" aria-hidden="true" />
    <div class="register-inner">
      <header class="register-brand">
        <p class="platform-name">识图技术数字机器人</p>
        <p class="platform-tag">注册后即可使用工作台与测试用例能力</p>
      </header>
      <div class="card tech-panel">
      <h1>注册账号</h1>
      <p class="gateway-hint">
        通过手机号或邮箱注册并设置密码；请求经 API 网关转发至用户服务，密码加密存储。注册成功后将自动创建个人空间，并登录获取
        JWT。
      </p>

      <div class="segmented" role="tablist" aria-label="注册方式">
        <button
          type="button"
          class="seg-btn"
          :class="{ active: mode === 'phone' }"
          role="tab"
          :aria-selected="mode === 'phone'"
          @click="mode = 'phone'"
        >
          手机号
        </button>
        <button
          type="button"
          class="seg-btn"
          :class="{ active: mode === 'email' }"
          role="tab"
          :aria-selected="mode === 'email'"
          @click="mode = 'email'"
        >
          邮箱
        </button>
      </div>

      <form @submit.prevent="submit">
        <label v-if="mode === 'phone'" class="field">
          <span>手机号</span>
          <input
            v-model="phone"
            type="tel"
            inputmode="numeric"
            autocomplete="tel"
            placeholder="11 位中国大陆手机号"
            maxlength="11"
            required
          />
        </label>
        <label v-else class="field">
          <span>邮箱</span>
          <input v-model="email" type="email" autocomplete="email" placeholder="name@example.com" required />
        </label>
        <label class="field">
          <span>密码（至少 6 位）</span>
          <input v-model="password" type="password" autocomplete="new-password" required minlength="6" />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button type="submit" class="btn primary glow btn-block" :disabled="loading">
          {{ loading ? "提交中…" : "注册并登录" }}
        </button>
      </form>
      <p class="muted foot">
        <router-link :to="{ name: 'platformIntro' }">平台介绍</router-link>
        · 已有账号？
        <router-link to="/login">登录</router-link>
      </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const mode = ref("phone");
const phone = ref("");
const email = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");
const auth = useAuthStore();
const router = useRouter();

async function submit() {
  error.value = "";
  loading.value = true;
  try {
    if (mode.value === "phone") {
      const digits = phone.value.replace(/\D/g, "");
      if (digits.length !== 11 || !digits.startsWith("1")) {
        error.value = "请输入有效的 11 位手机号";
        return;
      }
      await auth.register({ phone: digits, password: password.value });
    } else {
      await auth.register({ email: email.value.trim(), password: password.value });
    }
    router.replace("/");
  } catch (e) {
    error.value = formatApiError(e);
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.register-shell {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
  position: relative;
}

.register-backdrop {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: #f8fafc;
}

.register-backdrop::after {
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

.register-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
}

.register-brand {
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
}

.gateway-hint {
  margin: 0 0 1.25rem;
  font-size: 0.8rem;
  line-height: 1.45;
  color: #64748b;
}

.card {
  padding: 2rem 1.75rem;
  border-radius: var(--radius-lg);
  background: #ffffff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
}

h1 {
  margin-top: 0;
  margin-bottom: 0.35rem;
  font-size: 1.35rem;
  color: #0f172a;
}

.segmented {
  display: flex;
  gap: 0;
  margin-bottom: 1.25rem;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid #cbd5e1;
}

.seg-btn {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: none;
  background: #f1f5f9;
  color: #475569;
  cursor: pointer;
  font: inherit;
  font-size: 0.9rem;
}

.seg-btn.active {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
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
}

.muted.foot {
  margin-top: 1.25rem;
  font-size: 0.9rem;
  color: #64748b;
  text-align: center;
}
</style>

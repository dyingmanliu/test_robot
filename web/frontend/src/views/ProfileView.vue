<template>
  <div class="profile">
    <header class="page-head">
      <h1>个人中心</h1>
      <p class="br-hint">
        维护您在平台上的数字身份标识（昵称、形象与公司信息），便于跨会话可追溯与协作。
      </p>
    </header>

    <p v-if="loadError" class="banner err">{{ loadError }}</p>

    <section class="card">
      <h2>基础信息</h2>
      <div class="avatar-row">
        <div class="avatar-wrap">
          <img
            v-if="form.avatar_url && !avatarBroken"
            :src="form.avatar_url"
            alt=""
            class="avatar-img"
            @error="avatarBroken = true"
          />
          <div v-else class="avatar-placeholder">{{ initials }}</div>
        </div>
        <p class="muted small">头像支持填写图片 URL（由用户服务持久化）；无效链接时将显示昵称首字。</p>
      </div>

      <form class="grid-form" @submit.prevent="saveProfile">
        <label class="field">
          <span>昵称</span>
          <input v-model="form.nickname" type="text" maxlength="64" placeholder="展示名称，可用于顶栏与可追溯身份" />
        </label>
        <label class="field">
          <span>头像 URL</span>
          <input
            v-model="form.avatar_url"
            type="url"
            maxlength="512"
            placeholder="https://..."
            @input="avatarBroken = false"
          />
        </label>
        <label class="field">
          <span>公司</span>
          <input v-model="form.company" type="text" maxlength="128" placeholder="所在企业或团队" />
        </label>
        <p v-if="profileMsg" class="ok-msg">{{ profileMsg }}</p>
        <p v-if="profileErr" class="err">{{ profileErr }}</p>
        <button type="submit" class="btn primary" :disabled="profileSaving">
          {{ profileSaving ? "保存中…" : "保存资料" }}
        </button>
      </form>
    </section>

    <section class="card">
      <h2>修改密码</h2>
      <p class="muted small">修改前需验证当前密码；新密码至少 6 位，且需两次输入一致。</p>
      <form class="grid-form" @submit.prevent="savePassword">
        <label class="field">
          <span>当前密码</span>
          <input v-model="pwd.old" type="password" autocomplete="current-password" required />
        </label>
        <label class="field">
          <span>新密码</span>
          <input
            v-model="pwd.new"
            type="password"
            autocomplete="new-password"
            required
            minlength="6"
            maxlength="128"
          />
        </label>
        <label class="field">
          <span>确认新密码</span>
          <input v-model="pwd.confirm" type="password" autocomplete="new-password" required minlength="6" />
        </label>
        <p v-if="pwdMsg" class="ok-msg">{{ pwdMsg }}</p>
        <p v-if="pwdErr" class="err">{{ pwdErr }}</p>
        <button type="submit" class="btn primary" :disabled="pwdSaving">
          {{ pwdSaving ? "提交中…" : "更新密码" }}
        </button>
      </form>
    </section>

    <p class="back muted">
      <router-link to="/">← 返回工作台</router-link>
    </p>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { formatApiError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const form = reactive({
  nickname: "",
  avatar_url: "",
  company: "",
});
const pwd = reactive({
  old: "",
  new: "",
  confirm: "",
});

const loadError = ref("");
const profileSaving = ref(false);
const profileMsg = ref("");
const profileErr = ref("");
const pwdSaving = ref(false);
const pwdMsg = ref("");
const pwdErr = ref("");
const avatarBroken = ref(false);

const initials = computed(() => {
  const n = form.nickname && form.nickname.trim();
  if (n) return n.slice(0, 2).toUpperCase();
  return "用户";
});

async function load() {
  loadError.value = "";
  try {
    const data = await auth.fetchMe();
    form.nickname = data.nickname || "";
    form.avatar_url = data.avatar_url || "";
    form.company = data.company || "";
    avatarBroken.value = false;
  } catch (e) {
    loadError.value = formatApiError(e);
  }
}

async function saveProfile() {
  profileMsg.value = "";
  profileErr.value = "";
  profileSaving.value = true;
  try {
    await auth.updateProfile({
      nickname: form.nickname.trim() || null,
      avatar_url: form.avatar_url.trim() || null,
      company: form.company.trim() || null,
    });
    profileMsg.value = "资料已保存";
  } catch (e) {
    profileErr.value = formatApiError(e);
  } finally {
    profileSaving.value = false;
  }
}

async function savePassword() {
  pwdMsg.value = "";
  pwdErr.value = "";
  if (pwd.new !== pwd.confirm) {
    pwdErr.value = "两次输入的新密码不一致";
    return;
  }
  if (pwd.new.length < 6) {
    pwdErr.value = "新密码至少 6 位";
    return;
  }
  pwdSaving.value = true;
  try {
    await auth.changePassword(pwd.old, pwd.new, pwd.confirm);
    pwdMsg.value = "密码已更新";
    pwd.old = "";
    pwd.new = "";
    pwd.confirm = "";
  } catch (e) {
    pwdErr.value = formatApiError(e);
  } finally {
    pwdSaving.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.profile {
  max-width: 560px;
}

.page-head {
  margin-bottom: 1.25rem;
}

.page-head h1 {
  margin: 0 0 0.5rem;
  font-size: 1.5rem;
}

.br-hint {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: #64748b;
}

.banner {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 1rem;
}

.banner.err {
  background: #fef2f2;
  color: #991b1b;
}

.card {
  margin-bottom: 1.5rem;
  padding: 1.5rem;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.card h2 {
  margin: 0 0 1rem;
  font-size: 1.1rem;
}

.avatar-row {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.avatar-wrap {
  flex-shrink: 0;
}

.avatar-img,
.avatar-placeholder {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e2e8f0;
  color: #475569;
  font-size: 1.1rem;
  font-weight: 600;
}

.muted {
  color: #64748b;
}

.small {
  font-size: 0.8rem;
  margin: 0;
  flex: 1;
  line-height: 1.45;
}

.grid-form .field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  margin-bottom: 1rem;
}

.grid-form .field span {
  font-size: 0.85rem;
  color: #475569;
}

.grid-form input {
  padding: 0.55rem 0.65rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.err {
  color: #b91c1c;
  font-size: 0.9rem;
}

.ok-msg {
  color: #15803d;
  font-size: 0.9rem;
}

.back {
  margin-top: 0.5rem;
}
</style>

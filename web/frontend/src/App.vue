<template>
  <div class="layout">
    <!-- 右上角：用户名 + 退出（固定） -->
    <div v-if="auth.token" class="user-corner">
      <span class="who" :title="auth.displayLabel">{{ auth.displayLabel }}</span>
      <button type="button" class="btn ghost btn-exit" @click="logout">退出</button>
    </div>

    <header class="top">
      <div class="top-bar">
        <router-link :to="auth.token ? '/' : { name: 'platformIntro' }" class="brand" @click="closeAllDetails">
          <span class="brand-badge" aria-hidden="true">ST</span>
          <span class="brand-full">识图技术数字机器人</span>
        </router-link>

        <nav v-if="!auth.token" class="nav nav-public">
          <router-link :to="{ name: 'platformIntro' }" class="nav-link" @click="closeAllDetails">平台介绍</router-link>
          <router-link to="/login" class="nav-link" @click="closeAllDetails">登录</router-link>
          <router-link to="/register" class="nav-link nav-em" @click="closeAllDetails">注册</router-link>
        </nav>

        <nav v-else class="nav">
          <router-link to="/" class="nav-link" @click="closeAllDetails">工作台</router-link>

          <router-link to="/marketplace" class="nav-link" @click="closeAllDetails">机器人商城</router-link>

          <router-link to="/my-robots" class="nav-link" @click="closeAllDetails">我的机器人</router-link>

          <details class="nav-dd" :class="{ 'nav-dd--current': projectSpaceMenuActive }" @toggle="onNavDetailsToggle">
            <summary class="nav-dd-trigger">项目空间</summary>
            <div class="nav-dd-panel">
              <router-link to="/projects" class="nav-dd-item" @click="closeAllDetails">项目列表</router-link>
              <router-link :to="{ name: 'cases' }" class="nav-dd-item" @click="closeAllDetails">测试用例</router-link>
            </div>
          </details>

          <details class="nav-dd" :class="{ 'nav-dd--current': monitorMenuActive }" @toggle="onNavDetailsToggle">
            <summary class="nav-dd-trigger">运行监控</summary>
            <div class="nav-dd-panel">
              <router-link
                v-if="auth.role === 'platform_admin' || auth.role === 'tse'"
                to="/monitor"
                class="nav-dd-item"
                @click="closeAllDetails"
              >
                运行监控
              </router-link>
              <router-link to="/dashboard" class="nav-dd-item" @click="closeAllDetails">数据看板</router-link>
            </div>
          </details>

          <details
            v-if="auth.role === 'platform_admin'"
            class="nav-dd"
            :class="{ 'nav-dd--current': adminMenuActive }"
            @toggle="onNavDetailsToggle"
          >
            <summary class="nav-dd-trigger">后台管理</summary>
            <div class="nav-dd-panel">
              <router-link to="/admin/rental-orders" class="nav-dd-item" @click="closeAllDetails">租用审批</router-link>
              <router-link to="/admin/users" class="nav-dd-item" @click="closeAllDetails">用户与角色</router-link>
            </div>
          </details>

          <router-link :to="{ name: 'platformIntro' }" class="nav-link" @click="closeAllDetails">平台介绍</router-link>
          <router-link to="/profile" class="nav-link" @click="closeAllDetails">个人中心</router-link>
        </nav>
      </div>
    </header>

    <router-view v-slot="{ Component, route }">
      <main class="main" :class="{ 'main--bleed': route.meta.fullBleed }">
        <component v-if="Component" :is="Component" :key="route.fullPath" />
      </main>
    </router-view>
  </div>
</template>

<script setup>
import { computed, onMounted, watch } from "vue";
import { useAuthStore } from "@/stores/auth";
import { useRoute, useRouter } from "vue-router";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

/** 子路由命中时高亮对应下拉分组标题 */
const projectSpaceMenuActive = computed(
  () => route.path.startsWith("/projects") || route.path === "/cases",
);
const monitorMenuActive = computed(() => route.path === "/monitor" || route.path === "/dashboard");
const adminMenuActive = computed(
  () => route.path.startsWith("/admin"),
);

/** 路由变化时收起下拉，避免上一页展开的菜单残留 */
watch(
  () => route.fullPath,
  () => {
    closeAllDetails();
  },
);

/** 仅允许一个「项目空间 / 运行监控 / 后台管理」下拉同时展开 */
function onNavDetailsToggle(ev) {
  const target = ev.target;
  if (!(target instanceof HTMLDetailsElement) || !target.open) return;
  document.querySelectorAll(".nav-dd").forEach((el) => {
    if (el !== target && el instanceof HTMLDetailsElement) el.open = false;
  });
}

onMounted(async () => {
  if (auth.token && !auth.displayLabel) {
    try {
      await auth.fetchMe();
    } catch {
      auth.clear();
    }
  }
});

function logout() {
  auth.clear();
  router.push({ name: "login" });
}

/** 导航后收起 details，避免移动端菜单残留 */
function closeAllDetails() {
  document.querySelectorAll(".nav-dd").forEach((el) => {
    if (el instanceof HTMLDetailsElement) el.open = false;
  });
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.user-corner {
  position: fixed;
  top: 0.55rem;
  right: 1rem;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.75rem;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(10px);
  border: 1px solid #e8ecf1;
  border-radius: 999px;
  box-shadow: 0 2px 14px rgb(15 23 42 / 7%);
}

.who {
  font-size: 0.84rem;
  color: #475569;
  max-width: 10rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.btn-exit {
  padding: 0.35rem 0.75rem;
  font-size: 0.82rem;
  border-radius: 999px;
}

.top {
  background: #ffffff;
  border-bottom: 1px solid #e8ecf1;
  position: relative;
  z-index: 10;
}

.top::after {
  content: "";
  display: block;
  height: 2px;
  background: linear-gradient(90deg, #2563eb 0%, #38bdf8 48%, #7dd3fc 100%);
  opacity: 0.75;
}

.top-bar {
  max-width: 1220px;
  margin: 0 auto;
  width: 100%;
  padding: 0.85rem 11rem 0.75rem 1.25rem;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-wrap: wrap;
}

.brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  text-decoration: none;
  color: inherit;
  flex: 0 1 auto;
  min-width: 0;
}

.brand:hover {
  opacity: 0.94;
}

.brand-badge {
  flex-shrink: 0;
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.95rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #fff;
  background: linear-gradient(145deg, #3b82f6 0%, #1d4ed8 55%, #1e3a8a 100%);
  box-shadow: 0 2px 10px rgb(37 99 235 / 28%);
}

.brand-full {
  font-size: clamp(1.05rem, 1.55vw, 1.38rem);
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.28;
  color: #0f172a;
}

.nav {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  flex-wrap: wrap;
  flex: 1 1 auto;
  justify-content: flex-start;
}

.nav-link {
  font-size: 0.84rem;
  color: #475569;
  text-decoration: none;
  padding: 0.42rem 0.65rem;
  border-radius: 8px;
  white-space: nowrap;
  border: 1px solid transparent;
  transition:
    color 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.nav-link:hover {
  color: #1e40af;
  background: #eff6ff;
  text-decoration: none;
}

.nav-link.router-link-active {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}

/* 未登录顶栏：注册主按钮（非当前路由时也保持强调，不与 router-link-active 冲突） */
.nav-link.nav-em {
  color: #1d4ed8;
  border-color: #bfdbfe;
  background: #eff6ff;
}

/* 下拉：原生 details，桌面 hover 同步展开可选中仅 click */
.nav-dd {
  position: relative;
}

.nav-dd-trigger {
  list-style: none;
  font-size: 0.84rem;
  color: #475569;
  padding: 0.42rem 0.65rem;
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
  border: 1px solid transparent;
  transition:
    color 0.15s ease,
    background 0.15s ease,
    border-color 0.15s ease;
}

.nav-dd-trigger::-webkit-details-marker {
  display: none;
}

.nav-dd-trigger::after {
  content: " ▾";
  font-size: 0.65rem;
  opacity: 0.65;
}

.nav-dd[open] .nav-dd-trigger,
.nav-dd.nav-dd--current .nav-dd-trigger {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}

.nav-dd-panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  min-width: 11rem;
  padding: 0.35rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 12px 32px rgb(15 23 42 / 12%);
  z-index: 80;
}

.nav-dd-item {
  display: block;
  padding: 0.48rem 0.7rem;
  border-radius: 8px;
  font-size: 0.84rem;
  color: #334155;
  text-decoration: none;
}

.nav-dd-item:hover {
  background: #f1f5f9;
  color: #1d4ed8;
}

.nav-dd-item.router-link-active {
  color: #1d4ed8;
  background: #eff6ff;
  font-weight: 600;
}

.main {
  flex: 1;
  padding: 1.35rem 1.25rem 2rem;
  max-width: 1160px;
  width: 100%;
  margin: 0 auto;
  background: #ffffff;
}

.main--bleed {
  max-width: none;
  padding: 0;
  width: 100%;
}

@media (max-width: 1100px) {
  .top-bar {
    padding-right: 1.25rem;
    padding-top: 3rem;
  }

  .user-corner {
    top: 0.5rem;
    right: 0.65rem;
    max-width: calc(100vw - 1.3rem);
  }
}

@media (max-width: 640px) {
  .brand-full {
    font-size: 1rem;
  }

  .nav {
    gap: 0.15rem;
  }
}
</style>

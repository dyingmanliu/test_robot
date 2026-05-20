<template>
  <div class="intro">
    <!-- Hero：与全局顶栏配合，不再重复内嵌导航条 -->
    <section class="hero">
      <div class="hero-bg" aria-hidden="true" />
      <div class="hero-inner">
        <p class="hero-kicker">企业级 · 多租户 · AI 驱动</p>
        <h1 class="hero-title">
          鸿蒙生态<span class="hero-accent">智能测试平台</span>
        </h1>
        <p class="hero-lead">
          用<strong>数字机器人</strong>承接分析、执行、专项与质量评估；项目空间隔离资产，执行日志可追溯，计费与商城一站式闭环——对标业界智能测试代理形态，沉淀你可信赖的自动化中枢。
        </p>
        <div class="hero-cta">
          <router-link v-if="!auth.token" to="/register" class="btn btn-xl btn-solid">立即开始使用</router-link>
          <router-link v-else to="/marketplace" class="btn btn-xl btn-solid">浏览机器人商城</router-link>
          <router-link :to="auth.token ? '/projects' : '/login'" class="btn btn-xl btn-outline-muted">{{
            auth.token ? "进入项目空间" : "已有账号登录"
          }}</router-link>
        </div>
      </div>
    </section>

    <!-- 指标条 -->
    <section class="strip">
      <div class="strip-inner">
        <div v-for="s in stats" :key="s.label" class="strip-item">
          <strong>{{ s.value }}</strong>
          <span>{{ s.label }}</span>
        </div>
      </div>
    </section>

    <!-- 核心能力 -->
    <section class="section">
      <div class="section-inner">
        <h2 class="section-title">平台核心能力</h2>
        <p class="section-desc">围绕「项目—用例—执行—报告—运维」全链路，与现有工作台、商城与监控模块一致。</p>
        <div class="feat-grid">
          <article v-for="f in features" :key="f.title" class="feat-card">
            <div class="feat-icon" :class="f.tone">{{ f.icon }}</div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.body }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- 四类数字机器人 -->
    <section class="section">
      <div class="section-inner">
        <h2 class="section-title">四类数字机器人</h2>
        <p class="section-desc">与商城目录一致，可按业务场景单独租用、组合使用。</p>
        <div class="robot-grid">
          <article v-for="r in robots" :key="r.id" class="robot-tile">
            <span class="robot-cat">{{ r.category }}</span>
            <h3>{{ r.name }}</h3>
            <p>{{ r.blurb }}</p>
          </article>
        </div>
      </div>
    </section>

    <!-- 流程 -->
    <section class="section">
      <div class="section-inner">
        <h2 class="section-title">使用流程</h2>
        <div class="flow">
          <div v-for="(step, i) in steps" :key="step.t" class="flow-step">
            <span class="flow-num">{{ i + 1 }}</span>
            <h4>{{ step.t }}</h4>
            <p>{{ step.d }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 底部 CTA -->
    <section class="cta-block">
      <div class="cta-inner">
        <h2>准备好升级你的测试交付了吗？</h2>
        <p>登录后使用工作台、项目看板与执行历史；管理员与 TSE 可访问运行监控与后台配置。</p>
        <div class="hero-cta">
          <router-link v-if="!auth.token" to="/register" class="btn btn-xl btn-solid">创建账号</router-link>
          <router-link v-else to="/" class="btn btn-xl btn-solid">返回工作台</router-link>
          <router-link to="/login" class="btn btn-xl btn-outline-muted">登录</router-link>
        </div>
      </div>
    </section>

    <footer class="intro-foot">
      <p>鸿蒙生态智能测试平台 · 页面结构参考业界智能测试代理类产品站点的常见叙事逻辑。</p>
    </footer>
  </div>
</template>

<script setup>
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

const stats = [
  { value: "4+", label: "数字机器人品类" },
  { value: "全链路", label: "用例 · 执行 · 日志" },
  { value: "多租户", label: "项目空间隔离" },
  { value: "可观测", label: "监控与数据看板" },
];

const features = [
  {
    tone: "blue",
    icon: "◇",
    title: "项目空间与用例管理",
    body: "按被测应用与测试目标划分空间；支持用例维护、版本快照、导入与知识库检索入口。",
  },
  {
    tone: "cyan",
    icon: "▸",
    title: "自动化执行与日志",
    body: "基于执行记录的 step_log 持久化；支持排队、运行中、成功/失败状态与识别步数统计。",
  },
  {
    tone: "amber",
    icon: "◎",
    title: "机器人商城与计费",
    body: "四类数字人分时/按次计费；预订单对接支付流程，便于租户按需启用能力。",
  },
  {
    tone: "green",
    icon: "⌁",
    title: "看板与运行监控",
    body: "工作台总览、项目看板、数据看板与数字机器人运行态势（权限分级可见）。",
  },
  {
    tone: "violet",
    icon: "◈",
    title: "功能测试任务编排",
    body: "项目内功能测试任务向导，与设备与下发通道衔接（按项目模块可用功能）。",
  },
  {
    tone: "slate",
    icon: "■",
    title: "角色与权限",
    body: "平台管理员、TSE、企业租户分层；运行监控与后台管理按角色开放。",
  },
];

const robots = [
  {
    id: "test_analysis",
    category: "测试分析",
    name: "测试分析数字机器人",
    blurb: "覆盖缺口识别、执行日志聚类与策略摘要，与项目看板联动。",
  },
  {
    id: "functional_execution",
    category: "功能执行",
    name: "功能执行数字机器人",
    blurb: "自然语言用例驱动端侧执行，日志与平台执行记录打通。",
  },
  {
    id: "specialized_execution",
    category: "专项执行",
    name: "专项执行数字机器人",
    blurb: "兼容、弱网、权限等专项编排，面向里程碑与抽检场景。",
  },
  {
    id: "quality_assessment",
    category: "质量评估",
    name: "质量评估数字机器人",
    blurb: "量化评分、趋势与发布风险提示，服务版本门禁与管理层摘要。",
  },
];

const steps = [
  { t: "创建项目空间", d: "绑定被测应用与测试目标，作为用例与报告的容器。" },
  { t: "维护用例并编排", d: "编写或导入用例；在商城选用数字机器人能力。" },
  { t: "执行与观测", d: "触发自动化运行，查看日志、项目看板与（授权下）运行监控。" },
  { t: "评估与迭代", d: "结合数据看板与质量评估机器人输出，持续改进交付。" },
];
</script>

<style scoped>
.intro {
  --intro-bg: #f2f5fb;
  --intro-bg-soft: #eef2f9;
  min-height: 100vh;
  background: var(--intro-bg);
  color: #0f172a;
}

.intro .btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  border: 1px solid transparent;
  font-weight: 600;
  transition:
    background 0.15s,
    color 0.15s,
    border-color 0.15s,
    filter 0.15s;
}

.hero {
  position: relative;
  padding: 3rem 1.25rem 4rem;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 75% 55% at 50% -5%, rgba(59, 130, 246, 0.14), transparent 58%),
    radial-gradient(ellipse 45% 35% at 95% 25%, rgba(56, 189, 248, 0.08), transparent),
    linear-gradient(180deg, var(--intro-bg-soft) 0%, var(--intro-bg) 72%);
}

.hero-inner {
  position: relative;
  max-width: 920px;
  margin: 0 auto;
  text-align: center;
}

.hero-kicker {
  margin: 0 0 1rem;
  font-size: 0.8rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #2563eb;
  font-weight: 600;
}

.hero-title {
  margin: 0 0 1rem;
  font-size: clamp(1.75rem, 4.5vw, 2.65rem);
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.03em;
  color: #0f172a;
}

.hero-accent {
  background: linear-gradient(90deg, #2563eb, #0891b2, #6366f1);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.hero-lead {
  margin: 0 auto 2rem;
  max-width: 640px;
  font-size: 1.02rem;
  line-height: 1.75;
  color: #475569;
}

.hero-lead strong {
  color: #0f172a;
  font-weight: 600;
}

.hero-cta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
}

.btn-xl {
  padding: 0.75rem 1.5rem;
  font-size: 0.95rem;
}

.btn-solid {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  color: #fff;
  border: none;
  box-shadow: 0 8px 28px rgba(37, 99, 235, 0.35);
}

.btn-solid:hover {
  filter: brightness(1.06);
}

.btn-outline-muted {
  background: rgba(255, 255, 255, 0.72);
  color: #334155;
  border: 1px solid #cbd5e1;
  box-shadow: 0 1px 0 rgb(255 255 255 / 0.9) inset;
}

.btn-outline-muted:hover {
  background: #fff;
  border-color: #94a3b8;
}

.strip {
  background: var(--intro-bg);
  border-top: 1px solid #e2e8f0;
  border-bottom: 1px solid #e2e8f0;
}

.strip-inner {
  max-width: 1000px;
  margin: 0 auto;
  padding: 1.5rem 1.25rem;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 1rem;
  text-align: center;
}

.strip-item strong {
  display: block;
  font-size: 1.35rem;
  font-weight: 800;
  color: #1d4ed8;
  margin-bottom: 0.25rem;
}

.strip-item span {
  font-size: 0.82rem;
  color: #64748b;
}

.section {
  padding: 3.5rem 1.25rem;
}

/* 与根容器同一浅底色，避免块状跳色 */

.section-inner {
  max-width: 1040px;
  margin: 0 auto;
}

.section-title {
  margin: 0 0 0.65rem;
  font-size: clamp(1.35rem, 2.8vw, 1.75rem);
  font-weight: 800;
  text-align: center;
  letter-spacing: -0.02em;
}

.section-desc {
  margin: 0 auto 2rem;
  max-width: 640px;
  text-align: center;
  font-size: 0.98rem;
  color: #64748b;
  line-height: 1.65;
}

.feat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 1.25rem;
}

.feat-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1.35rem 1.25rem;
  box-shadow: 0 4px 18px rgb(15 23 42 / 4%);
}

.feat-card h3 {
  margin: 0.65rem 0 0.45rem;
  font-size: 1.05rem;
  font-weight: 700;
}

.feat-card p {
  margin: 0;
  font-size: 0.9rem;
  color: #475569;
  line-height: 1.55;
}

.feat-icon {
  width: 2.75rem;
  height: 2.75rem;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  font-weight: 700;
}

.feat-icon.blue {
  background: #eff6ff;
  color: #2563eb;
}

.feat-icon.cyan {
  background: #ecfeff;
  color: #0891b2;
}

.feat-icon.amber {
  background: #fffbeb;
  color: #d97706;
}

.feat-icon.green {
  background: #ecfdf5;
  color: #059669;
}

.feat-icon.violet {
  background: #f5f3ff;
  color: #7c3aed;
}

.feat-icon.slate {
  background: #f8fafc;
  color: #475569;
}

.robot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
}

.robot-tile {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 1.25rem;
}

.robot-cat {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2563eb;
}

.robot-tile h3 {
  margin: 0.5rem 0 0.45rem;
  font-size: 1.02rem;
  font-weight: 700;
}

.robot-tile p {
  margin: 0;
  font-size: 0.88rem;
  color: #64748b;
  line-height: 1.55;
}

.flow {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.25rem;
}

.flow-step {
  position: relative;
  padding: 1.25rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}

.flow-num {
  display: inline-flex;
  width: 2rem;
  height: 2rem;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: linear-gradient(145deg, #3b82f6, #1d4ed8);
  color: #fff;
  font-weight: 800;
  font-size: 0.9rem;
  margin-bottom: 0.65rem;
}

.flow-step h4 {
  margin: 0 0 0.35rem;
  font-size: 1rem;
}

.flow-step p {
  margin: 0;
  font-size: 0.88rem;
  color: #64748b;
  line-height: 1.5;
}

.cta-block {
  padding: 3.5rem 1.25rem;
  background: linear-gradient(180deg, var(--intro-bg-soft) 0%, var(--intro-bg) 100%);
  color: #0f172a;
  border-top: 1px solid #e2e8f0;
}

.cta-inner {
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
}

.cta-inner h2 {
  margin: 0 0 0.75rem;
  font-size: clamp(1.35rem, 3vw, 1.85rem);
  font-weight: 800;
}

.cta-inner > p {
  margin: 0 0 1.75rem;
  color: #475569;
  font-size: 1rem;
  line-height: 1.65;
}

.intro-foot {
  padding: 1.5rem 1.25rem 2.5rem;
  text-align: center;
  font-size: 0.78rem;
  color: #64748b;
  background: var(--intro-bg);
  border-top: 1px solid #e8ecf3;
}

.intro-foot p {
  margin: 0;
  max-width: 560px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.55;
}
</style>

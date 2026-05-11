<template>
  <div class="mascot-wrap" :class="{ 'mascot-wrap--inline': inline }">
    <img
      class="mascot-img"
      src="/images/digital-robot-mascot.png"
      :alt="altText"
      width="400"
      height="400"
      loading="lazy"
      decoding="async"
    />
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  robotId: {
    type: String,
    required: true,
  },
  /** 卡片角标等场景：小尺寸，不占整行 */
  inline: {
    type: Boolean,
    default: false,
  },
});

const altText = computed(() => {
  const m = {
    test_analysis: "测试分析数字机器人形象",
    functional_execution: "功能执行数字机器人形象",
    specialized_execution: "专项执行数字机器人形象",
    quality_assessment: "质量评估数字机器人形象",
  };
  return m[props.robotId] || "数字机器人形象";
});
</script>

<style scoped>
.mascot-wrap {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgb(226 232 240 / 95%);
  background: linear-gradient(185deg, #ffffff 0%, #f0f7ff 48%, #eef2f7 100%);
  box-shadow: 0 6px 22px rgb(15 23 42 / 6%);
}

.mascot-img {
  display: block;
  width: 100%;
  max-height: 168px;
  height: auto;
  object-fit: contain;
  object-position: center center;
}

.mascot-wrap--inline {
  width: 4.5rem;
  height: 4.5rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 10px rgb(15 23 42 / 7%);
}

.mascot-wrap--inline .mascot-img {
  width: 100%;
  max-height: none;
  height: 100%;
  object-fit: contain;
  object-position: center center;
}
</style>

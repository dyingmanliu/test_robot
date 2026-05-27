<template>
  <div ref="rootRef" class="app-search-select" :class="{ open, disabled }">
    <input
      ref="inputRef"
      type="text"
      class="app-search-input"
      :value="inputText"
      :placeholder="placeholder"
      :disabled="disabled"
      autocomplete="off"
      role="combobox"
      :aria-expanded="open"
      aria-autocomplete="list"
      @focus="onFocus"
      @blur="onBlur"
      @input="onInput"
      @keydown="onKeydown"
    />
    <ul v-if="open && !disabled" class="app-search-dropdown" role="listbox">
      <li
        v-if="!filteredOptions.length"
        class="app-search-option empty"
        role="option"
        aria-disabled="true"
      >
        无匹配应用
      </li>
      <li
        v-for="(opt, idx) in filteredOptions"
        :key="opt.value"
        class="app-search-option"
        :class="{ active: idx === highlightIndex }"
        role="option"
        :aria-selected="opt.value === modelValue"
        @mousedown.prevent="pick(opt)"
      >
        <span class="opt-label">{{ opt.label }}</span>
        <span v-if="opt.value !== opt.label" class="opt-id muted">{{ opt.value }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { fuzzyMatch } from "@/utils/fuzzyMatch";

const props = defineProps({
  modelValue: { type: String, default: "" },
  options: { type: Array, default: () => [] },
  extraOption: { type: Object, default: null },
  placeholder: { type: String, default: "输入应用名或包名搜索…" },
  disabled: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue"]);

const rootRef = ref(null);
const inputRef = ref(null);
const open = ref(false);
const inputText = ref("");
const highlightIndex = ref(0);

const allOptions = computed(() => {
  const list = [...(props.options || [])];
  if (props.extraOption?.value) {
    list.unshift(props.extraOption);
  }
  return list;
});

const filteredOptions = computed(() => {
  const q = inputText.value.trim();
  if (!q) return allOptions.value;
  return allOptions.value.filter((o) => fuzzyMatch(q, `${o.label} ${o.value}`));
});

const selectedLabel = computed(() => {
  const hit = allOptions.value.find((o) => o.value === props.modelValue);
  return hit?.label || props.modelValue || "";
});

watch(
  () => props.modelValue,
  () => {
    if (!open.value) {
      inputText.value = selectedLabel.value;
    }
  },
  { immediate: true },
);

watch(
  () => [props.options, props.extraOption],
  () => {
    if (!open.value) {
      inputText.value = selectedLabel.value;
    }
    highlightIndex.value = 0;
  },
);

watch(filteredOptions, () => {
  highlightIndex.value = 0;
});

function onFocus() {
  if (props.disabled) return;
  open.value = true;
  inputText.value = "";
  highlightIndex.value = 0;
}

function onInput(e) {
  inputText.value = e.target.value;
  open.value = true;
  if (!inputText.value.trim()) {
    emit("update:modelValue", "");
  }
}

function onBlur() {
  window.setTimeout(() => {
    open.value = false;
    inputText.value = selectedLabel.value;
  }, 150);
}

function pick(opt) {
  emit("update:modelValue", opt.value);
  inputText.value = opt.label;
  open.value = false;
}

function onKeydown(e) {
  if (!open.value) {
    if (e.key === "ArrowDown" || e.key === "Enter") {
      open.value = true;
      e.preventDefault();
    }
    return;
  }
  const n = filteredOptions.value.length;
  if (e.key === "ArrowDown") {
    e.preventDefault();
    if (n) highlightIndex.value = (highlightIndex.value + 1) % n;
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    if (n) highlightIndex.value = (highlightIndex.value - 1 + n) % n;
  } else if (e.key === "Enter") {
    e.preventDefault();
    const opt = filteredOptions.value[highlightIndex.value];
    if (opt && !opt.empty) pick(opt);
  } else if (e.key === "Escape") {
    open.value = false;
    inputText.value = selectedLabel.value;
    inputRef.value?.blur();
  }
}
</script>

<style scoped>
.app-search-select {
  position: relative;
  width: 100%;
}
.app-search-input {
  width: 100%;
  padding: 0.45rem 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.88rem;
  background: #fff;
  box-sizing: border-box;
}
.app-search-select.open .app-search-input {
  border-color: #93c5fd;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}
.app-search-select.disabled .app-search-input {
  background: #f1f5f9;
  cursor: not-allowed;
}
.app-search-dropdown {
  position: absolute;
  z-index: 40;
  left: 0;
  right: 0;
  margin: 0.25rem 0 0;
  padding: 0.25rem 0;
  max-height: 16rem;
  overflow-y: auto;
  list-style: none;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
}
.app-search-option {
  padding: 0.45rem 0.65rem;
  font-size: 0.86rem;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}
.app-search-option:hover,
.app-search-option.active {
  background: #eff6ff;
}
.app-search-option.empty {
  color: #64748b;
  cursor: default;
}
.opt-label {
  color: #0f172a;
  word-break: break-all;
}
.opt-id {
  font-size: 0.78rem;
  word-break: break-all;
}
.muted {
  color: #64748b;
}
</style>

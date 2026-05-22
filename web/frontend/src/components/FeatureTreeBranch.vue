<template>
  <li class="tree-node">
    <div class="tree-row">
      <button
        v-if="hasChildren"
        type="button"
        class="tree-caret-btn"
        :aria-expanded="!isCollapsed"
        :aria-label="isCollapsed ? '展开' : '折叠'"
        @click.stop="onToggleCollapse"
      >
        <span class="tree-caret-icon" :class="{ collapsed: isCollapsed }" aria-hidden="true" />
      </button>
      <span v-else class="tree-caret-spacer" aria-hidden="true" />
      <button
        type="button"
        class="tree-btn"
        :class="[`type-${node.node_type}`, { selected: selectedId === node.id }]"
        :style="{ paddingLeft: `${0.35 + depth * 1.1}rem` }"
        @click="$emit('select', node)"
      >
        <span class="tree-icon" :class="`icon-${node.node_type}`" aria-hidden="true">
          <svg v-if="node.node_type === 'application'" viewBox="0 0 16 16" fill="none">
            <rect x="3" y="1.5" width="10" height="13" rx="2" stroke="currentColor" stroke-width="1.2" />
            <circle cx="8" cy="12" r="0.9" fill="currentColor" />
          </svg>
          <svg v-else viewBox="0 0 16 16" fill="none">
            <rect x="3.5" y="3.5" width="9" height="9" rx="2" stroke="currentColor" stroke-width="1.2" />
            <path d="M6 8h4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
          </svg>
        </span>
        <span class="tree-name">{{ node.name }}</span>
        <span
          v-if="node.node_type !== 'application' && node.function_type"
          class="tree-tag"
        >
          {{ node.function_type }}
        </span>
      </button>
    </div>
    <ul v-if="hasChildren && !isCollapsed" class="tree-children">
      <FeatureTreeBranch
        v-for="ch in node.children"
        :key="ch.id"
        :node="ch"
        :selected-id="selectedId"
        :collapsed-ids="collapsedIds"
        :depth="depth + 1"
        @select="$emit('select', $event)"
        @toggle-collapse="$emit('toggle-collapse', $event)"
      />
    </ul>
  </li>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  node: { type: Object, required: true },
  selectedId: { type: String, default: "" },
  /** Set<string>：折叠的节点 id */
  collapsedIds: { type: Object, default: () => new Set() },
  depth: { type: Number, default: 0 },
});
const emit = defineEmits(["select", "toggle-collapse"]);

const hasChildren = computed(() => (props.node.children || []).length > 0);
const isCollapsed = computed(() => {
  const id = props.node?.id;
  return Boolean(id && props.collapsedIds?.has?.(id));
});

function onToggleCollapse() {
  if (props.node?.id) emit("toggle-collapse", props.node.id);
}
</script>

<style scoped>
.tree-row {
  display: flex;
  align-items: stretch;
  gap: 0.15rem;
}
.tree-caret-btn {
  flex-shrink: 0;
  width: 1.1rem;
  height: 1.1rem;
  margin: 0.28rem 0 0 0.2rem;
  padding: 0;
  border: none;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tree-caret-btn:hover {
  background: #f1f5f9;
}
.tree-caret-icon {
  width: 0;
  height: 0;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-left: 6px solid #64748b;
  transition: transform 0.15s ease;
}
.tree-caret-icon:not(.collapsed) {
  transform: rotate(90deg);
}
.tree-caret-btn:hover .tree-caret-icon {
  border-left-color: #334155;
}
.tree-caret-spacer {
  flex-shrink: 0;
  width: 1.1rem;
  margin-left: 0.2rem;
}
.tree-children {
  list-style: none;
  margin: 0;
  padding: 0;
  border-left: 1px solid #e2e8f0;
  margin-left: 0.85rem;
}
.tree-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex: 1;
  min-width: 0;
  text-align: left;
  border: none;
  background: transparent;
  padding: 0.38rem 0.5rem 0.38rem 0;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: #1e293b;
  line-height: 1.35;
  transition: background 0.12s ease;
}
.tree-btn:hover {
  background: #f1f5f9;
}
.tree-btn.selected {
  background: #dbeafe;
  color: #1d4ed8;
  box-shadow: inset 0 0 0 1px #93c5fd;
}
.tree-btn.type-application .tree-name {
  font-weight: 600;
}
.tree-btn.type-function .tree-name,
.tree-btn.type-module .tree-name,
.tree-btn.type-screen .tree-name {
  font-weight: 500;
}
.tree-icon {
  flex-shrink: 0;
  width: 1rem;
  height: 1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.tree-icon svg {
  width: 100%;
  height: 100%;
}
.icon-application {
  color: #2563eb;
}
.icon-screen {
  color: #7c3aed;
}
.icon-function,
.icon-module,
.icon-screen {
  color: #059669;
}
.tree-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-tag {
  flex-shrink: 0;
  font-size: 0.7rem;
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
  max-width: 5.5rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tree-btn.selected .tree-tag {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1e40af;
}
</style>

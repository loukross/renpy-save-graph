<template>
  <div v-if="isOpen" class="modal-overlay picker-overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <span>Select folder</span>
        <button @click="$emit('close')">×</button>
      </div>
      <div class="modal-body">
        <div v-if="loading && !flatRows.length" class="tree-row"><span class="tree-toggle">⋯</span>Loading…</div>
        <div
          v-for="row in flatRows"
          :key="row.node.path"
          class="tree-row"
          :class="{ selected: selected === row.node.path }"
          :style="{ paddingLeft: (8 + row.depth * 18) + 'px' }"
          @click="$emit('select', row.node.path)"
        >
          <span class="tree-toggle" @click.stop="$emit('toggle', row.node)">
            <template v-if="row.node.loading">⋯</template>
            <template v-else-if="row.node.expanded">▼</template>
            <template v-else>▶</template>
          </span>
          {{ row.node.name }}
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-primary" :disabled="!selected" @click="$emit('confirm', selected)">
          {{ confirmLabel || 'Select folder' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  nodes: Array,
  selected: String,
  loading: Boolean,
  confirmLabel: String,
});

defineEmits(['close', 'select', 'toggle', 'confirm']);

const flatRows = computed(() => {
  const result = [];
  const walk = (nodes, depth) => {
    for (const n of (nodes || [])) {
      result.push({ node: n, depth });
      if (n.expanded && n.children) walk(n.children, depth + 1);
    }
  };
  walk(props.nodes, 0);
  return result;
});
</script>

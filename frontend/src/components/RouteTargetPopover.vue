<template>
  <div v-if="isOpen" class="route-target-popover-box" @click.stop>
    <div class="popover-header">
      <span>🎯 Route Targets</span>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>
    <div class="popover-body">
      <div v-if="routeTargets && routeTargets.length" class="button-grid">
        <button
          v-for="rt in routeTargets"
          :key="rt.name"
          class="popover-option-btn"
          :class="{ active: isSelected(rt.name) }"
          :title="rt.expr"
          @click="$emit('toggle', rt.name)"
        >
          {{ rt.name }}
        </button>
      </div>
      <div v-else class="empty-hint">No route targets configured</div>
    </div>
    <div class="popover-footer">
      <button class="btn-secondary btn-reset" @click="$emit('clear')">
        Clear
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
  routeTargets: Array,
  isSelected: Function,
});

defineEmits(['close', 'toggle', 'clear']);
</script>

<style scoped>
.route-target-popover-box {
  position: absolute;
  bottom: calc(100% + 6px);
  right: 0;
  width: 280px;
  max-height: 400px;
  background: var(--bg2);
  border: 1px solid var(--accent);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.popover-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 13px;
  color: var(--accent2);
}
.close-btn {
  background: none;
  border: none;
  color: var(--text-dim);
  font-size: 16px;
  cursor: pointer;
  padding: 0 4px;
}
.close-btn:hover { color: var(--text); }
.popover-body {
  padding: 12px;
  overflow-y: auto;
  flex: 1;
}
.button-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.popover-option-btn {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
  transition: all 0.15s ease;
}
.popover-option-btn:hover {
  border-color: var(--accent);
}
.popover-option-btn.active {
  background: #1a2450;
  border-color: var(--accent2);
  color: var(--accent2);
  font-weight: 600;
}
.empty-hint {
  font-size: 12px;
  color: var(--text-dim);
  font-style: italic;
}
.popover-footer {
  padding: 8px 12px;
  border-top: 1px solid var(--border);
  background: var(--bg3);
  display: flex;
  justify-content: flex-end;
}
.btn-reset {
  font-size: 12px;
  padding: 4px 10px;
}
</style>

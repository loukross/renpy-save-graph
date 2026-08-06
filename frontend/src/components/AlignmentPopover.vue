<template>
  <div v-if="isOpen" class="alignment-popover-box" @click.stop>
    <div class="popover-header">
      <span>📐 Horizontal Alignment Options</span>
      <button class="close-btn" @click="$emit('close')">×</button>
    </div>
    <div class="popover-body">
      <div class="section-title">Tags</div>
      <div v-if="allTags && allTags.length" class="button-grid">
        <button
          v-for="t in allTags"
          :key="'tag-' + t"
          class="popover-option-btn tag-btn"
          :class="{ active: isSelected('#' + t) }"
          @click="$emit('toggle', '#' + t)"
        >
          #{{ t }}
        </button>
      </div>
      <div v-else class="empty-hint">No tags created yet</div>

      <div class="section-title" style="margin-top:12px">Story Variables</div>
      <div v-if="milestoneVars && milestoneVars.length" class="button-grid">
        <button
          v-for="v in milestoneVars"
          :key="'var-' + v"
          class="popover-option-btn var-btn"
          :class="{ active: isSelected(v) }"
          @click="$emit('toggle', v)"
        >
          {{ v }}
        </button>
      </div>
      <div v-else class="empty-hint">No milestone variables configured</div>
    </div>
    <div class="popover-footer">
      <button class="btn-secondary btn-reset" @click="$emit('clear')">
        Natural Depth (Reset)
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
  allTags: Array,
  milestoneVars: Array,
  isSelected: Function,
});

defineEmits(['close', 'toggle', 'clear']);
</script>

<style scoped>
.alignment-popover-box {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  width: 320px;
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
.section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: var(--text-dim);
  margin-bottom: 6px;
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

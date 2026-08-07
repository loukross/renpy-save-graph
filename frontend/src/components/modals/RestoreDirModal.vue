<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto;max-height:90vh;width:540px">
      <div class="modal-header">
        <span>📁 Set Save Directory</span>
        <button @click="$emit('close')">✕</button>
      </div>
      <div style="padding:16px;font-size:14px;color:var(--text)">
        <p style="margin-bottom:12px;line-height:1.4">
          Changing the save directory for this node will set it for this node <em>and</em> all child nodes.
        </p>
        <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:16px">
          <label
            v-for="(dir, idx) in savesDirs"
            :key="dir"
            style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg3);border:1px solid var(--border);border-radius:6px;cursor:pointer"
            :style="selectedDir === dir ? 'border-color:var(--accent);background:var(--bg2)' : ''"
          >
            <input
              type="radio"
              name="restoreTargetDir"
              :value="dir"
              v-model="selectedDir"
              style="width:auto"
            />
            <div style="flex:1;overflow:hidden">
              <div style="font-weight:600;font-size:13px;word-break:break-all">
                {{ dir }}
              </div>
              <div style="font-size:11px;color:var(--text-dim)">
                {{ idx === 0 ? 'Primary save directory' : `Additional save directory #${idx}` }}
              </div>
            </div>
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-primary" :disabled="!selectedDir" @click="$emit('confirm', selectedDir)">
          Set Save Directory
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  savesDirs: {
    type: Array,
    default: () => [],
  },
  currentDir: String,
});

const emit = defineEmits(['close', 'confirm']);

const selectedDir = ref('');

watch(
  () => [props.isOpen, props.currentDir, props.savesDirs],
  () => {
    if (props.isOpen) {
      if (props.currentDir && props.savesDirs.includes(props.currentDir)) {
        selectedDir.value = props.currentDir;
      } else if (props.savesDirs && props.savesDirs.length) {
        selectedDir.value = props.savesDirs[0];
      }
    }
  },
  { immediate: true }
);
</script>

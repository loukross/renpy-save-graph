<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto">
      <div class="modal-header">
        <span>Remove space</span>
        <button @click="$emit('close')">×</button>
      </div>
      <div style="padding:16px 20px">
        <div style="margin-bottom:14px">
          Remove <strong style="color:var(--text)">{{ space?.label || space?.id }}</strong>?
        </div>
        <label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;color:var(--text-dim)">
          <input type="checkbox" v-model="deleteLibrary" style="width:auto" />
          Permanently delete the git library
        </label>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-danger" @click="$emit('confirm', deleteLibrary)">Remove</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  space: Object,
});

defineEmits(['close', 'confirm']);

const deleteLibrary = ref(false);

watch(() => props.isOpen, (open) => {
  if (open) deleteLibrary.value = false;
});
</script>

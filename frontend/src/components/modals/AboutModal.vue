<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto;max-height:90vh;width:440px;border-radius:12px;padding:20px">
      <div class="modal-header" style="border:none;padding:0 0 12px 0">
        <span>About Ren'Py Save Graph</span>
        <button @click="$emit('close')">×</button>
      </div>
      <div style="font-size:13px;color:var(--text);line-height:1.6">
        <p style="margin-bottom:12px">
          A visual novel flowchart viewer and save game tracker for Ren'Py visual novels.
        </p>
        <p style="color:var(--text-dim);font-size:12px">
          Version 0.1.0 • Built with Vue 3, D3.js, and FastAPI.
        </p>
      </div>
      <div class="modal-footer" style="border:none;padding:16px 0 0 0">
        <button class="btn-secondary" @click="$emit('close')">Close</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
});

defineEmits(['close']);
</script>

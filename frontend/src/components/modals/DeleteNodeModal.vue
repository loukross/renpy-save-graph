<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto;max-height:90vh;width:440px;border-radius:12px;padding:20px">
      <div class="modal-header" style="border:none;padding:0 0 12px 0;color:var(--red-val)">
        <span>Delete Save Node</span>
        <button @click="$emit('close')">×</button>
      </div>
      <div style="font-size:13px;color:var(--text);line-height:1.6">
        <p style="margin-bottom:12px">
          Are you sure you want to delete node <strong>{{ node ? node.sha.slice(0, 7) : '' }}</strong>?
        </p>
        <p style="color:var(--text-dim);font-size:12px">
          Children nodes will be cleanly reparented to maintaining tree continuity.
        </p>
      </div>
      <div class="modal-footer" style="border:none;padding:16px 0 0 0;display:flex;gap:8px;justify-content:flex-end">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-danger" @click="$emit('confirm')">Delete Node</button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
  node: Object,
});

defineEmits(['close', 'confirm']);
</script>

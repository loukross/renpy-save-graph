<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto;max-height:90vh;width:500px;border-radius:12px;padding:24px;text-align:center">
      <div style="font-size:36px;margin-bottom:12px">🎮 📈</div>
      <h2 style="font-size:20px;font-weight:700;color:var(--accent2);margin-bottom:8px">
        Welcome to Ren'Py Save Graph!
      </h2>
      <p style="color:var(--text);font-size:14px;line-height:1.5;margin-bottom:20px">
        Track your choices, explore story branches, inspect save state variables, and jump to decision points cleanly.
      </p>

      <div style="display:flex;flex-direction:column;gap:10px">
        <button class="btn-primary" style="justify-content:center;padding:10px 16px;font-size:14px;font-weight:600" @click="$emit('start-tour')">
          🚀 Start Interactive Tour
        </button>
        <button class="btn-secondary" style="justify-content:center;padding:8px 16px;font-size:13px" @click="$emit('close')">
          Skip for now
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
});

defineEmits(['close', 'start-tour']);
</script>

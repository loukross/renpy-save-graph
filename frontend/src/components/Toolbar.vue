<template>
  <div id="graph-toolbar">
    <select
      id="slot-select"
      v-if="availableSlots && availableSlots.length"
      :value="selectedSlot"
      @change="$emit('update:selectedSlot', $event.target.value)"
    >
      <option v-for="s in availableSlots" :key="s" :value="s">{{ s }}</option>
    </select>

    <button class="btn-secondary" :disabled="loading" @click="$emit('refresh')">↺ Refresh</button>
    <button class="btn-secondary" :disabled="loading" @click="$emit('ingest')">⬇ Ingest</button>

    <span v-if="loading" class="loading">Loading…</span>
    <span v-else-if="watching" id="watching-indicator" style="font-size:13px;color:var(--green)">● Watching</span>

    <div style="position:relative;display:inline-block" ref="jumpMenuRoot">
      <button class="btn-secondary" @click.stop="jumpMenuOpen = !jumpMenuOpen">🎯 Jump to…</button>
      <div
        v-if="jumpMenuOpen"
        @click.stop
        style="position:absolute;top:100%;left:0;margin-top:6px;z-index:250;width:300px;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:10px;box-shadow:0 8px 24px rgba(0,0,0,0.6)"
      >
        <div style="display:flex;flex-direction:column;gap:6px">
          <button class="btn-secondary" style="justify-content:flex-start;font-size:13px;padding:6px 10px" @click="onJumpHead">📍 Current Head (Active Save)</button>
          <button class="btn-secondary" style="justify-content:flex-start;font-size:13px;padding:6px 10px" @click="onJumpRoot">🌱 Root (Beginning)</button>
          <div style="border-top:1px solid var(--border);margin:4px 0"></div>
          <label style="font-size:13px;font-weight:600;color:var(--text-dim)">📅 Jump to Date Range</label>
          <div style="display:flex;gap:4px">
            <button class="btn-secondary" style="font-size:12px;padding:2px 8px" @click="onDatePreset('today')">Today</button>
            <button class="btn-secondary" style="font-size:12px;padding:2px 8px" @click="onDatePreset('3days')">3 Days</button>
            <button class="btn-secondary" style="font-size:12px;padding:2px 8px" @click="onDatePreset('7days')">7 Days</button>
          </div>
          <div style="display:flex;gap:6px;align-items:center;margin-top:4px">
            <input type="date" v-model="jumpDateFrom" style="font-size:13px;padding:3px 6px;flex:1" />
            <span style="font-size:13px;color:var(--text-dim)">to</span>
            <input type="date" v-model="jumpDateTo" style="font-size:13px;padding:3px 6px;flex:1" />
          </div>
          <button class="btn-primary" style="margin-top:6px;justify-content:center;font-size:13px" @click="onApplyDateJump">Jump to Range</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';

defineProps({
  availableSlots: Array,
  selectedSlot: String,
  loading: Boolean,
  watching: Boolean,
});

const emit = defineEmits([
  'update:selectedSlot',
  'refresh',
  'ingest',
  'jump-head',
  'jump-root',
  'jump-range',
]);

const jumpMenuOpen = ref(false);
const jumpMenuRoot = ref(null);
const jumpDateFrom = ref('');
const jumpDateTo = ref('');

function onDocumentClick(e) {
  if (jumpMenuRoot.value && !jumpMenuRoot.value.contains(e.target)) {
    jumpMenuOpen.value = false;
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick));
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick));

function onJumpHead() {
  jumpMenuOpen.value = false;
  emit('jump-head');
}

function onJumpRoot() {
  jumpMenuOpen.value = false;
  emit('jump-root');
}

function onDatePreset(preset) {
  const now = new Date();
  let fromDate = new Date();
  if (preset === 'today') {
    fromDate.setHours(0, 0, 0, 0);
  } else if (preset === '3days') {
    fromDate.setDate(now.getDate() - 3);
  } else if (preset === '7days') {
    fromDate.setDate(now.getDate() - 7);
  }
  jumpDateFrom.value = fromDate.toISOString().slice(0, 10);
  jumpDateTo.value = now.toISOString().slice(0, 10);
  onApplyDateJump();
}

function onApplyDateJump() {
  jumpMenuOpen.value = false;
  emit('jump-range', { from: jumpDateFrom.value, to: jumpDateTo.value });
}
</script>

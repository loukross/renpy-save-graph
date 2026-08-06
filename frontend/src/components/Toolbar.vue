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

    <div style="position:relative">
      <button
        id="btn-alignment-popover"
        class="btn-secondary"
        style="font-size:12px;padding:3px 8px;width:175px;text-align:left;display:inline-flex;justify-content:space-between;align-items:center"
        @click.stop="$emit('toggle-popover')"
      >
        <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
          📐 Align: {{ alignmentButtonLabel }}
        </span>
        <span style="font-size:9px">▼</span>
      </button>

      <AlignmentPopover
        :is-open="showAlignmentPopover"
        :all-tags="allTags"
        :milestone-vars="milestoneVars"
        :is-selected="isAlignmentSelected"
        @close="$emit('close-popover')"
        @toggle="$emit('toggle-alignment', $event)"
        @clear="$emit('clear-alignments')"
      />
    </div>

    <!-- Base Sort Direction Button -->
    <button
      class="btn-secondary"
      style="font-size:12px;padding:3px 8px"
      :title="sortDir === 'desc' ? 'Base sort: Chronological (oldest at top)' : 'Base sort: Reverse (newest at top)'"
      @click="$emit('update:sortDir', sortDir === 'desc' ? 'asc' : 'desc')"
    >
      Base sort: {{ sortDir === 'desc' ? '↓' : '↑' }}
    </button>

    <!-- Filter input -->
    <input
      :value="filterExpr"
      @input="$emit('update:filterExpr', $event.target.value)"
      placeholder="Filter (e.g. gold >= 100)"
      style="width:160px;font-size:12px;padding:3px 8px"
    />

    <!-- Date Jump Dropdown -->
    <select
      v-if="datesList && datesList.length"
      style="width:auto;font-size:12px;padding:3px 8px"
      @change="$emit('jump-to-date', $event.target.value)"
    >
      <option value="">Jump to date…</option>
      <option v-for="d in datesList" :key="d" :value="d">{{ d }}</option>
    </select>

    <span v-if="loading" class="loading">Loading…</span>
  </div>
</template>

<script setup>
import AlignmentPopover from './AlignmentPopover.vue';

defineProps({
  availableSlots: Array,
  selectedSlot: String,
  showAlignmentPopover: Boolean,
  alignmentButtonLabel: String,
  allTags: Array,
  milestoneVars: Array,
  isAlignmentSelected: Function,
  sortDir: String,
  filterExpr: String,
  datesList: Array,
  loading: Boolean,
});

defineEmits([
  'update:selectedSlot',
  'toggle-popover',
  'close-popover',
  'toggle-alignment',
  'clear-alignments',
  'update:sortDir',
  'update:filterExpr',
  'jump-to-date',
]);
</script>

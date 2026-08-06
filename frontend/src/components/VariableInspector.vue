<template>
  <div id="bottom-panel">
    <div id="bottom-resizer" ref="resizerRef"></div>
    <div id="bottom-pulltab">
      <button class="bp-toggle" @click="$emit('update:isOpen', !isOpen)">{{ isOpen ? '▼' : '▲' }}</button>
      <span style="font-size:12px;color:var(--text-dim);font-weight:600">Inspector</span>
    </div>
    <div v-show="isOpen" id="bottom-content" ref="contentRef">
      <div style="padding:6px 12px;flex-shrink:0">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <label style="font-size:12px;font-weight:600;color:var(--text-dim)">🔍 Variable Filter Regex</label>
        </div>
        <div style="display:flex;align-items:center;gap:4px">
          <input
            :value="searchQuery"
            @input="$emit('update:searchQuery', $event.target.value)"
            placeholder="e.g. ^karma|money$"
            style="flex:1;padding:3px 8px;font-size:13px;font-family:monospace;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px"
          />
          <button
            class="btn-secondary"
            style="padding:3px 8px;font-size:13px;flex-shrink:0"
            :style="searchQuery === '^[^_]' ? 'border-color:var(--accent)' : ''"
            @click="$emit('update:searchQuery', '^[^_]')"
          >Game vars</button>
        </div>
      </div>
      <div v-if="loading" style="padding:10px;font-size:12px;color:var(--text-dim)">Loading variables…</div>
      <div v-else-if="!stateData || !Object.keys(stateData.variables || {}).length" style="padding:10px;font-size:12px;color:var(--text-dim)">
        No state data recorded for this save point.
      </div>
      <div v-else style="overflow-y:auto;flex:1;padding:0 12px 8px">
        <table class="diff-table">
          <thead>
            <tr>
              <th style="width:20px"></th>
              <th style="width:20px"></th>
              <th style="white-space:nowrap;width:1%">Variable</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[key, val] in sortedRows" :key="key">
              <td style="padding:2px 4px;width:20px;text-align:center">
                <button
                  style="background:none;border:none;cursor:pointer;font-size:16px;padding:0;line-height:1"
                  :style="{ color: isFavorite(key) ? '#ffcc00' : '#445566' }"
                  :title="isFavorite(key) ? 'Remove favorite' : 'Add favorite'"
                  @click="$emit('toggle-favorite', key)"
                >{{ isFavorite(key) ? '★' : '☆' }}</button>
              </td>
              <td style="padding:2px 4px;width:20px;text-align:center">
                <button
                  style="background:none;border:none;cursor:pointer;font-size:16px;font-weight:bold;padding:0;line-height:1;color:#607090"
                  title="Add to filter"
                  @click="$emit('add-to-filter', key, val)"
                >+</button>
              </td>
              <td class="var" style="white-space:nowrap">{{ key }}</td>
              <td class="new">{{ val }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  stateData: Object,
  searchQuery: String,
  favoriteVars: Array,
  loading: Boolean,
});

defineEmits(['update:isOpen', 'update:searchQuery', 'toggle-favorite', 'add-to-filter']);

const resizerRef = ref(null);
const contentRef = ref(null);

const sortedRows = computed(() => {
  if (!props.stateData) return [];
  const favs = new Set(props.favoriteVars || []);
  // The /state/{sha} endpoint returns {"variables": {...actual game vars...}} —
  // unwrap it, matching ui.html's inspectorRows (Object.entries(nodeState.variables)).
  const variables = props.stateData.variables || {};
  const entries = Object.entries(variables).sort((a, b) => {
    const fa = favs.has(a[0]), fb = favs.has(b[0]);
    if (fa !== fb) return fa ? -1 : 1;
    return a[0].localeCompare(b[0]);
  });
  const raw = (props.searchQuery || '').trim();
  if (!raw) return entries;
  const patterns = raw.split(',').map(p => p.trim()).filter(Boolean);
  try {
    const regexes = patterns.map(p => new RegExp(p, 'i'));
    return entries.filter(([k]) => regexes.some(r => r.test(k)));
  } catch {
    return entries;
  }
});

function isFavorite(varName) {
  return props.favoriteVars && props.favoriteVars.includes(varName);
}

let dragging = false, startY = 0, startH = 0;

function onMouseDown(e) {
  dragging = true;
  startY = e.clientY;
  startH = contentRef.value ? contentRef.value.offsetHeight : 170;
  resizerRef.value && resizerRef.value.classList.add('dragging');
  document.body.style.cursor = 'row-resize';
  document.body.style.userSelect = 'none';
  e.preventDefault();
}

function onMouseMove(e) {
  if (!dragging || !contentRef.value) return;
  const h = Math.max(60, startH + (startY - e.clientY));
  contentRef.value.style.height = h + 'px';
}

function onMouseUp() {
  if (!dragging) return;
  dragging = false;
  resizerRef.value && resizerRef.value.classList.remove('dragging');
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
}

onMounted(() => {
  resizerRef.value && resizerRef.value.addEventListener('mousedown', onMouseDown);
  document.addEventListener('mousemove', onMouseMove);
  document.addEventListener('mouseup', onMouseUp);
});

onBeforeUnmount(() => {
  resizerRef.value && resizerRef.value.removeEventListener('mousedown', onMouseDown);
  document.removeEventListener('mousemove', onMouseMove);
  document.removeEventListener('mouseup', onMouseUp);
});
</script>

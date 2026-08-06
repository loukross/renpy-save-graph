<template>
  <div v-if="isOpen" id="bottom-panel">
    <div id="bottom-pulltab">
      <button class="bp-toggle" @click="$emit('close')">▼ Hide Panel</button>
      <span style="font-size:12px;color:var(--text-dim);font-weight:600">State Variable Inspector</span>
      <input
        :value="searchQuery"
        @input="$emit('update:searchQuery', $event.target.value)"
        placeholder="Filter variables…"
        style="width:140px;font-size:11px;padding:2px 6px;margin-left:auto"
      />
    </div>
    <div id="bottom-content">
      <div v-if="loading" style="padding:10px;font-size:12px;color:var(--text-dim)">Loading variables…</div>
      <div v-else-if="!stateData || !Object.keys(stateData).length" style="padding:10px;font-size:12px;color:var(--text-dim)">
        No state data recorded for this save point.
      </div>
      <div v-else style="overflow-y:auto;flex:1;padding:6px 10px">
        <table class="diff-table">
          <thead>
            <tr>
              <th style="width:24px">★</th>
              <th>Variable</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(val, key) in filteredVariables" :key="key">
              <td>
                <button
                  style="background:none;border:none;color:var(--gold);cursor:pointer;font-size:14px;padding:0"
                  @click="$emit('toggle-favorite', key)"
                >
                  {{ isFavorite(key) ? '★' : '☆' }}
                </button>
              </td>
              <td class="var">{{ key }}</td>
              <td class="new">{{ val }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  stateData: Object,
  searchQuery: String,
  favoriteVars: Array,
  loading: Boolean,
});

defineEmits(['close', 'update:searchQuery', 'toggle-favorite']);

const filteredVariables = computed(() => {
  if (!props.stateData) return {};
  const q = (props.searchQuery || '').toLowerCase();
  const res = {};
  for (const [k, v] of Object.entries(props.stateData)) {
    if (!q || k.toLowerCase().includes(q)) {
      res[k] = v;
    }
  }
  return res;
});

function isFavorite(varName) {
  return props.favoriteVars && props.favoriteVars.includes(varName);
}
</script>

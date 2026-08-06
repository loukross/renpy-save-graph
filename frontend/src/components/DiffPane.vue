<template>
  <div id="diff-pane">
    <div id="diff-header">
      <div id="diff-title">
        <template v-if="node">
          {{ node.sha.slice(0, 7) }}
          <span v-if="node.is_head" class="branch-badge">HEAD</span>
          <span v-if="node.is_suspect" class="branch-badge" style="background:#501a1a;border-color:#8a2a2a;color:#f88a8a">Suspect Lineage</span>
        </template>
        <template v-else>Select a save point</template>
      </div>
      <div id="diff-subtitle">{{ node ? node.subject : '' }}</div>
    </div>

    <div v-if="node" id="restore-bar">
      <button v-if="!node.is_head" class="btn-secondary" :disabled="restoring" @click="$emit('restore')">
        {{ restoring ? 'Restoring…' : '← Restore to Game' }}
      </button>
      <button
        class="btn-danger"
        :disabled="node.is_head || !node.parents || !node.parents.length"
        :title="node.is_head ? 'Cannot delete active save point' : ((!node.parents || !node.parents.length) ? 'Cannot delete root node' : 'Delete node')"
        @click="$emit('delete')"
      >🗑 Delete node</button>
    </div>

    <div id="diff-body">
      <div v-if="loading" class="diff-empty">Loading diff…</div>
      <div v-else-if="!node" class="diff-empty">Click a node to see what changed.</div>
      <div v-else-if="!node.parents || !node.parents.length" class="diff-empty">Root commit — no parent to diff against.</div>
      <div v-else-if="!diffData" class="diff-empty">—</div>
      <div v-else-if="!filteredChanges.length" class="diff-empty">No variable changes{{ varFilter ? ' (filter active)' : '' }}.</div>
      <table v-else class="diff-table">
        <thead>
          <tr>
            <th style="white-space:nowrap;width:1%">Variable</th>
            <th>Before</th>
            <th>After</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in filteredChanges" :key="c.var">
            <td class="var" style="white-space:nowrap">{{ c.var }}</td>
            <td class="old">{{ fmtVal(c.old) }}</td>
            <td class="new">{{ fmtVal(c.new) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div style="padding:8px 10px;border-top:1px solid var(--border);flex-shrink:0">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <label style="font-size:12px;font-weight:600;color:var(--text-dim)">🔍 Variable Filter Regex</label>
      </div>
      <div style="display:flex;align-items:center;gap:4px">
        <input
          v-model="varFilter"
          placeholder="e.g. ^karma|money$"
          style="flex:1;padding:3px 8px;font-size:13px;font-family:monospace;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px"
        />
        <button
          class="btn-secondary"
          style="padding:3px 8px;font-size:13px;flex-shrink:0"
          :style="varFilter === '^[^_]' ? 'border-color:var(--accent)' : ''"
          @click="varFilter = '^[^_]'"
        >Game vars</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';

const props = defineProps({
  node: Object,
  diffData: Object,
  loading: Boolean,
  restoring: Boolean,
});

defineEmits(['restore', 'delete']);

const varFilter = ref('^[^_]');

const filteredChanges = computed(() => {
  if (!props.diffData || !props.diffData.changes) return [];
  const raw = (varFilter.value || '').trim();
  if (!raw) return props.diffData.changes;
  const patterns = raw.split(',').map(p => p.trim()).filter(Boolean);
  try {
    const regexes = patterns.map(p => new RegExp(p));
    return props.diffData.changes.filter(c => regexes.some(r => r.test(c.var)));
  } catch {
    return props.diffData.changes;
  }
});

function fmtVal(v) {
  if (v == null) return '—';
  const s = JSON.stringify(v);
  return s.length <= 256 ? s : s.slice(0, 254) + '…';
}
</script>

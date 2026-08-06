<template>
  <div v-if="isOpen" id="diff-pane">
    <div id="diff-header">
      <div id="diff-title">
        <span>{{ node ? node.sha.slice(0, 7) : '' }}</span>
        <span v-if="node && node.is_head" class="branch-badge">HEAD</span>
        <span v-if="node && node.is_suspect" class="branch-badge" style="background:#501a1a;border-color:#8a2a2a;color:#f88a8a">Suspect Lineage</span>
      </div>
      <div id="diff-subtitle">{{ node ? node.subject : '' }}</div>
    </div>

    <div id="diff-body">
      <div v-if="loading" class="diff-empty">Loading diff…</div>
      <div v-else-if="!diffData || !diffData.changes || !diffData.changes.length" class="diff-empty">
        No state differences from parent.
      </div>
      <table v-else class="diff-table">
        <thead>
          <tr>
            <th>Variable</th>
            <th>Parent</th>
            <th>Node</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in diffData.changes" :key="c.var">
            <td class="var">{{ c.var }}</td>
            <td class="old">{{ c.old !== undefined ? c.old : '-' }}</td>
            <td class="new">{{ c.new !== undefined ? c.new : '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({
  isOpen: Boolean,
  node: Object,
  diffData: Object,
  loading: Boolean,
});
</script>

<template>
  <div id="header">
    <h1>Ren'Py Save Graph</h1>
    <nav>
      <button :class="{ active: currentView === 'spaces' }" @click="$emit('update:view', 'spaces')">
        Spaces
      </button>
      <button
        :class="{ active: currentView === 'graph' }"
        :disabled="!selectedSpaceId"
        @click="$emit('open-graph', selectedSpaceId)"
      >
        Graph
      </button>
      <button class="btn-secondary tour-btn" @click="$emit('start-tour')">
        🎓 Tour
      </button>
      <button class="btn-secondary about-btn" @click="$emit('open-about')">
        ℹ About
      </button>
    </nav>
    <span v-if="currentView === 'graph' && headSha" class="head-info">
      HEAD {{ headSha.slice(0, 7) }}
    </span>
  </div>
</template>

<script setup>
defineProps({
  currentView: String,
  selectedSpaceId: String,
  headSha: String,
});

defineEmits(['update:view', 'open-graph', 'start-tour', 'open-about']);
</script>

<style scoped>
.tour-btn, .about-btn {
  font-size: 12px;
  padding: 3px 8px;
  margin-left: 4px;
}
.tour-btn { margin-left: 8px; }
</style>

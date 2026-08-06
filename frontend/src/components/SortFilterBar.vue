<template>
  <div id="sort-filter-bar" style="padding:10px 12px;border-top:1px solid var(--border);flex-shrink:0;background:var(--bg2)">
    <div :style="{ display: 'grid', gridTemplateColumns: hasRouteTargets ? 'auto 1fr 1fr auto' : 'auto 1fr 1fr', gap: '16px', alignItems: 'start' }">
      <!-- Column 1: Horizontal Alignment -->
      <div style="display:flex;flex-direction:column;gap:6px;position:relative">
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:12px;font-weight:600;color:var(--text-dim)">📐 Horizontal Alignment</label>
          <button class="help-btn" @click.stop="$emit('toggle-help', 'milestone', $event)" title="Milestone Progress Variable Rules Help">?</button>
        </div>
        <div style="display:flex;align-items:center;gap:6px">
          <button
            id="btn-alignment-popover"
            class="btn-secondary"
            style="width:175px;padding:4px 10px;font-size:13px;white-space:nowrap;display:flex;align-items:center;justify-content:space-between"
            @click.stop="$emit('toggle-popover')"
          >
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ alignmentButtonLabel }}</span>
            <span style="font-size:10px;flex-shrink:0;margin-left:4px">▼</span>
          </button>
          <button
            class="btn-secondary"
            style="padding:3px 6px;font-size:12px;white-space:nowrap"
            :style="{ color: showMilestoneGuides ? 'var(--accent2)' : 'var(--text-dim)', borderColor: showMilestoneGuides ? 'var(--accent)' : 'var(--border)' }"
            title="Toggle Milestone Column Guidelines"
            @click="$emit('toggle-guides')"
          >Guides</button>
        </div>

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

      <!-- Column 2: Sort Controls -->
      <div style="display:flex;flex-direction:column;gap:6px">
        <label style="font-size:12px;font-weight:600;color:var(--text-dim)">📅 Sort Controls</label>
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:13px;color:var(--text-dim);white-space:nowrap">Base Sort:</label>
          <select
            :value="graphBaseSort"
            @change="$emit('update:graphBaseSort', $event.target.value)"
            style="width:auto;padding:3px 6px;font-size:13px"
          >
            <option value="chronological">📅 Chronological</option>
            <option value="jaccard">🧬 Jaccard Leaf Similarity</option>
          </select>
          <button
            class="btn-secondary"
            style="padding:3px 6px;font-size:13px"
            :title="graphBaseDir === 'asc' ? 'Ascending' : 'Descending'"
            @click="$emit('toggle-sort-dir')"
          >{{ graphBaseDir === 'asc' ? '↓' : '↑' }}</button>
        </div>
        <div v-if="graphBaseSort === 'jaccard'" style="display:flex;align-items:center;gap:6px">
          <label style="font-size:13px;color:var(--text-dim);white-space:nowrap">Secondary:</label>
          <div style="position:relative;flex:1;display:flex;align-items:center">
            <input
              :value="secondarySortExpr"
              @input="$emit('update:secondarySortExpr', $event.target.value)"
              @keydown.enter="$emit('apply-sort')"
              placeholder="e.g. score DESC, day ASC"
              style="width:100%;padding:3px 30px 3px 6px;font-size:13px;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px"
            />
            <button
              class="btn-secondary"
              title="Sort History"
              @click="sortHistoryOpen = !sortHistoryOpen"
              style="position:absolute;right:2px;padding:0 6px;font-size:15px;font-weight:bold;height:22px;border:none;background:transparent;color:var(--text);cursor:pointer"
            >▾</button>
            <div
              v-if="sortHistoryOpen"
              @click.stop
              style="position:absolute;bottom:100%;left:0;right:0;margin-bottom:6px;z-index:250;max-height:260px;overflow-y:auto;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:6px;box-shadow:0 8px 24px rgba(0,0,0,0.6)"
            >
              <div style="font-size:11px;font-weight:600;color:var(--text-dim);padding:4px 6px;border-bottom:1px solid var(--border);margin-bottom:4px">📜 Recent Sorts (up to 20)</div>
              <div v-if="!sortHistory || !sortHistory.length" style="padding:8px 6px;font-size:12px;color:var(--text-dim);text-align:center">No sort history yet</div>
              <div
                v-else v-for="(item, idx) in sortHistory" :key="idx"
                style="display:flex;align-items:center;justify-content:space-between;padding:4px 6px;border-radius:4px;cursor:pointer;font-family:monospace;font-size:12px;color:var(--text);gap:8px"
                @click="sortHistoryOpen = false; $emit('use-sort-history', item)"
              >
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">{{ item }}</span>
                <button @click.stop="$emit('remove-sort-history', idx)" title="Delete from history"
                        style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px;font-weight:bold;padding:0 4px;line-height:1">×</button>
              </div>
            </div>
          </div>
          <button class="btn-secondary" style="padding:3px 8px;font-size:13px;flex-shrink:0" @click="$emit('apply-sort')">Sort</button>
        </div>
      </div>

      <!-- Column 3: Filter Controls -->
      <div style="display:flex;flex-direction:column;gap:6px;position:relative">
        <div style="display:flex;align-items:center;gap:6px">
          <label style="font-size:12px;font-weight:600;color:var(--text-dim)">🔍 Graph Filter Expression</label>
          <button class="help-btn" @click.stop="$emit('toggle-help', 'filter', $event)" title="Expression Help">?</button>
        </div>
        <div style="display:flex;align-items:center;gap:4px">
          <div style="position:relative;flex:1;display:flex;align-items:center">
            <input
              :value="filterExpr"
              @input="$emit('update:filterExpr', $event.target.value)"
              @keydown.enter="$emit('apply-filter')"
              placeholder="e.g. score >= 5 && day != 0"
              style="width:100%;padding:3px 30px 3px 6px;font-size:13px;font-family:monospace;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:4px"
            />
            <button
              class="btn-secondary"
              title="Filter History"
              @click="filterHistoryOpen = !filterHistoryOpen"
              style="position:absolute;right:2px;padding:0 6px;font-size:15px;font-weight:bold;height:22px;border:none;background:transparent;color:var(--text);cursor:pointer"
            >▾</button>
            <div
              v-if="filterHistoryOpen"
              @click.stop
              style="position:absolute;bottom:100%;left:0;right:0;margin-bottom:6px;z-index:250;max-height:260px;overflow-y:auto;background:var(--bg2);border:1px solid var(--border);border-radius:6px;padding:6px;box-shadow:0 8px 24px rgba(0,0,0,0.6)"
            >
              <div style="font-size:11px;font-weight:600;color:var(--text-dim);padding:4px 6px;border-bottom:1px solid var(--border);margin-bottom:4px">📜 Recent Filters (up to 20)</div>
              <div v-if="!filterHistory || !filterHistory.length" style="padding:8px 6px;font-size:12px;color:var(--text-dim);text-align:center">No filter history yet</div>
              <div
                v-else v-for="(item, idx) in filterHistory" :key="idx"
                style="display:flex;align-items:center;justify-content:space-between;padding:4px 6px;border-radius:4px;cursor:pointer;font-family:monospace;font-size:12px;color:var(--text);gap:8px"
                @click="filterHistoryOpen = false; $emit('update:filterExpr', item); $emit('apply-filter')"
              >
                <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">{{ item }}</span>
                <button @click.stop="$emit('remove-filter-history', idx)" title="Delete from history"
                        style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px;font-weight:bold;padding:0 4px;line-height:1">×</button>
              </div>
            </div>
          </div>
          <button class="btn-secondary" style="padding:3px 8px;font-size:13px;flex-shrink:0" @click="$emit('apply-filter')">Filter</button>
          <button v-if="filterActive" class="btn-secondary" style="padding:3px 8px;font-size:13px;flex-shrink:0" @click="$emit('clear-filter')">✕ Clear</button>
        </div>
        <span v-if="filterError" style="font-size:12px;color:#e06060;display:block">{{ filterError }}</span>
      </div>

      <!-- Column 4: Route Targets -->
      <div v-if="routeTargets && routeTargets.length" ref="routeTargetRoot" style="display:flex;flex-direction:column;gap:6px;position:relative">
        <label style="font-size:12px;font-weight:600;color:var(--text-dim)">🎯 Route Targets</label>
        <div style="display:flex;align-items:center;gap:6px">
          <button
            id="btn-route-target-popover"
            class="btn-secondary"
            style="width:160px;padding:4px 10px;font-size:13px;white-space:nowrap;display:flex;align-items:center;justify-content:space-between"
            @click.stop="routeTargetPopoverOpen = !routeTargetPopoverOpen"
          >
            <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ routeTargetButtonLabel }}</span>
            <span style="font-size:10px;flex-shrink:0;margin-left:4px">▼</span>
          </button>
        </div>

        <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--text-dim);cursor:pointer">
          <input
            type="checkbox"
            style="width:auto"
            :checked="hideOffTrack"
            @change="$emit('update:hideOffTrack', $event.target.checked)"
          />
          Hide off-track subtrees
        </label>

        <RouteTargetPopover
          :is-open="routeTargetPopoverOpen"
          :route-targets="routeTargets"
          :is-selected="(name) => selectedRouteTargets.includes(name)"
          @close="routeTargetPopoverOpen = false"
          @toggle="$emit('toggle-route-target', $event)"
          @clear="$emit('clear-route-targets')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import AlignmentPopover from './AlignmentPopover.vue';
import RouteTargetPopover from './RouteTargetPopover.vue';

const props = defineProps({
  showAlignmentPopover: Boolean,
  alignmentButtonLabel: String,
  allTags: Array,
  milestoneVars: Array,
  isAlignmentSelected: Function,
  showMilestoneGuides: Boolean,
  graphBaseSort: String,
  graphBaseDir: String,
  secondarySortExpr: String,
  sortHistory: Array,
  filterExpr: String,
  filterError: String,
  filterActive: Boolean,
  filterHistory: Array,
  routeTargets: Array,
  selectedRouteTargets: {
    type: Array,
    default: () => [],
  },
  hideOffTrack: {
    type: Boolean,
    default: true,
  },
});

defineEmits([
  'toggle-popover',
  'close-popover',
  'toggle-alignment',
  'clear-alignments',
  'toggle-guides',
  'update:graphBaseSort',
  'toggle-sort-dir',
  'update:secondarySortExpr',
  'apply-sort',
  'use-sort-history',
  'remove-sort-history',
  'toggle-route-target',
  'clear-route-targets',
  'update:hideOffTrack',
  'update:filterExpr',
  'apply-filter',
  'clear-filter',
  'use-filter-history',
  'remove-filter-history',
  'toggle-help',
]);

const sortHistoryOpen = ref(false);
const filterHistoryOpen = ref(false);
const routeTargetPopoverOpen = ref(false);
const routeTargetRoot = ref(null);

const hasRouteTargets = computed(() => !!(props.routeTargets && props.routeTargets.length));

const routeTargetButtonLabel = computed(() => {
  if (!props.selectedRouteTargets || !props.selectedRouteTargets.length) return 'None';
  if (props.selectedRouteTargets.length === 1) return props.selectedRouteTargets[0];
  return `${props.selectedRouteTargets.length} Active`;
});

function onDocumentClick(e) {
  if (routeTargetRoot.value && !routeTargetRoot.value.contains(e.target)) {
    routeTargetPopoverOpen.value = false;
  }
}

onMounted(() => document.addEventListener('click', onDocumentClick));
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick));
</script>

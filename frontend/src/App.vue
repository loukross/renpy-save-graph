<template>
  <div id="app">
    <AppHeader
      :current-view="view"
      :selected-space-id="selectedSpaceId"
      :head-sha="graphData ? graphData.head : ''"
      @update:view="view = $event"
      @open-graph="openGraph"
      @start-tour="startInteractiveTour(true)"
      @open-about="aboutModalOpen = true"
    />

    <!-- Spaces View -->
    <div v-show="view === 'spaces'" class="view" id="spaces-view">
      <div class="spaces-content">
        <div class="spaces-inner">
          <h2>Game Spaces</h2>

          <div v-if="!spaces.length && !spaceForm.isNew">
            <p class="empty">No game spaces yet.</p>
            <button class="btn-primary" style="margin-top:12px" @click="startNewSpace">
              Create space
            </button>
          </div>

          <div v-if="spaces.length" class="space-picker-row">
            <select v-model="selectedSpaceId" @change="onSpaceSelected">
              <option v-for="s in spaces" :key="s.id" :value="s.id">{{ s.label || s.id }}</option>
            </select>
          </div>
          <div v-if="spaces.length" class="space-actions-row">
            <button v-if="selectedSpaceId" class="btn-duplicate" @click="duplicateSpace">Duplicate</button>
            <button class="btn-secondary" @click="startNewSpace">New…</button>
            <button class="btn-import" @click="openImportModal">Import…</button>
          </div>

          <SpaceFormModal
            :space-form="spaceForm"
            :selected-space-id="selectedSpaceId"
            :default-data-dir="defaultDataDir"
            @remove-additional-saves-dir="removeAdditionalSavesDir"
            @add-milestone-var="addMilestoneVar"
            @remove-milestone-var="removeMilestoneVar"
            @open-graph="openGraph"
            @add-space="addSpace"
            @save-space="saveSpaceConfig"
            @delete-space="deleteSpace"
            @open-picker="openPicker"
            @toggle-help="toggleHelp"
          />
        </div>
      </div>
    </div>

    <!-- Graph View -->
    <div v-show="view === 'graph'" class="view" id="graph-view">
      <Toolbar
        :available-slots="availableSlots"
        v-model:selected-slot="selectedSlot"
        :loading="graphLoading"
        :watching="!!watcher"
        @refresh="reloadGraph"
        @ingest="ingest"
        @fit-screen="onFitScreen"
        @jump-head="jumpHead"
        @jump-root="jumpRoot"
        @jump-latest="jumpLatest"
        @jump-range="onJumpRange"
      />

      <div id="graph-main">
        <div id="graph-pane">
          <GraphCanvas
            :key="selectedSpaceId + '-' + selectedSlot"
            ref="graphCanvasRef"
            :graph-data="graphData"
            :node-states="nodeStates"
            :node-diffs="nodeDiffs"
            :node-tags="nodeTags"
            :selected-node-sha="selectedNodeSha"
            :selected-alignments="selectedAlignments"
            :lineage-validity-expr="currentSpace ? currentSpace.lineage_validity_expr : ''"
            :show-milestone-guides="showMilestoneGuides"
            :graph-base-sort="graphBaseSort"
            :graph-base-dir="graphBaseDir"
            :filter-expr="appliedFilterExpr"
            :route-targets="currentSpace ? currentSpace.route_targets : []"
            :selected-route-targets="selectedRouteTargets"
            :hide-off-track="hideOffTrack"
            :auto-select-on-add="autoSelectOnAdd"
            :space-id="selectedSpaceId"
            :slot-name="selectedSlot"
            :get-node-equivalence-key="getNodeEquivalenceKey"
            @select-node="onSelectNode"
            @add-node-tag="onAddNodeTag"
            @remove-node-tag="onRemoveNodeTag"
            @edit-note="openNoteOverlay"
            @toggle-auto-select="autoSelectOnAdd = !autoSelectOnAdd"
          />

          <SortFilterBar
            :show-alignment-popover="showAlignmentPopover"
            :alignment-button-label="alignmentButtonLabel"
            :all-tags="allSpaceTags"
            :milestone-vars="currentSpace ? currentSpace.milestone_vars : []"
            :is-alignment-selected="isAlignmentSelected"
            :show-milestone-guides="showMilestoneGuides"
            :graph-base-sort="graphBaseSort"
            :graph-base-dir="graphBaseDir"
            :secondary-sort-expr="graphOrderByExpr"
            :sort-history="currentSortHistory"
            :filter-expr="filterExpr"
            :filter-error="filterError"
            :filter-active="filterActive"
            :filter-history="currentFilterHistory"
            :route-targets="currentSpace ? currentSpace.route_targets : []"
            :selected-route-targets="selectedRouteTargets"
            :hide-off-track="hideOffTrack"
            @update:hideOffTrack="hideOffTrack = $event"
            @toggle-popover="showAlignmentPopover = !showAlignmentPopover"
            @close-popover="showAlignmentPopover = false"
            @toggle-alignment="toggleAlignment($event, reloadGraph)"
            @clear-alignments="clearAlignments(reloadGraph)"
            @toggle-guides="showMilestoneGuides = !showMilestoneGuides"
            @update:graphBaseSort="onBaseSortChange"
            @toggle-sort-dir="onToggleSortDir"
            @update:secondarySortExpr="graphOrderByExpr = $event"
            @apply-sort="applySort"
            @use-sort-history="useSortHistory"
            @remove-sort-history="removeFromSortHistory"
            @toggle-route-target="toggleRouteTarget"
            @clear-route-targets="clearRouteTargets"
            @update:filterExpr="filterExpr = $event"
            @apply-filter="applyFilter"
            @clear-filter="clearFilter"
            @remove-filter-history="removeFromFilterHistory"
            @toggle-help="toggleHelp"
          />
        </div>

        <div id="resizer" ref="resizerRef"></div>

        <DiffPane
          :node="selectedNode"
          :diff-data="diffData"
          :save-dir="selectedNodeSaveDir"
          :loading="diffLoading"
          :restoring="restoring"
          :has-multiple-saves-dirs="hasMultipleSavesDirs"
          @restore="doRestore"
          @delete="openDeleteModal"
          @change-save-dir="openChangeSaveDirModal"
        />
      </div>

      <VariableInspector
        v-model:is-open="bottomPanelOpen"
        :state-data="selectedNodeState"
        v-model:search-query="varSearchQuery"
        :favorite-vars="currentSpace ? currentSpace.favorite_vars : []"
        :loading="stateLoading"
        @toggle-favorite="toggleFavorite"
        @add-to-filter="addToFilter"
      />
    </div>

    <!-- Note edit overlay -->
    <div
      v-if="noteOverlay.open"
      id="note-overlay"
      :style="{ left: noteOverlay.x + 'px', top: noteOverlay.y + 'px', transform: `scale(${noteOverlay.scale})`, transformOrigin: 'top left' }"
      @mousedown.stop
    >
      <textarea
        ref="noteTextareaRef"
        v-model="noteText"
        placeholder="Add a note…"
        @blur="saveNoteAndClose"
        @keydown.enter.exact.prevent="saveNoteAndClose"
        @keydown.esc.prevent="closeNote"
        @input="onNoteInput"
        style="width:100%;min-height:48px;height:48px;resize:none;overflow:hidden"
      ></textarea>
    </div>

    <!-- Modals -->
    <OnboardingModal
      :is-open="onboardingModalOpen"
      @close="onboardingModalOpen = false"
      @start-tour="startInteractiveTour"
    />

    <AboutModal
      :is-open="aboutModalOpen"
      @close="aboutModalOpen = false"
    />

    <DeleteNodeModal
      :is-open="deleteNodeModalOpen"
      :node="nodeToDelete"
      :has-current-head-downstream="hasCurrentHeadDownstream"
      :busy="deleteNodeBusy"
      @close="deleteNodeModalOpen = false"
      @confirm="confirmDeleteNode"
    />

    <PickerModal
      :is-open="picker.open"
      :nodes="picker.nodes"
      :selected="picker.selected"
      :loading="picker.loading"
      :confirm-label="picker.target === 'additional_saves_dir' ? 'Add directory' : 'Select folder'"
      @close="picker.open = false"
      @select="pickerSelect"
      @toggle="pickerToggle"
      @confirm="selectFolder"
    />

    <RemoveSpaceModal
      :is-open="removeSpaceModal.open"
      :space="removeSpaceModal.space"
      @close="removeSpaceModal.open = false"
      @confirm="confirmRemoveSpace"
    />

    <ImportLibraryModal
      :is-open="importModalOpen"
      :form="importForm"
      @close="importModalOpen = false"
      @inspect="inspectLibrary"
      @plan="planImport"
      @import="importLibrary"
      @open-picker="openPicker"
    />

    <RestoreDirModal
      :is-open="restoreDirModal.open"
      :saves-dirs="restoreDirModal.savesDirs"
      :current-dir="restoreDirModal.currentDir"
      @close="restoreDirModal.open = false"
      @confirm="confirmRestoreDir"
    />

    <HelpPopover
      :is-open="helpPopover.open"
      :type="helpPopover.type"
      :left="helpPopover.left"
      :bottom="helpPopover.bottom"
      @close="helpPopover.open = false"
    />

    <div v-if="toastMessage" class="toast">{{ toastMessage }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import jsep from 'jsep';

import AppHeader from './components/AppHeader.vue';
import Toolbar from './components/Toolbar.vue';
import SortFilterBar from './components/SortFilterBar.vue';
import GraphCanvas from './components/GraphCanvas.vue';
import DiffPane from './components/DiffPane.vue';
import VariableInspector from './components/VariableInspector.vue';
import HelpPopover from './components/HelpPopover.vue';
import SpaceFormModal from './components/modals/SpaceFormModal.vue';
import OnboardingModal from './components/modals/OnboardingModal.vue';
import AboutModal from './components/modals/AboutModal.vue';
import DeleteNodeModal from './components/modals/DeleteNodeModal.vue';
import ImportLibraryModal from './components/modals/ImportLibraryModal.vue';
import PickerModal from './components/modals/PickerModal.vue';
import RemoveSpaceModal from './components/modals/RemoveSpaceModal.vue';
import RestoreDirModal from './components/modals/RestoreDirModal.vue';

import { useTags } from './composables/useTags.js';
import { useAlignments } from './composables/useAlignments.js';
import { useGraphData } from './composables/useGraphData.js';

const view = ref('spaces');
const spaces = ref([]);
const selectedSpaceId = ref('');
const availableSlots = ref([]);
const selectedSlot = ref('');
const defaultDataDir = ref('');

const importModalOpen = ref(false);
const importForm = ref({
  library_path: '', saves_dirs: [], label: '',
  inspect: null, inspecting: false, saving: false, error: '',
});

const spaceForm = ref({
  isNew: false,
  label: '',
  saves_dir: '',
  library_path: '',
  node_hint_format: '',
  slot_exclude: '',
  lineage_validity_expr: '',
  milestone_vars: [],
  route_targets: [],
  newMilestoneInput: '',
  saving: false,
  error: '',
});

const bottomPanelOpen = ref(false);
const onboardingModalOpen = ref(false);
const aboutModalOpen = ref(false);
const deleteNodeModalOpen = ref(false);
const deleteNodeBusy = ref(false);
const nodeToDelete = ref(null);
const restoring = ref(false);

const graphBaseSort = ref('chronological');
const graphBaseDir = ref('asc');
const graphOrderByExpr = ref('');
const filterExpr = ref('');
// Only updated when the user hits "Filter" / presses Enter (applyFilter) —
// GraphCanvas watches this, not the live-typed filterExpr, so typing
// doesn't trigger a full graph re-render on every keystroke.
const appliedFilterExpr = ref('');
const filterActive = ref(false);
const filterError = ref('');
const selectedRouteTargets = ref([]);
const hideOffTrack = ref(true);
const autoSelectOnAdd = ref(false);
const toastMessage = ref('');
const varSearchQuery = ref('^[^_]');

let toastTimer = null;
function showToast(msg) {
  toastMessage.value = msg;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastMessage.value = ''; }, 3000);
}

const graphCanvasRef = ref(null);
const resizerRef = ref(null);

const watcher = ref(null);

const noteOverlay = ref({ open: false, sha: null, x: 0, y: 0, scale: 1 });
const noteText = ref('');
const noteTextareaRef = ref(null);

const picker = ref({ open: false, target: 'saves_dir', nodes: [], selected: null, loading: false });
const removeSpaceModal = ref({ open: false, space: null });
const restoreDirModal = ref({ open: false, savesDirs: [], currentDir: '' });
const helpPopover = ref({ open: false, type: null, left: '0px', bottom: '0px' });

const { nodeTags, allSpaceTags, fetchTags, commitTags, addNodeTag, removeNodeTag } = useTags();
const {
  selectedAlignments,
  showAlignmentPopover,
  showMilestoneGuides,
  alignmentButtonLabel,
  isAlignmentSelected,
  toggleAlignment,
  clearAlignments,
  getNodeEquivalenceKey,
} = useAlignments();

const {
  graphData,
  nodeStates,
  nodeDiffs,
  graphLoading,
  selectedNodeSha,
  selectedNode,
  selectedNodeState,
  selectedNodeSaveDir,
  diffData,
  diffLoading,
  stateLoading,
  fetchGraphBundle,
  commitGraphBundle,
  loadAllStates,
  selectNode,
} = useGraphData();

const currentSpace = computed(() => spaces.value.find(s => s.id === selectedSpaceId.value));
const hasMultipleSavesDirs = computed(() => {
  return !!(currentSpace.value && currentSpace.value.additional_saves_dirs && currentSpace.value.additional_saves_dirs.length > 0);
});
const currentSortHistory = computed(() => (currentSpace.value && currentSpace.value.sort_history) || []);
const currentFilterHistory = computed(() => (currentSpace.value && currentSpace.value.filter_history) || []);

const hasCurrentHeadDownstream = computed(() => {
  if (!nodeToDelete.value || !graphData.value || !graphData.value.nodes) return false;
  const targetSha = nodeToDelete.value.sha;
  const childrenMap = new Map();
  graphData.value.nodes.forEach(n => {
    (n.parents || []).forEach(pSha => {
      if (!childrenMap.has(pSha)) childrenMap.set(pSha, []);
      childrenMap.get(pSha).push(n.sha);
    });
  });
  const nodeMap = new Map(graphData.value.nodes.map(n => [n.sha, n]));
  const stack = [...(childrenMap.get(targetSha) || [])];
  const visited = new Set();
  while (stack.length) {
    const currSha = stack.pop();
    if (visited.has(currSha)) continue;
    visited.add(currSha);
    const currNode = nodeMap.get(currSha);
    if (currNode && currNode.is_head) return true;
    const kids = childrenMap.get(currSha) || [];
    for (const k of kids) stack.push(k);
  }
  return false;
});

onMounted(async () => {
  await loadConfig();
  if (spaces.value.length) {
    selectedSpaceId.value = spaces.value[0].id;
    await onSpaceSelected();
  }
  if (!localStorage.getItem('renpy_save_graph_tour_seen')) {
    setTimeout(() => { onboardingModalOpen.value = true; }, 500);
  }
  window.addEventListener('click', onGlobalClick);
  initResizer();
});

onBeforeUnmount(() => {
  window.removeEventListener('click', onGlobalClick);
  stopWatcher();
});

function onGlobalClick(e) {
  if (!e.target.closest('.help-popover') && !e.target.closest('.help-btn')) {
    helpPopover.value.open = false;
  }
}

let suppressSlotWatch = false;

watch(selectedSlot, async (newSlot) => {
  if (suppressSlotWatch) return;
  // Startup picks a slot while still on the Spaces page; loading a graph
  // nobody is looking at costs an ingest and a full fetch for nothing.
  if (view.value !== 'graph') return;
  if (newSlot && selectedSpaceId.value) {
    await reloadGraph();
  }
});

watch(view, (newVal) => {
  if (newVal !== 'graph') stopWatcher();
});

async function loadConfig() {
  try {
    const resp = await fetch('/api/config');
    if (!resp.ok) return;
    const data = await resp.json();
    spaces.value = data.spaces || [];
    defaultDataDir.value = data.default_data_dir || '';
  } catch (e) {
    console.error('Error loading config:', e);
  }
}

async function onSpaceSelected() {
  const sp = currentSpace.value;
  if (!sp) return;
  spaceForm.value = {
    isNew: false,
    label: sp.label || '',
    saves_dir: sp.saves_dir || '',
    additional_saves_dirs: sp.additional_saves_dirs ? [...sp.additional_saves_dirs] : [],
    library_path: sp.library_path || '',
    node_hint_format: sp.node_hint_format || '',
    slot_exclude: sp.slot_exclude || '',
    lineage_validity_expr: sp.lineage_validity_expr || '',
    milestone_vars: sp.milestone_vars ? [...sp.milestone_vars] : [],
    route_targets: sp.route_targets ? [...sp.route_targets] : [],
    newMilestoneInput: '',
    saving: false,
    error: '',
  };
  await loadSlots();
}

function startNewSpace() {
  selectedSpaceId.value = '';
  spaceForm.value = {
    isNew: true,
    label: '',
    saves_dir: '',
    additional_saves_dirs: [],
    library_path: '',
    node_hint_format: '',
    slot_exclude: '',
    lineage_validity_expr: '',
    milestone_vars: [],
    route_targets: [],
    newMilestoneInput: '',
    saving: false,
    error: '',
  };
}

// -- importing a cloned library -------------------------------------------

function openImportModal() {
  importForm.value = {
    step: 1, library_path: '', saves_dirs: [], label: '',
    inspect: null, inspecting: false,
    plan: [], planning: false, approved: false,
    saving: false, error: '',
  };
  importModalOpen.value = true;
}

// Step 2 shows what import would write over, so ask before anything is touched.
async function planImport() {
  const form = importForm.value;
  form.step = 2;
  form.planning = true;
  form.error = '';
  form.approved = false;
  try {
    const resp = await fetch('/api/library/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        library_path: form.library_path,
        saves_dirs: form.saves_dirs.filter(Boolean),
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      form.error = data.detail || 'Could not read the library.';
      return;
    }
    form.plan = data.slots || [];
  } catch (e) {
    form.error = String(e);
  } finally {
    form.planning = false;
  }
}

async function inspectLibrary() {
  const form = importForm.value;
  form.inspect = null;
  if (!form.library_path) return;
  form.inspecting = true;
  try {
    const resp = await fetch(`/api/library/inspect?path=${encodeURIComponent(form.library_path)}`);
    form.inspect = await resp.json();
    if (form.inspect.ok && !form.label) {
      form.label = form.inspect.space?.label || '';
    }
  } catch (e) {
    form.inspect = { ok: false, error: String(e) };
  } finally {
    form.inspecting = false;
  }
}

async function importLibrary() {
  const form = importForm.value;
  form.saving = true;
  form.error = '';
  try {
    const resp = await fetch('/api/spaces/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        library_path: form.library_path,
        saves_dirs: form.saves_dirs.filter(Boolean),
        label: form.label,
        overwrite: form.approved,
      }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      const detail = data.detail;
      if (detail?.error === 'WOULD_OVERWRITE') {
        form.error = `Approve overwriting ${detail.slots.join(', ')} to continue.`;
      } else if (typeof detail === 'string') {
        form.error = detail;
      } else {
        form.error = 'Import failed.';
      }
      return;
    }
    await loadConfig();
    importModalOpen.value = false;
    selectedSpaceId.value = data.id;
    await onSpaceSelected();
  } catch (e) {
    form.error = String(e);
  } finally {
    form.saving = false;
  }
}

function duplicateSpace() {
  const current = currentSpace.value;
  if (!current) return;
  selectedSpaceId.value = '';
  spaceForm.value = {
    isNew: true,
    label: '',
    saves_dir: '',
    additional_saves_dirs: JSON.parse(JSON.stringify(current.additional_saves_dirs || [])),
    library_path: '',
    node_hint_format: current.node_hint_format || '',
    slot_exclude: current.slot_exclude || '',
    lineage_validity_expr: current.lineage_validity_expr || '',
    milestone_vars: JSON.parse(JSON.stringify(current.milestone_vars || [])),
    route_targets: JSON.parse(JSON.stringify(current.route_targets || [])),
    newMilestoneInput: '',
    saving: false,
    error: '',
  };
}

async function addSpace() {
  if (!spaceForm.value.saves_dir) return;
  spaceForm.value.saving = true;
  try {
    const resp = await fetch('/api/spaces', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: spaceForm.value.label,
        saves_dir: spaceForm.value.saves_dir,
        additional_saves_dirs: spaceForm.value.additional_saves_dirs,
        library_path: spaceForm.value.library_path,
        node_hint_format: spaceForm.value.node_hint_format,
        slot_exclude: spaceForm.value.slot_exclude,
        lineage_validity_expr: spaceForm.value.lineage_validity_expr,
        milestone_vars: spaceForm.value.milestone_vars,
        route_targets: spaceForm.value.route_targets,
      }),
    });
    if (resp.ok) {
      const sp = await resp.json();
      await loadConfig();
      selectedSpaceId.value = sp.id;
      await onSpaceSelected();
    }
  } catch (e) {
    console.error('Error adding space:', e);
  } finally {
    spaceForm.value.saving = false;
  }
}

async function saveSpaceConfig() {
  if (!selectedSpaceId.value) return;
  spaceForm.value.saving = true;
  try {
    const resp = await fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        label: spaceForm.value.label,
        saves_dir: spaceForm.value.saves_dir,
        additional_saves_dirs: spaceForm.value.additional_saves_dirs,
        node_hint_format: spaceForm.value.node_hint_format,
        slot_exclude: spaceForm.value.slot_exclude,
        lineage_validity_expr: spaceForm.value.lineage_validity_expr,
        milestone_vars: spaceForm.value.milestone_vars,
        route_targets: spaceForm.value.route_targets,
      }),
    });
    if (resp.ok) {
      spaceForm.value.open = false;
      showToast('Space saved.');
      await loadConfig();
      loadSlots();
      if (view.value === 'graph' && selectedSpaceId.value) {
        reloadGraph();
      }
    }
  } catch (e) {
    console.error('Error saving space config:', e);
  } finally {
    spaceForm.value.saving = false;
  }
}

function deleteSpace() {
  const space = currentSpace.value;
  if (space) removeSpaceModal.value = { open: true, space };
}

async function confirmRemoveSpace(deleteLibrary) {
  const space = removeSpaceModal.value.space;
  removeSpaceModal.value.open = false;
  if (!space) return;
  await fetch(`/api/spaces/${space.id}?delete_library=${deleteLibrary}`, { method: 'DELETE' });
  await loadConfig();
  if (selectedSpaceId.value === space.id) {
    if (spaces.value.length) {
      selectedSpaceId.value = spaces.value[0].id;
      await onSpaceSelected();
    } else {
      startNewSpace();
    }
  }
  showToast('Space removed.');
}

async function loadSlots() {
  if (!selectedSpaceId.value) return;
  try {
    const resp = await fetch(`/api/spaces/${selectedSpaceId.value}/slots`);
    if (!resp.ok) return;
    const data = await resp.json();
    availableSlots.value = data.slots || [];
    if (availableSlots.value.length && (!selectedSlot.value || !availableSlots.value.includes(selectedSlot.value))) {
      selectedSlot.value = availableSlots.value[0];
    }
  } catch (e) {
    console.error('Error loading slots:', e);
  }
}

async function openGraph(spaceId) {
  if (!spaceId) return;
  selectedSpaceId.value = spaceId;
  view.value = 'graph';
  // loadSlots picks a slot, whose watcher would reload the graph a second time.
  // Mute it and reload once here, so the watcher still starts after the load.
  suppressSlotWatch = true;
  try {
    await loadSlots();
    await reloadGraph();
  } finally {
    suppressSlotWatch = false;
  }
  startWatcher(spaceId);
}

async function reloadGraph() {
  if (!selectedSpaceId.value || !selectedSlot.value) return;
  try {
    await fetch(`/api/spaces/${selectedSpaceId.value}/ingest`, { method: 'POST' });
  } catch (e) {}
  await loadSlots();
  graphLoading.value = true;
  try {
    const [bundle, tags] = await Promise.all([
      fetchGraphBundle(selectedSpaceId.value, selectedSlot.value, graphBaseSort.value, graphBaseDir.value, currentSpace.value, appliedFilterExpr.value, graphOrderByExpr.value),
      fetchTags(selectedSpaceId.value, selectedSlot.value),
    ]);
    // Both commits in one tick, so the canvas redraws once.
    commitTags(tags);
    commitGraphBundle(bundle);
  } finally {
    graphLoading.value = false;
  }
}

function onBaseSortChange(value) {
  graphBaseSort.value = value;
  reloadGraph();
}

function onToggleSortDir() {
  graphBaseDir.value = graphBaseDir.value === 'asc' ? 'desc' : 'asc';
  reloadGraph();
}

async function applySort() {
  await reloadGraph();
  const expr = graphOrderByExpr.value.trim();
  if (!expr) return;
  const space = currentSpace.value;
  if (space) {
    let history = [...(space.sort_history || [])];
    history = [expr, ...history.filter(x => x !== expr)].slice(0, 20);
    space.sort_history = history;
    fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sort_history: history }),
    });
  }
}

function useSortHistory(item) {
  graphOrderByExpr.value = item;
  applySort();
}

async function removeFromSortHistory(idx) {
  const space = currentSpace.value;
  if (!space) return;
  const history = [...(space.sort_history || [])];
  history.splice(idx, 1);
  space.sort_history = history;
  await fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sort_history: history }),
  });
}

async function applyFilter() {
  const expr = filterExpr.value.trim();
  if (!expr) { clearFilter(); return; }
  try {
    jsep(expr);
    filterError.value = '';
  } catch (e) {
    filterError.value = e.message;
    return;
  }
  filterActive.value = true;
  appliedFilterExpr.value = expr;
  // Re-fetch states (not the full graph/screenshots/tags) so any variable
  // named only in this filter gets pulled in — otherwise delta()/changed()
  // silently evaluate against undefined for anything not already fetched
  // by favorites/milestones/sort/lineage.
  await loadAllStates(selectedSpaceId.value, selectedSlot.value, currentSpace.value, appliedFilterExpr.value, graphOrderByExpr.value);

  const space = currentSpace.value;
  if (space) {
    let history = [...(space.filter_history || [])];
    history = [expr, ...history.filter(x => x !== expr)].slice(0, 20);
    space.filter_history = history;
    fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filter_history: history }),
    });
  }
}

function clearFilter() {
  filterActive.value = false;
  filterError.value = '';
  filterExpr.value = '';
  appliedFilterExpr.value = '';
}

function toggleRouteTarget(name) {
  const idx = selectedRouteTargets.value.indexOf(name);
  if (idx === -1) {
    selectedRouteTargets.value.push(name);
  } else {
    selectedRouteTargets.value.splice(idx, 1);
  }
  // A route target's expr may reference a variable nothing else needed —
  // make sure it's actually been fetched before GraphCanvas evaluates it.
  loadAllStates(selectedSpaceId.value, selectedSlot.value, currentSpace.value, appliedFilterExpr.value, graphOrderByExpr.value);
}

function clearRouteTargets() {
  selectedRouteTargets.value = [];
}

async function removeFromFilterHistory(idx) {
  const space = currentSpace.value;
  if (!space) return;
  const history = [...(space.filter_history || [])];
  history.splice(idx, 1);
  space.filter_history = history;
  await fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filter_history: history }),
  });
}

async function onSelectNode(sha) {
  await selectNode(selectedSpaceId.value, selectedSlot.value, sha);
  bottomPanelOpen.value = true;
}

// Auto-select brings a newly arrived save point into view. Clicking a node
// yourself does not pan, since you can already see what you clicked.
async function selectAndCenterNode(sha) {
  await onSelectNode(sha);
  await nextTick();
  graphCanvasRef.value && graphCanvasRef.value.centerGraphOnNode(sha);
}

function onAddNodeTag(sha, tag) {
  addNodeTag(selectedSpaceId.value, selectedSlot.value, sha, tag, reloadGraph);
}

function onRemoveNodeTag(sha, tag) {
  removeNodeTag(selectedSpaceId.value, selectedSlot.value, sha, tag, reloadGraph);
}

function removeAdditionalSavesDir(idx) {
  if (spaceForm.value.additional_saves_dirs) {
    spaceForm.value.additional_saves_dirs.splice(idx, 1);
  }
}

function addMilestoneVar() {
  const v = spaceForm.value.newMilestoneInput.trim();
  if (v && !spaceForm.value.milestone_vars.includes(v)) {
    spaceForm.value.milestone_vars.push(v);
    spaceForm.value.newMilestoneInput = '';
  }
}

function removeMilestoneVar(idx) {
  spaceForm.value.milestone_vars.splice(idx, 1);
}

async function toggleFavorite(varName) {
  const space = currentSpace.value;
  if (!space) return;
  const favs = [...(space.favorite_vars || [])];
  const idx = favs.indexOf(varName);
  if (idx === -1) favs.push(varName); else favs.splice(idx, 1);
  space.favorite_vars = favs;
  await fetch(`/api/spaces/${selectedSpaceId.value}/config`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ favorite_vars: favs }),
  });
}

function addToFilter(varName, value) {
  const val = typeof value === 'string' ? `'${value}'` : value;
  const snippet = `${varName} == ${val}`;
  filterExpr.value = filterExpr.value.trim() ? filterExpr.value.trim() + ' && ' + snippet : snippet;
}

// -- ingest / restore / delete ------------------------------------------

async function ingest() {
  if (!selectedSpaceId.value) return;
  try {
    const res = await fetch(`/api/spaces/${selectedSpaceId.value}/ingest`, { method: 'POST' }).then(r => r.json());
    await loadSlots();
    await reloadGraph();
    if (!res.count) {
      showToast('No new save detected in watched folders.');
    } else {
      showToast(`Committed ${res.count} new save point(s).`);
      const lastSha = res.results && res.results.length ? res.results[res.results.length - 1].sha : null;
      if (autoSelectOnAdd.value && lastSha) {
        await selectAndCenterNode(lastSha);
      }
    }
  } catch (e) {
    console.error('Error ingesting:', e);
  }
}

async function doRestore(targetSaveDir = null) {
  if (!selectedNode.value || restoring.value) return;
  restoring.value = true;
  try {
    const targetSha = selectedNode.value.sha;
    const payload = { sha: targetSha };
    if (targetSaveDir) {
      payload.target_save_dir = targetSaveDir;
    }
    const resp = await fetch(`/api/spaces/${selectedSpaceId.value}/slots/${selectedSlot.value}/restore`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}));
      if (resp.status === 400 && e.detail && typeof e.detail === 'object' && e.detail.error === 'SAVE_DIR_REQUIRED') {
        restoreDirModal.value = {
          open: true,
          savesDirs: e.detail.saves_dirs || [],
        };
        return;
      }
      throw new Error(typeof e.detail === 'string' ? e.detail : resp.statusText);
    }
    const info = await resp.json();
    showToast(`Restored to ${info.short}`);
    if (graphData.value && graphData.value.nodes) {
      // Replaced, not mutated in place: the canvas watches graphData by
      // reference, so an in-place edit would never reach the head marker.
      const nodes = graphData.value.nodes.map(n => ({ ...n, is_head: n.sha === targetSha }));
      graphData.value = { ...graphData.value, head: targetSha, nodes };
      const selectedSha = selectedNode.value && selectedNode.value.sha;
      if (selectedSha) {
        selectedNode.value = nodes.find(n => n.sha === selectedSha) || selectedNode.value;
      }
    }
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    restoring.value = false;
  }
}

function openChangeSaveDirModal() {
  if (!currentSpace.value) return;
  const allSavesDirs = [currentSpace.value.saves_dir, ...(currentSpace.value.additional_saves_dirs || [])].filter(Boolean);
  restoreDirModal.value = {
    open: true,
    savesDirs: allSavesDirs,
    currentDir: selectedNodeSaveDir.value || '',
    // Captured now: the confirm handler must not depend on selection surviving.
    sha: selectedNode.value ? selectedNode.value.sha : '',
    slot: selectedSlot.value,
    spaceId: selectedSpaceId.value,
  };
}

async function confirmRestoreDir(chosenDir) {
  const { sha, slot, spaceId } = restoreDirModal.value;
  restoreDirModal.value.open = false;
  if (!sha || !slot || !spaceId) {
    showToast('Could not set save directory: no save point selected.');
    return;
  }
  try {
    const resp = await fetch(`/api/spaces/${spaceId}/slots/${slot}/nodes/${sha}/save-dir`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ save_dir: chosenDir }),
    });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}));
      throw new Error(e.detail || resp.statusText);
    }
    showToast('Updated save directory for node and child nodes.');
    selectedNodeSaveDir.value = chosenDir;
    if (diffData.value) {
      diffData.value = { ...diffData.value, save_dir: chosenDir };
    }
    if (selectedNode.value) {
      selectedNode.value = { ...selectedNode.value, save_dir: chosenDir };
    }
  } catch (err) {
    showToast(`Error: ${err.message}`);
  }
}

function openDeleteModal() {
  const node = selectedNode.value;
  if (!node || node.is_head || !node.parents || !node.parents.length) return;
  nodeToDelete.value = node;
  deleteNodeBusy.value = false;
  deleteNodeModalOpen.value = true;
}

async function confirmDeleteNode(strategy) {
  if (!nodeToDelete.value || deleteNodeBusy.value) return;
  deleteNodeBusy.value = true;
  try {
    const sha = nodeToDelete.value.sha;
    const resp = await fetch(`/api/spaces/${selectedSpaceId.value}/slots/${selectedSlot.value}/nodes/${sha}?strategy=${strategy}`, { method: 'DELETE' });
    if (!resp.ok) {
      const e = await resp.json().catch(() => ({}));
      throw new Error(e.detail || resp.statusText);
    }
    showToast(`Deleted node ${sha.slice(0, 7)}`);
    deleteNodeModalOpen.value = false;
    selectedNodeSha.value = '';
    selectedNode.value = null;
    await reloadGraph();
  } catch (err) {
    showToast(`Error: ${err.message}`);
  } finally {
    deleteNodeBusy.value = false;
  }
}

// -- jump-to-node -----------------------------------------------------

function jumpHead() {
  graphCanvasRef.value && graphCanvasRef.value.jumpToHead();
}

function jumpRoot() {
  graphCanvasRef.value && graphCanvasRef.value.jumpToRoot();
}

function jumpLatest() {
  graphCanvasRef.value && graphCanvasRef.value.jumpToLatest();
}

function onFitScreen() {
  graphCanvasRef.value && graphCanvasRef.value.fitGraphToScreen();
}

function onJumpRange({ from, to }) {
  if (!graphCanvasRef.value) return;
  let fromTs = 0, toTs = Infinity;
  if (from) fromTs = new Date(from + 'T00:00:00').getTime() / 1000;
  if (to) toTs = new Date(to + 'T23:59:59').getTime() / 1000;
  const count = graphCanvasRef.value.jumpToDateRange(fromTs, toTs);
  showToast(count ? `Found ${count} save node(s) in date range` : 'No save nodes found in selected date range');
}

// -- note editing overlay ----------------------------------------------

function openNoteOverlay(payload) {
  noteOverlay.value = { open: true, sha: payload.sha, x: payload.x, y: payload.y, scale: payload.scale };
  noteText.value = payload.text || '';
  nextTick(() => { noteTextareaRef.value && noteTextareaRef.value.focus(); });
}

function onNoteInput(e) {
  e.target.style.height = 'auto';
  e.target.style.height = e.target.scrollHeight + 'px';
}

async function saveNoteAndClose() {
  const sha = noteOverlay.value.sha;
  if (!sha) return;
  const text = noteText.value;
  await fetch(`/api/spaces/${selectedSpaceId.value}/slots/${selectedSlot.value}/note/${sha}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  const node = graphData.value && graphData.value.nodes.find(n => n.sha === sha);
  if (node) node.note = text;
  noteOverlay.value = { open: false, sha: null, x: 0, y: 0, scale: 1 };
}

function closeNote() {
  noteOverlay.value = { open: false, sha: null, x: 0, y: 0, scale: 1 };
}

// -- file watcher --------------------------------------------------------

function startWatcher(spaceId) {
  stopWatcher();
  const es = new EventSource(`/api/spaces/${spaceId}/watch`);
  es.onmessage = async (ev) => {
    const data = JSON.parse(ev.data);
    if (data.error) {
      showToast('Watch error: ' + data.error);
    } else if (data.committed) {
      if (data.slot === selectedSlot.value) {
        showToast(`Auto-committed ${data.short}`);
        await reloadGraph();
        if (autoSelectOnAdd.value && data.sha) {
          await selectAndCenterNode(data.sha);
        }
      } else {
        showToast(`Committed ${data.short} (${data.slot})`);
      }
    }
  };
  watcher.value = es;
}

function stopWatcher() {
  if (watcher.value) {
    watcher.value.close();
    watcher.value = null;
  }
}

// -- folder picker --------------------------------------------------------

async function fetchFolderNode(path) {
  try {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(path)}`);
    const data = res.ok ? await res.json() : { dirs: [], path };
    const basePath = data.path || path;
    return (data.dirs || []).map(name => ({
      name,
      path: (basePath === '/' ? '' : basePath) + '/' + name,
      expanded: false,
      loading: false,
      children: null,
    }));
  } catch (e) {
    return [];
  }
}

async function openPicker(target = 'saves_dir') {
  picker.value.target = target;
  let current;
  if (target === 'import_library') {
    current = importForm.value.library_path;
  } else if (target.startsWith('import_saves_dir:')) {
    current = importForm.value.saves_dirs[Number(target.split(':')[1])];
  } else if (target.startsWith('additional_saves_dir:')) {
    // Changing one that exists: start the browser where it currently points.
    current = spaceForm.value.additional_saves_dirs[Number(target.split(':')[1])];
  } else if (target === 'additional_saves_dir') {
    current = spaceForm.value.saves_dir;
  } else {
    current = spaceForm.value[target];
  }
  picker.value.open = true;
  picker.value.selected = current || null;
  picker.value.nodes = [];
  picker.value.loading = true;

  try {
    const rootNodes = await fetchFolderNode('/');

    if (current && current.startsWith('/')) {
      const parts = current.split('/').filter(Boolean);
      let curNodes = rootNodes;
      let accumPath = '';

      for (const part of parts) {
        accumPath += '/' + part;
        const match = curNodes.find(n => n.name === part || n.path === accumPath);
        if (!match) break;
        const children = await fetchFolderNode(match.path);
        match.children = children;
        match.expanded = true;
        curNodes = children;
      }
    }
    picker.value.nodes = [...rootNodes];
  } catch (e) {
    console.error('Error loading folder picker:', e);
  } finally {
    picker.value.loading = false;
  }
}

async function pickerToggle(node) {
  if (node.expanded) {
    node.expanded = false;
    picker.value.nodes = [...picker.value.nodes];
    return;
  }
  if (node.children !== null) {
    node.expanded = true;
    picker.value.nodes = [...picker.value.nodes];
    return;
  }
  node.loading = true;
  try {
    const res = await fetch(`/api/browse?path=${encodeURIComponent(node.path)}`);
    const data = res.ok ? await res.json() : { dirs: [], path: node.path };
    const basePath = data.path || node.path;
    node.children = (data.dirs || []).map(name => ({
      name, path: basePath + (basePath.endsWith('/') ? '' : '/') + name,
      expanded: false, loading: false, children: null,
    }));
    node.expanded = true;
  } catch (e) {
    console.error('Error expanding folder node:', e);
  } finally {
    node.loading = false;
    picker.value.nodes = [...picker.value.nodes];
  }
}

function pickerSelect(path) {
  picker.value.selected = path;
}

function selectFolder(path) {
  // Import modal targets: the library folder, or one save location by index.
  if (picker.value.target === 'import_library') {
    importForm.value.library_path = path;
    picker.value.open = false;
    inspectLibrary();
    return;
  }
  if (picker.value.target.startsWith('import_saves_dir:')) {
    importForm.value.saves_dirs[Number(picker.value.target.split(':')[1])] = path;
    picker.value.open = false;
    return;
  }
  if (picker.value.target.startsWith('additional_saves_dir:')) {
    const idx = Number(picker.value.target.split(':')[1]);
    const dirs = spaceForm.value.additional_saves_dirs || [];
    if (path && !dirs.some((d, i) => d === path && i !== idx)) dirs[idx] = path;
    picker.value.open = false;
    return;
  }
  if (picker.value.target === 'additional_saves_dir') {
    if (!spaceForm.value.additional_saves_dirs) spaceForm.value.additional_saves_dirs = [];
    if (path && !spaceForm.value.additional_saves_dirs.includes(path)) {
      spaceForm.value.additional_saves_dirs.push(path);
    }
  } else {
    spaceForm.value[picker.value.target] = path;
  }
  picker.value.open = false;
}

// -- shared help popover --------------------------------------------------

function toggleHelp(type, event) {
  if (helpPopover.value.open && helpPopover.value.type === type) {
    helpPopover.value.open = false;
    return;
  }
  const rect = event.currentTarget.getBoundingClientRect();
  const popoverWidth = 360;
  const left = Math.min(window.innerWidth - popoverWidth - 10, Math.max(10, rect.left - 180));
  const bottom = window.innerHeight - rect.top + 8;
  helpPopover.value = { open: true, type, left: left + 'px', bottom: bottom + 'px' };
}

// -- resizable diff pane ---------------------------------------------------

function initResizer() {
  const resizer = resizerRef.value;
  if (!resizer) return;
  resizer.addEventListener('mousedown', (e) => {
    const diffPaneEl = document.getElementById('diff-pane');
    if (!diffPaneEl) return;
    const startX = e.clientX;
    const startW = diffPaneEl.offsetWidth;
    resizer.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();

    const onMove = (ev) => {
      const w = Math.max(150, Math.min(900, startW + (startX - ev.clientX)));
      diffPaneEl.style.width = w + 'px';
    };
    const onUp = () => {
      resizer.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

// -- interactive tour -------------------------------------------------

async function startInteractiveTour(force = false) {
  onboardingModalOpen.value = false;
  localStorage.setItem('renpy_save_graph_tour_seen', 'true');
  try {
    await fetch('/api/examples/reset', { method: 'POST' });
    await loadConfig();
  } catch (e) {
    console.error('Error resetting example space:', e);
  }

  // Start on the Spaces page — the tour walks the config fields there first,
  // then transitions into the Graph view via the milestone-vars step's
  // onNextClick below, staying in sync with driver.js's own progression
  // instead of jumping to the graph before the tour even begins.
  view.value = 'spaces';
  const exSpace = spaces.value.find(s => s.id === 'example-space') || spaces.value[0];
  if (exSpace) {
    selectedSpaceId.value = exSpace.id;
    await onSpaceSelected();
  }

  const driverObj = driver({
    showProgress: true,
    animate: true,
    steps: [
      {
        element: '#header h1',
        popover: {
          title: "Welcome to Ren'Py Save Graph! 🎓",
          description: "This tool organizes your visual novel choices into an interactive story flowchart using a single dedicated save slot in your Ren'Py game.",
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#spaces-view',
        popover: {
          title: 'Game Spaces',
          description: 'Game Spaces represent your visual novel playthroughs. We\'ve initialized an <b>Example Game Space</b> for you to explore.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-saves-dir',
        popover: {
          title: 'Saves Directory',
          description: 'Point this at the game\'s "game/saves/" folder (from the game\'s root, .exe-containing folder). This is the primary required field.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-additional-saves-dirs',
        popover: {
          title: 'Additional Saves Directories',
          description: 'For games split across multiple installations (e.g. Episodes 1–8 and Episode 9+), add extra saves folders here to watch them together and seamlessly link save points across episode releases into one flowchart.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-node-hint',
        popover: {
          title: 'Node Hint Format',
          description: 'Shows a snippet (e.g. the last dialogue line) under each node using {variable} placeholders.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-slot-exclude',
        popover: {
          title: 'Slot Exclude Regex',
          description: 'Hides matching slot names, like autosaves, from the slot picker.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-lineage-validity',
        popover: {
          title: 'Lineage Validity Check',
          description: 'An optional expression (same language as the Graph Filter) describing what a valid save looks like, e.g. delta(\'karma\') >= 0. Any node where it evaluates false gets flagged with a red border — useful for catching an accidental save of past state over future state.',
          side: 'left',
          align: 'start',
        },
      },
      {
        element: '#field-milestone-vars',
        popover: {
          title: 'Milestone Progress Variables',
          description: 'Configure story progress variables (such as <code>currentEpisode</code> or <code>chapter</code>) that increase monotonically. Save points advancing to new milestone values across separate subtrees align along vertical milestone columns in the graph view.',
          side: 'left',
          align: 'start',
        },
      },
      {
        element: '#field-route-targets',
        popover: {
          title: 'Route Targets',
          description: 'Optional named rules (same expression language as the Lineage Validity check), e.g. <code>delta(\'goodChoices\') >= 0</code>, describing a route worth tracking. On the graph view, select one or more targets to see exactly where a branch first fell off that route — everything downstream of that point is hidden by default.',
          side: 'left',
          align: 'start',
          onNextClick: async () => {
            const targetSpaceId = selectedSpaceId.value || spaces.value.find(s => s.id === 'example-space')?.id || spaces.value[0]?.id;
            if (targetSpaceId) {
              await openGraph(targetSpaceId);
              await nextTick();
            }
            driverObj.moveNext();
          },
        },
      },
      {
        element: '#graph-canvas',
        popover: {
          title: 'Interactive Flowchart Canvas',
          description: 'This is your story flowchart! It displays decision points, story branches, and active save heads. Click any node to inspect it.',
          side: 'right',
          align: 'center',
        },
      },
      {
        element: '#slot-select',
        popover: {
          title: 'Single Dedicated Save Slot',
          description: 'Select a slot with a save - for example, 1-1-LT1 is the first slot on the first page.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#watching-indicator',
        popover: {
          title: 'Game Save Watcher',
          description: 'After you save to the selected slot in the game, a new node is automatically added here.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#graph-canvas button',
        popover: {
          title: 'Auto-select on Add',
          description: 'Enable "⚡ Auto-select on add" to automatically select and inspect new save points the instant you save in-game.',
          side: 'left',
          align: 'start',
          onNextClick: async () => {
            if (graphData.value && graphData.value.nodes) {
              const nodeC = graphData.value.nodes.find(n => n.subject && (n.subject.includes('mountain') || n.subject.includes('castle')));
              if (nodeC) {
                await onSelectNode(nodeC.sha);
              }
            }
            driverObj.moveNext();
          },
        },
      },
      {
        element: '#diff-pane',
        popover: {
          title: 'Diff View',
          description: 'Selecting a node shows its choice differences side-by-side compared to its parent node.',
          side: 'left',
          align: 'center',
          onHighlightStarted: async () => {
            if (graphData.value && graphData.value.nodes) {
              const nodeC = graphData.value.nodes.find(n => n.subject && (n.subject.includes('mountain') || n.subject.includes('castle')));
              if (nodeC) {
                await onSelectNode(nodeC.sha);
              }
            }
          },
          onNextClick: () => {
            bottomPanelOpen.value = true;
            driverObj.moveNext();
          },
        },
      },
      {
        element: '#bottom-panel',
        popover: {
          title: 'Variable Inspector',
          description: 'Inspect all recorded Ren\'Py game variables, stats, flags, and inventory items for any save point.',
          side: 'top',
          align: 'center',
        },
      },
      {
        element: '#sort-filter-bar',
        popover: {
          title: 'Sort & Filter',
          description: 'Filter nodes using JSEP expressions like "gold >= 100", or re-order branches chronologically or by choice differences.',
          side: 'top',
          align: 'start',
        },
      },
      {
        element: '.node-tag-manager',
        popover: {
          title: 'Custom Node Tags 🏷️',
          description: 'Click <b>+tag</b> on any node card to attach custom labels (e.g. <code>boss-fight</code> or <code>ending-a</code>). You can then align your flowchart horizontally by tag using the 📐 Horizontal Alignment popover!',
          side: 'right',
          align: 'start',
          onHighlightStarted: async () => {
            if (graphData.value && graphData.value.nodes) {
              const nodeB = graphData.value.nodes.find(n => n.subject && (n.subject.includes('forest') || n.subject.includes('Misty')));
              if (nodeB && graphCanvasRef.value) {
                graphCanvasRef.value.centerGraphOnNode(nodeB.sha);
              }
            }
          },
          onNextClick: async () => {
            if (graphData.value && graphData.value.nodes) {
              const nodeA = graphData.value.nodes.find(n => n.parents && n.parents.length === 0);
              if (nodeA) {
                await onSelectNode(nodeA.sha);
              }
            }
            driverObj.moveNext();
          },
        },
      },
      {
        element: '#restore-bar',
        popover: {
          title: 'Restore to Game',
          description: 'Click "Restore to Game" on any node (other than the current) to copy that save point back into your single slot. Load that slot in-game to branch off and make different choices.',
          side: 'top',
          align: 'center',
          onHighlightStarted: async () => {
            if (graphData.value && graphData.value.nodes) {
              const nodeA = graphData.value.nodes.find(n => n.parents && n.parents.length === 0);
              if (nodeA) {
                await onSelectNode(nodeA.sha);
              }
            }
          },
        },
      },
      {
        element: '#header h1',
        popover: {
          title: 'Enjoy! 🎉',
          description: 'If you have any suggestions, feature requests, or bug reports, please visit the GitHub Issues page.',
          side: 'bottom',
          align: 'start',
        },
      },
    ],
  });
  driverObj.drive();
}
</script>

<style>
@import './styles/main.css';
</style>

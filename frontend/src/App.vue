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
            <button class="btn-secondary" @click="startNewSpace">New…</button>
          </div>

          <SpaceFormModal
            :space-form="spaceForm"
            :selected-space-id="selectedSpaceId"
            :default-data-dir="defaultDataDir"
            @add-milestone-var="addMilestoneVar"
            @remove-milestone-var="removeMilestoneVar"
            @open-graph="openGraph"
            @add-space="addSpace"
            @save-space="saveSpaceConfig"
            @delete-space="deleteSpace"
          />
        </div>
      </div>
    </div>

    <!-- Graph View -->
    <div v-show="view === 'graph'" class="view" id="graph-view">
      <Toolbar
        :available-slots="availableSlots"
        v-model:selected-slot="selectedSlot"
        :show-alignment-popover="showAlignmentPopover"
        :alignment-button-label="alignmentButtonLabel"
        :all-tags="allSpaceTags"
        :milestone-vars="currentSpace ? currentSpace.milestone_vars : []"
        :is-alignment-selected="isAlignmentSelected"
        v-model:sort-dir="graphBaseDir"
        v-model:filter-expr="filterExpr"
        :dates-list="datesList"
        :loading="graphLoading"
        @toggle-popover="showAlignmentPopover = !showAlignmentPopover"
        @close-popover="showAlignmentPopover = false"
        @toggle-alignment="toggleAlignment($event, reloadGraph)"
        @clear-alignments="clearAlignments(reloadGraph)"
      />

      <div id="graph-main">
        <div id="graph-pane">
          <GraphCanvas
            :graph-data="graphData"
            :node-states="nodeStates"
            :node-thumbnails="nodeThumbnails"
            :node-tags="nodeTags"
            :selected-node-sha="selectedNodeSha"
            :selected-alignments="selectedAlignments"
            :show-milestone-guides="showMilestoneGuides"
            :graph-base-sort="graphBaseSort"
            :graph-base-dir="graphBaseDir"
            :auto-select-on-add="autoSelectOnAdd"
            :get-node-equivalence-key="getNodeEquivalenceKey"
            @select-node="onSelectNode"
            @add-node-tag="onAddNodeTag"
            @remove-node-tag="onRemoveNodeTag"
          />
        </div>

        <DiffPane
          :is-open="diffPaneOpen"
          :node="selectedNode"
          :diff-data="diffData"
          :loading="diffLoading"
        />
      </div>

      <VariableInspector
        :is-open="bottomPanelOpen"
        :state-data="selectedNodeState"
        v-model:search-query="varSearchQuery"
        :favorite-vars="currentSpace ? currentSpace.favorite_vars : []"
        :loading="stateLoading"
        @close="bottomPanelOpen = false"
      />
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
      @close="deleteNodeModalOpen = false"
      @confirm="confirmDeleteNode"
    />

    <div v-if="toastMessage" class="toast">{{ toastMessage }}</div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';

import AppHeader from './components/AppHeader.vue';
import Toolbar from './components/Toolbar.vue';
import GraphCanvas from './components/GraphCanvas.vue';
import DiffPane from './components/DiffPane.vue';
import VariableInspector from './components/VariableInspector.vue';
import SpaceFormModal from './components/modals/SpaceFormModal.vue';
import OnboardingModal from './components/modals/OnboardingModal.vue';
import AboutModal from './components/modals/AboutModal.vue';
import DeleteNodeModal from './components/modals/DeleteNodeModal.vue';

import { useTags } from './composables/useTags.js';
import { useAlignments } from './composables/useAlignments.js';
import { useGraphData } from './composables/useGraphData.js';

const view = ref('spaces');
const spaces = ref([]);
const selectedSpaceId = ref('');
const availableSlots = ref([]);
const selectedSlot = ref('');
const defaultDataDir = ref('');

const spaceForm = ref({
  isNew: false,
  label: '',
  saves_dir: '',
  library_path: '',
  node_hint_format: '',
  slot_exclude: '',
  lineage_validity_expr: '',
  milestone_vars: [],
  newMilestoneInput: '',
  saving: false,
  error: '',
});

const diffPaneOpen = ref(false);
const bottomPanelOpen = ref(false);
const onboardingModalOpen = ref(false);
const aboutModalOpen = ref(false);
const deleteNodeModalOpen = ref(false);
const nodeToDelete = ref(null);

const graphBaseSort = ref('chronological');
const graphBaseDir = ref('desc');
const filterExpr = ref('');
const datesList = ref([]);
const autoSelectOnAdd = ref(false);
const toastMessage = ref('');
const varSearchQuery = ref('');

const { nodeTags, allSpaceTags, loadTags, addNodeTag, removeNodeTag } = useTags();
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
  nodeThumbnails,
  graphLoading,
  selectedNodeSha,
  selectedNode,
  selectedNodeState,
  diffData,
  diffLoading,
  stateLoading,
  loadGraph,
  selectNode,
} = useGraphData();

const currentSpace = computed(() => spaces.value.find(s => s.id === selectedSpaceId.value));

onMounted(async () => {
  await loadConfig();
  if (spaces.value.length) {
    selectedSpaceId.value = spaces.value[0].id;
    await onSpaceSelected();
  }
  if (!localStorage.getItem('renpy_save_graph_tour_seen')) {
    setTimeout(() => { onboardingModalOpen.value = true; }, 500);
  }
});

watch(selectedSlot, async (newSlot) => {
  if (newSlot && selectedSpaceId.value) {
    await reloadGraph();
  }
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
    library_path: sp.library_path || '',
    node_hint_format: sp.node_hint_format || '',
    slot_exclude: sp.slot_exclude || '',
    lineage_validity_expr: sp.lineage_validity_expr || '',
    milestone_vars: sp.milestone_vars ? [...sp.milestone_vars] : [],
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
    library_path: '',
    node_hint_format: '',
    slot_exclude: '',
    lineage_validity_expr: '',
    milestone_vars: [],
    newMilestoneInput: '',
    saving: false,
    error: '',
  };
}

async function loadSlots() {
  if (!selectedSpaceId.value) return;
  try {
    const resp = await fetch(`/api/spaces/${selectedSpaceId.value}/slots`);
    if (!resp.ok) return;
    const data = await resp.json();
    availableSlots.value = data.slots || [];
    if (availableSlots.value.length && !selectedSlot.value) {
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
  await loadSlots();
  await reloadGraph();
}

async function reloadGraph() {
  if (!selectedSpaceId.value || !selectedSlot.value) return;
  await loadGraph(selectedSpaceId.value, selectedSlot.value, graphBaseSort.value, graphBaseDir.value, currentSpace.value, filterExpr.value);
  await loadTags(selectedSpaceId.value, selectedSlot.value);
}

async function onSelectNode(sha) {
  await selectNode(selectedSpaceId.value, selectedSlot.value, sha);
  diffPaneOpen.value = true;
  bottomPanelOpen.value = true;
}

function onAddNodeTag(sha, tag) {
  addNodeTag(selectedSpaceId.value, selectedSlot.value, sha, tag, reloadGraph);
}

function onRemoveNodeTag(sha, tag) {
  removeNodeTag(selectedSpaceId.value, selectedSlot.value, sha, tag, reloadGraph);
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

async function startInteractiveTour(force = false) {
  onboardingModalOpen.value = false;
  localStorage.setItem('renpy_save_graph_tour_seen', 'true');
  try {
    await fetch('/api/examples/reset', { method: 'POST' });
    await loadConfig();
  } catch (e) {
    console.error('Error resetting example space:', e);
  }
  const exSpace = spaces.value.find(s => s.id === 'example-space') || spaces.value[0];
  if (exSpace) {
    selectedSpaceId.value = exSpace.id;
    selectedSlot.value = '1-1-LT1';
    await openGraph(exSpace.id);
  }

  const driverObj = driver({
    showProgress: true,
    steps: [
      {
        element: '#header',
        popover: {
          title: "Welcome to Ren'Py Save Graph! 🎮",
          description: "This application tracks your Ren'Py game saves as a visual decision tree.",
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#spaces-view',
        popover: {
          title: 'Game Space Selector',
          description: 'A Game Space represents one Ren\'Py game. Use this dropdown to pick which game to view or configure.',
          side: 'bottom',
          align: 'start',
        },
      },
      {
        element: '#field-saves-dir',
        popover: {
          title: 'Saves Directory',
          description: 'This is the path to your Ren\'Py game\'s saves directory (e.g. <code>~/.renpy/game_name/saves</code>).',
          side: 'left',
          align: 'start',
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
        element: '#diff-pane',
        popover: {
          title: 'Diff View',
          description: 'Selecting a node shows its choice differences side-by-side compared to its parent node.',
          side: 'left',
          align: 'center',
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
        element: '#graph-toolbar',
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

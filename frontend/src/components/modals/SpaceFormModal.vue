<template>
  <div v-if="spaceForm.isNew || selectedSpaceId">
    <hr class="section-divider" />
    <h2>{{ spaceForm.isNew ? 'New space' : 'Space configuration' }}</h2>

    <div class="field">
      <label>Label <span class="optional">(optional)</span></label>
      <input v-model="spaceForm.label" placeholder="My game" />
    </div>

    <div class="field" id="field-saves-dir">
      <label>Saves directory</label>
      <div class="input-row">
        <input v-model="spaceForm.saves_dir" placeholder="/path/to/game/saves" />
        <button class="btn-secondary" @click="$emit('open-picker', 'saves_dir')">Browse…</button>
      </div>
    </div>

    <div class="field" id="field-node-hint">
      <label>Node hint format <span class="optional">(optional)</span></label>
      <input v-model="spaceForm.node_hint_format" style="font-family:monospace" />
    </div>

    <div class="field" id="field-slot-exclude">
      <label>Slot exclude regex <span class="optional">(optional, e.g. autosave)</span></label>
      <input v-model="spaceForm.slot_exclude" placeholder="autosave" style="font-family:monospace" />
    </div>

    <details class="advanced" id="advanced-details">
      <summary>Advanced</summary>

      <div class="field">
        <label>Library path <span class="optional">(default: app data)</span></label>
        <template v-if="spaceForm.isNew">
          <div class="input-row">
            <input
              v-model="spaceForm.library_path"
              :placeholder="defaultDataDir ? defaultDataDir + '/libs/<auto-id>' : 'default'"
            />
            <button class="btn-secondary" @click="$emit('open-picker', 'library_path')">Browse…</button>
          </div>
        </template>
        <template v-else>
          <input :value="spaceForm.library_path" disabled />
        </template>
      </div>

      <div class="field" id="field-lineage-validity">
        <div style="display:flex;align-items:center;gap:6px">
          <label>Lineage validity check expression <span class="optional">(optional)</span></label>
          <button class="help-btn" @click.stop="$emit('toggle-help', 'lineage', $event)" title="Expression Help">?</button>
        </div>
        <input
          v-model="spaceForm.lineage_validity_expr"
          placeholder="e.g. delta('money') >= 0"
          style="font-family:monospace;font-size:12px"
        />
      </div>

      <div class="field" id="field-milestone-vars">
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <label style="margin-bottom:0">Milestone progress variables <span class="optional">(optional)</span></label>
          <button class="help-btn" @click.stop="$emit('toggle-help', 'milestone', $event)" title="Milestone Progress Variable Rules Help">?</button>
        </div>
        <div style="display:flex;gap:6px;margin-bottom:6px">
          <input
            v-model="spaceForm.newMilestoneInput"
            placeholder="Add variable name (e.g. currentEpisode)"
            @keydown.enter.prevent="$emit('add-milestone-var')"
            style="font-family:monospace;font-size:12px;flex:1"
          />
          <button class="btn-secondary" @click.prevent="$emit('add-milestone-var')" style="font-size:12px;flex-shrink:0">+ Add</button>
        </div>
        <div v-if="spaceForm.milestone_vars && spaceForm.milestone_vars.length" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">
          <div
            v-for="(v, idx) in spaceForm.milestone_vars"
            :key="idx"
            style="display:inline-flex;align-items:center;gap:6px;background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:3px 10px;font-family:monospace;font-size:12px;color:var(--accent2)"
          >
            <span>{{ v }}</span>
            <button
              @click.prevent="$emit('remove-milestone-var', idx)"
              style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px;font-weight:bold;padding:0;line-height:1"
              title="Remove variable"
            >×</button>
          </div>
        </div>
      </div>

      <div class="field" id="field-route-targets">
        <div style="margin-bottom:6px">
          <label style="margin-bottom:0">Route targets <span class="optional">(optional)</span></label>
        </div>

        <div style="display:flex;gap:6px;margin-bottom:4px;font-size:11px;font-weight:bold;color:var(--text-dim)">
          <div style="flex:1">Name</div>
          <div style="flex:1.5;display:flex;align-items:center;gap:4px">
            <span>Rule Expression</span>
            <button class="help-btn" @click.stop="$emit('toggle-help', 'route-target', $event)" title="Expression Help">?</button>
          </div>
          <div style="width:65px"></div>
        </div>

        <div style="display:flex;gap:6px;margin-bottom:6px">
          <input
            v-model="newRouteName"
            placeholder="e.g. Max Points"
            style="font-size:12px;flex:1"
          />
          <input
            v-model="newRouteExpr"
            placeholder="e.g. delta('points') >= 0"
            @keydown.enter.prevent="addRouteTarget"
            style="font-family:monospace;font-size:12px;flex:1.5"
          />
          <button class="btn-secondary" @click.prevent="addRouteTarget" style="font-size:12px;width:65px;flex-shrink:0">+ Add</button>
        </div>

        <div v-if="spaceForm.route_targets && spaceForm.route_targets.length" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">
          <div
            v-for="(rt, idx) in spaceForm.route_targets"
            :key="idx"
            style="display:inline-flex;align-items:center;gap:8px;background:var(--bg3);border:1px solid var(--border);border-radius:16px;padding:4px 12px;font-size:12px"
          >
            <strong style="color:var(--accent2)">{{ rt.name }}:</strong>
            <code style="color:var(--text-dim);font-family:monospace">{{ rt.expr }}</code>
            <button
              @click.prevent="removeRouteTarget(idx)"
              style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px;font-weight:bold;padding:0;line-height:1"
              title="Remove Route Target"
            >×</button>
          </div>
        </div>
      </div>
    </details>

    <div v-if="spaceForm.error" class="error">{{ spaceForm.error }}</div>

    <div class="form-actions">
      <button
        v-if="!spaceForm.isNew && selectedSpaceId"
        class="btn-danger"
        @click="$emit('delete-space')"
      >Delete space</button>
      <div v-else></div>
      <div style="display:flex;gap:8px;align-items:center">
        <button
          v-if="!spaceForm.isNew && selectedSpaceId"
          class="btn-secondary"
          @click="$emit('open-graph', selectedSpaceId)"
        >View Graph →</button>
        <button
          class="btn-primary"
          :disabled="spaceForm.saving || !spaceForm.saves_dir"
          @click="spaceForm.isNew ? $emit('add-space') : $emit('save-space')"
        >
          {{ spaceForm.saving
              ? (spaceForm.isNew ? 'Creating…' : 'Saving…')
              : (spaceForm.isNew ? 'Create space' : 'Save') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const props = defineProps({
  spaceForm: Object,
  selectedSpaceId: String,
  defaultDataDir: String,
});

const emit = defineEmits([
  'open-picker',
  'toggle-help',
  'add-milestone-var',
  'remove-milestone-var',
  'delete-space',
  'open-graph',
  'add-space',
  'save-space',
]);

const newRouteName = ref('');
const newRouteExpr = ref('');

function addRouteTarget() {
  const name = newRouteName.value.trim();
  const expr = newRouteExpr.value.trim();
  if (!name || !expr) return;
  if (!props.spaceForm.route_targets) props.spaceForm.route_targets = [];
  props.spaceForm.route_targets.push({ name, expr });
  newRouteName.value = '';
  newRouteExpr.value = '';
}

function removeRouteTarget(idx) {
  if (props.spaceForm.route_targets) {
    props.spaceForm.route_targets.splice(idx, 1);
  }
}
</script>

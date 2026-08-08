<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="max-width:640px">
      <div class="modal-header">
        <span>Import library — step {{ form.step }} of 2</span>
        <button @click="$emit('close')">×</button>
      </div>

      <div class="modal-body" style="padding:16px">
        <!-- Step 1: where the library is, and where its saves belong here. -->
        <template v-if="form.step === 1">
          <p style="color:var(--text-dim);font-size:12px;margin:0 0 14px">
            Clone the library yourself first
            (<code>git clone &lt;url&gt;</code>), then point at the folder it created.
          </p>

          <div class="field">
            <label>Cloned library folder</label>
            <div class="input-row">
              <input
                v-model="form.library_path"
                placeholder="/path/to/cloned-library"
                @change="$emit('inspect')"
              />
              <button class="btn-secondary" @click="$emit('open-picker', 'import_library')">Browse…</button>
            </div>
          </div>

          <p v-if="form.inspecting" style="color:var(--text-dim);font-size:12px">Reading library…</p>
          <div v-else-if="form.inspect && !form.inspect.ok" class="error">{{ form.inspect.error }}</div>
          <p v-else-if="info" style="color:var(--accent2);font-size:12px">
            {{ info.slots.length }} slot{{ info.slots.length === 1 ? '' : 's' }} —
            {{ info.slots.join(', ') }}.
            Uses {{ info.save_dir_count }} save location{{ info.save_dir_count === 1 ? '' : 's' }}.
          </p>

          <template v-if="info">
            <div class="field" v-for="i in info.save_dir_count" :key="i">
              <label>
                Save location {{ i - 1 }}
                <span class="optional">
                  {{ i === 1 ? '(primary)' : '' }}
                  {{ nodeCount(i - 1) ? `· ${nodeCount(i - 1)} save points` : '' }}
                </span>
              </label>
              <div class="input-row">
                <input v-model="form.saves_dirs[i - 1]" placeholder="/path/to/game/saves" />
                <button
                  class="btn-secondary"
                  @click="$emit('open-picker', `import_saves_dir:${i - 1}`)"
                >Browse…</button>
              </div>
            </div>

            <div class="field">
              <label>Label <span class="optional">(optional)</span></label>
              <input v-model="form.label" placeholder="My game" />
            </div>

            <p style="color:var(--gold);font-size:12px;line-height:1.5;margin:14px 0 0">
              Import libraries you made yourself. A library carries <code>.save</code> files,
              and Ren'Py can execute code contained in a save when it loads one.
            </p>
          </template>
        </template>

        <!-- Step 2: what this is about to write over. -->
        <template v-else>
          <p v-if="form.planning" style="color:var(--text-dim);font-size:12px">Checking folders…</p>

          <template v-else-if="clashes.length">
            <p style="color:var(--gold);font-size:12px;line-height:1.5;margin:0 0 10px">
              These slots already have a save file. Importing replaces
              {{ clashes.length === 1 ? 'it' : 'them' }}:
            </p>
            <div
              v-for="entry in clashes"
              :key="entry.slot"
              style="background:var(--bg3);border:1px solid var(--border);border-radius:8px;padding:8px 12px;margin-bottom:6px"
            >
              <div style="color:var(--accent2);font-size:12px">{{ entry.slot }}</div>
              <div style="color:var(--text-dim);font-family:monospace;font-size:11px;word-break:break-all">
                {{ entry.target }}
              </div>
            </div>
            <label style="display:flex;gap:8px;align-items:flex-start;margin-top:12px;color:var(--text);font-size:12px;cursor:pointer">
              <input type="checkbox" v-model="form.approved" style="margin-top:2px;width:auto" />
              <span>I understand these save files will be overwritten.</span>
            </label>
          </template>

          <p v-else style="color:var(--accent2);font-size:12px">
            No existing saves will be overwritten.
          </p>

          <div v-if="form.error" class="error" style="margin-top:12px">{{ form.error }}</div>
        </template>
      </div>

      <div class="modal-footer">
        <button v-if="form.step === 2" class="btn-secondary" @click="form.step = 1">Back</button>
        <button v-else class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button
          v-if="form.step === 1"
          class="btn-primary"
          :disabled="!canContinue"
          @click="$emit('plan')"
        >Next</button>
        <button
          v-else
          class="btn-primary"
          :disabled="!canFinish"
          @click="$emit('import')"
        >{{ form.saving ? 'Importing…' : 'Finish' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  form: Object,
});

defineEmits(['close', 'inspect', 'plan', 'import', 'open-picker']);

const info = computed(() => (props.form.inspect?.ok ? props.form.inspect : null));
const clashes = computed(() => (props.form.plan || []).filter(e => e.occupied));

function nodeCount(index) {
  return info.value?.nodes_per_save_dir?.[index] || 0;
}

// Every location the library uses needs a folder on this machine; without one,
// save points recorded against it have nowhere to be restored to.
const canContinue = computed(() => {
  if (!info.value) return false;
  const dirs = props.form.saves_dirs || [];
  return Array.from({ length: info.value.save_dir_count })
    .every((_, i) => (dirs[i] || '').trim());
});

const canFinish = computed(() =>
  !props.form.planning && !props.form.saving && (!clashes.value.length || props.form.approved)
);
</script>

<template>
  <div v-if="isOpen" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal" style="height:auto;max-height:90vh;width:480px">
      <div class="modal-header">
        <span>🗑 Delete Save Node ({{ node ? node.sha.slice(0, 7) : '' }})</span>
        <button @click="$emit('close')">✕</button>
      </div>
      <div style="padding:16px;font-size:14px;color:var(--text)">
        <p style="margin-bottom:12px">
          Are you sure you want to delete node <strong>{{ node ? node.sha.slice(0, 7) : '' }}</strong>? This is permanent.
        </p>
        <div style="margin-bottom:16px;background:var(--bg3);padding:10px;border-radius:4px;border:1px solid var(--border)">
          <div style="font-weight:600;margin-bottom:4px;color:var(--accent2)">{{ node ? node.subject : '' }}</div>
          <div v-if="node && node.hint" style="font-size:12px;color:var(--text-dim)">{{ node.hint }}</div>
        </div>

        <label style="font-weight:600;display:block;margin-bottom:8px">Downstream saves handling:</label>
        <div style="display:flex;flex-direction:column;gap:10px">
          <label style="display:flex;align-items:flex-start;gap:8px;cursor:pointer">
            <input type="radio" v-model="strategy" value="reparent" style="margin-top:3px;width:auto" />
            <div>
              <strong>🔗 Reparent following saves onto parent</strong>
              <div style="font-size:12px;color:var(--text-dim)">Splices out this node and connects downstream saves directly to the parent node.</div>
            </div>
          </label>
          <label
            style="display:flex;align-items:flex-start;gap:8px"
            :style="hasCurrentHeadDownstream ? 'opacity:0.5;cursor:not-allowed' : 'cursor:pointer'"
          >
            <input
              type="radio" v-model="strategy" value="cascade"
              :disabled="hasCurrentHeadDownstream"
              style="margin-top:3px;width:auto"
            />
            <div>
              <strong>✂️ Delete all following saves</strong>
              <div style="font-size:12px;color:var(--text-dim)">Deletes this save node and all saves that follow it on these branches.</div>
              <div v-if="hasCurrentHeadDownstream" style="font-size:12px;color:#e06060;margin-top:2px">
                ⚠ Disabled because your active save point follows this one.
              </div>
            </div>
          </label>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn-secondary" @click="$emit('close')">Cancel</button>
        <button class="btn-danger" :disabled="busy" @click="$emit('confirm', strategy)">
          {{ busy ? 'Deleting…' : 'Delete Node' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  node: Object,
  hasCurrentHeadDownstream: Boolean,
  busy: Boolean,
});

defineEmits(['close', 'confirm']);

const strategy = ref('reparent');

watch(() => props.isOpen, (open) => {
  if (open) strategy.value = 'reparent';
});
</script>

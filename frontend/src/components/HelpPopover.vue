<template>
  <div
    v-if="isOpen"
    class="help-popover"
    @click.stop
    :style="{
      position: 'fixed',
      left: left,
      bottom: bottom,
      zIndex: 9999,
      width: '360px',
      background: 'var(--bg2)',
      border: '1px solid var(--border)',
      borderRadius: '8px',
      padding: '12px',
      boxShadow: '0 12px 32px rgba(0,0,0,0.7)',
    }"
  >
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;border-bottom:1px solid var(--border);padding-bottom:6px">
      <span style="font-size:13px;font-weight:600;color:var(--accent)">{{ title }}</span>
      <button @click="$emit('close')" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px;font-weight:bold">✕ Close</button>
    </div>

    <div v-if="type === 'filter' || type === 'lineage' || type === 'route-target'" style="font-size:12px;color:var(--text);line-height:1.5;display:flex;flex-direction:column;gap:8px">
      <div v-if="type === 'lineage'">
        Evaluated against each node's diff from its parent. When the
        expression evaluates <strong>false</strong>, the node's lineage is
        marked invalid.
      </div>
      <div v-else-if="type === 'route-target'">
        Evaluated against each node's diff from its parent, same as Lineage
        Validity. The first node along a branch where the expression
        evaluates <strong>false</strong> is that route's divergence point —
        it's marked "Suboptimal for &lt;name&gt;", and everything downstream
        of it is hidden from the graph by default (toggle "Hide off-track
        subtrees" to show it anyway).
      </div>
      <div><strong>Functions:</strong>
        <ul style="margin:4px 0 0 16px;padding:0">
          <li><code>delta('var')</code> — Change in value vs parent node</li>
          <li><code>changed('var')</code> — True if variable changed</li>
          <li><code>changed('var', from, to)</code> — Changed from value to value</li>
          <li><code>added('var')</code> — True if newly created on this node</li>
        </ul>
      </div>
      <div><strong>Comparisons & Logic:</strong>
        <div style="margin-top:2px"><code>&gt;</code>, <code>&lt;</code>, <code>&gt;=</code>, <code>&lt;=</code>, <code>==</code>, <code>!=</code>, <code>&amp;&amp;</code> (AND), <code>||</code> (OR), <code>!</code> (NOT)</div>
      </div>
      <div v-if="type === 'lineage'" style="background:var(--bg3);padding:6px;border-radius:4px;font-family:monospace;font-size:11px">
        delta('goodChoices') &gt;= 0 &amp;&amp; delta('chapter') &gt;= 0 &amp;&amp; ...
      </div>
      <div v-else style="background:var(--bg3);padding:6px;border-radius:4px;font-family:monospace;font-size:11px">
        karma &gt;= 10 &amp;&amp; delta('money') &gt; 0
      </div>
    </div>

    <div v-else-if="type === 'regex'" style="font-size:12px;color:var(--text);line-height:1.5;display:flex;flex-direction:column;gap:6px">
      <div><code>karma</code> — Matches variables containing "karma"</div>
      <div><code>^day</code> — Starts with "day" (e.g. <code>day_num</code>)</div>
      <div><code>score$</code> — Ends with "score"</div>
      <div><code>(karma|gold)</code> — Matches "karma" OR "gold"</div>
      <div><code>^[^_]</code> — Excludes system vars starting with <code>_</code></div>
      <div style="font-size:11px;color:var(--text-dim);margin-top:2px">Note: Matching is case-insensitive by default.</div>
    </div>

    <div v-else-if="type === 'additional-saves-dirs'" style="font-size:12px;color:var(--text);line-height:1.5;display:flex;flex-direction:column;gap:8px">
      <div>
        For games split into multiple separate installations or episode releases (e.g. Episodes 1–8 in one folder, Episode 9+ in another).
      </div>
      <div>
        <strong>How it works:</strong>
        <div style="margin-top:4px;color:var(--text-dim)">
          All configured saves folders are watched simultaneously. Save slots with matching names (e.g. <code>1-1-LT1.save</code>) across separate episode folders are automatically discovered and linked into the same flowchart tree, using the save file with the newest modification timestamp.
        </div>
      </div>
    </div>

    <div v-else-if="type === 'milestone'" style="font-size:12px;color:var(--text);line-height:1.5;display:flex;flex-direction:column;gap:8px">
      <div>
        Milestone variables are game state variables used to align save points across separate subtrees onto shared vertical milestone columns.
      </div>
      <div style="background:var(--bg3);padding:8px;border-radius:4px;border-left:3px solid var(--gold)">
        <strong>Rule for Story Progress Variables:</strong>
        <div style="margin-top:4px;color:var(--text-dim)">
          Milestone variables must represent <strong>monotonically progressing story markers</strong> (e.g. <code>currentEpisode = 1, 2, 3...</code> or <code>chapter</code>).
        </div>
        <div style="margin-top:4px;color:var(--red-val)">
          Variables that fluctuate, decrease, or revert to previous values (like <code>gold</code>, <code>health</code>, or temporary state flags) should <strong>not</strong> be used, as non-monotonic values produce unpredictable layout jumps and branch misalignments.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  isOpen: Boolean,
  type: String,
  left: String,
  bottom: String,
});

defineEmits(['close']);

const titles = {
  filter: '🔍 Graph Filter Expressions',
  lineage: '⚠ Lineage Validity Check Expression',
  'route-target': '🎯 Route Target Rule Expression',
  regex: '🔍 Regex Filter Basics',
  milestone: 'Milestone Progress Variable Rules',
  'additional-saves-dirs': '📁 Additional Saves Directories Help',
};

const title = computed(() => titles[props.type] || titles.regex);
</script>

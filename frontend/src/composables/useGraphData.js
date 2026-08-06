import { ref } from 'vue';

export function useGraphData() {
  const graphData = ref(null);
  const nodeStates = ref({});
  const nodeDiffs = ref({});
  const nodeThumbnails = ref({});
  const graphLoading = ref(false);

  const selectedNodeSha = ref('');
  const selectedNode = ref(null);
  const selectedNodeState = ref(null);
  const diffData = ref(null);
  const diffLoading = ref(false);
  const stateLoading = ref(false);

  async function loadAllStates(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr) {
    if (!spaceId || !slotName) return;
    try {
      const favs = spaceConfig?.favorite_vars || [];
      const mVars = spaceConfig?.milestone_vars || [];
      const needed = new Set([...favs, ...mVars]);
      const rawStr = ((graphOrderByExpr || '') + ' ' + (filterExpr || '') + ' ' + (spaceConfig?.lineage_validity_expr || ''));
      const exprMatches = rawStr.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
      const reserved = new Set(['chrono', 'jaccard', 'asc', 'desc', 'score', 'day', 'and', 'or', 'not', 'true', 'false', 'delta', 'changed', 'added']);
      exprMatches.forEach(v => {
        if (!reserved.has(v.toLowerCase())) needed.add(v);
      });

      const query = needed.size ? `?vars=${encodeURIComponent(Array.from(needed).join(','))}` : '';
      const url = `/api/spaces/${spaceId}/slots/${slotName}/states${query}`;
      const resp = await fetch(url);
      if (!resp.ok) return;
      const allStates = await resp.json();
      nodeStates.value = allStates || {};

      // Compute deltas & diffs for lineage checks
      const diffs = {};
      if (graphData.value && graphData.value.nodes) {
        for (const n of graphData.value.nodes) {
          const vars = allStates[n.sha] || {};
          const pSha = n.parents && n.parents[0];
          const pVars = pSha ? (allStates[pSha] || {}) : {};

          const deltas = {};
          const changed = {};
          const added = new Set();

          for (const [k, newVal] of Object.entries(vars)) {
            if (!Object.prototype.hasOwnProperty.call(pVars, k)) {
              added.add(k);
            } else {
              const oldVal = pVars[k];
              if (oldVal !== newVal) {
                changed[k] = { old: oldVal, new: newVal };
                if (typeof oldVal === 'number' && typeof newVal === 'number') {
                  deltas[k] = newVal - oldVal;
                }
              }
            }
          }
          diffs[n.sha] = { deltas, changed, added };
        }
      }
      nodeDiffs.value = diffs;
    } catch (e) {
      console.error('Error loading states:', e);
    }
  }

  async function loadGraph(spaceId, slotName, baseSort = 'chronological', baseDir = 'desc', spaceConfig = null, filterExpr = '', orderByExpr = '') {
    if (!spaceId || !slotName) return;
    graphLoading.value = true;
    try {
      const base = `/api/spaces/${spaceId}/slots/${slotName}`;
      const url = `${base}/graph?base_sort=${baseSort}&base_dir=${baseDir}&order_by=${encodeURIComponent(orderByExpr)}`;
      const [resp, shotResp] = await Promise.all([
        fetch(url),
        fetch(`${base}/screenshots`).then(r => r.json()).catch(() => ({})),
      ]);
      if (!resp.ok) return;
      graphData.value = await resp.json();
      nodeThumbnails.value = shotResp || {};
      await loadAllStates(spaceId, slotName, spaceConfig, filterExpr, orderByExpr);
    } catch (e) {
      console.error('Error loading graph:', e);
    } finally {
      graphLoading.value = false;
    }
  }

  async function selectNode(spaceId, slotName, sha) {
    if (!graphData.value || !graphData.value.nodes) return;
    const n = graphData.value.nodes.find(x => x.sha === sha);
    if (!n) return;
    selectedNodeSha.value = sha;
    selectedNode.value = n;

    // Load full state for node
    stateLoading.value = true;
    try {
      const resp = await fetch(`/api/spaces/${spaceId}/slots/${slotName}/state/${sha}`);
      if (resp.ok) {
        selectedNodeState.value = await resp.json();
      }
    } catch (e) {
      console.error('Error loading node state:', e);
    } finally {
      stateLoading.value = false;
    }

    // Load diff with parent
    if (n.parents && n.parents.length) {
      diffLoading.value = true;
      try {
        const parentSha = n.parents[0];
        const resp = await fetch(`/api/spaces/${spaceId}/slots/${slotName}/diff/${parentSha}/${sha}`);
        if (resp.ok) {
          diffData.value = await resp.json();
        }
      } catch (e) {
        console.error('Error loading diff:', e);
      } finally {
        diffLoading.value = false;
      }
    } else {
      diffData.value = { changes: [] };
    }
  }

  return {
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
    loadAllStates,
    selectNode,
  };
}

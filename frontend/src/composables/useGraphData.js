import { ref } from 'vue';

const RESERVED = new Set([
  'chrono', 'jaccard', 'asc', 'desc', 'score', 'day', 'and', 'or', 'not',
  'true', 'false', 'delta', 'changed', 'added',
]);

export function useGraphData() {
  const graphData = ref(null);
  const nodeStates = ref({});
  const nodeDiffs = ref({});
  const graphLoading = ref(false);

  const selectedNodeSha = ref('');
  const selectedNode = ref(null);
  const selectedNodeState = ref(null);
  const selectedNodeSaveDir = ref(null);
  const diffData = ref(null);
  const diffLoading = ref(false);
  const stateLoading = ref(false);

  // Only the variables the UI actually evaluates are worth fetching.
  function statesUrl(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr) {
    const needed = new Set([
      ...(spaceConfig?.favorite_vars || []),
      ...(spaceConfig?.milestone_vars || []),
    ]);
    const routeTargetExprs = (spaceConfig?.route_targets || []).map(rt => rt.expr || '').join(' ');
    const rawStr = ((graphOrderByExpr || '') + ' ' + (filterExpr || '') + ' ' + (spaceConfig?.lineage_validity_expr || '') + ' ' + routeTargetExprs);
    const exprMatches = rawStr.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
    exprMatches.forEach(v => {
      if (!RESERVED.has(v.toLowerCase())) needed.add(v);
    });
    const query = needed.size ? `?vars=${encodeURIComponent(Array.from(needed).join(','))}` : '';
    return `/api/spaces/${spaceId}/slots/${slotName}/states${query}`;
  }

  async function fetchStates(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr) {
    const resp = await fetch(statesUrl(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr));
    if (!resp.ok) return null;
    return (await resp.json()) || {};
  }

  function computeDiffs(graph, allStates) {
    const diffs = {};
    if (!graph || !graph.nodes) return diffs;
    for (const n of graph.nodes) {
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
    return diffs;
  }

  async function loadAllStates(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr) {
    if (!spaceId || !slotName) return;
    try {
      const states = await fetchStates(spaceId, slotName, spaceConfig, filterExpr, graphOrderByExpr);
      if (!states) return;
      nodeStates.value = states;
      nodeDiffs.value = computeDiffs(graphData.value, states);
    } catch (e) {
      console.error('Error loading states:', e);
    }
  }

  // Fetch and commit are split so the caller can land the graph, its states and
  // the tags in one tick — one redraw instead of one per response. Thumbnails
  // are not fetched: nodes point <image> straight at /screenshot/{sha}, so the
  // browser streams and caches them rather than us shipping base64 as JSON.
  async function fetchGraphBundle(spaceId, slotName, baseSort = 'chronological', baseDir = 'desc', spaceConfig = null, filterExpr = '', orderByExpr = '') {
    if (!spaceId || !slotName) return null;
    try {
      const url = `/api/spaces/${spaceId}/slots/${slotName}/graph?base_sort=${baseSort}&base_dir=${baseDir}&order_by=${encodeURIComponent(orderByExpr)}`;
      const [graph, states] = await Promise.all([
        fetch(url).then(r => (r.ok ? r.json() : null)),
        fetchStates(spaceId, slotName, spaceConfig, filterExpr, orderByExpr).catch(() => null),
      ]);
      if (!graph) return null;
      return { graph, states: states || {}, diffs: computeDiffs(graph, states || {}) };
    } catch (e) {
      console.error('Error loading graph:', e);
      return null;
    }
  }

  function commitGraphBundle(bundle) {
    if (!bundle) return;
    graphData.value = bundle.graph;
    nodeStates.value = bundle.states;
    nodeDiffs.value = bundle.diffs;
  }

  async function selectNode(spaceId, slotName, sha) {
    if (!graphData.value || !graphData.value.nodes) return;
    const n = graphData.value.nodes.find(x => x.sha === sha);
    if (!n) return;
    selectedNodeSha.value = sha;
    selectedNode.value = n;

    stateLoading.value = true;
    diffLoading.value = true;

    const parentSha = n.parents && n.parents.length ? n.parents[0] : sha;

    const statePromise = fetch(`/api/spaces/${spaceId}/slots/${slotName}/state/${sha}`)
      .then(r => (r.ok ? r.json() : null))
      .catch((e) => {
        console.error('Error loading node state:', e);
        return null;
      });

    const diffPromise = fetch(`/api/spaces/${spaceId}/slots/${slotName}/diff/${parentSha}/${sha}`)
      .then(r => (r.ok ? r.json() : null))
      .catch((e) => {
        console.error('Error loading diff:', e);
        return null;
      });

    try {
      const [stateRes, diffRes] = await Promise.all([statePromise, diffPromise]);
      selectedNodeState.value = stateRes;
      diffData.value = diffRes || { changes: [], save_dir: null };
      selectedNodeSaveDir.value = (diffRes && diffRes.save_dir != null) ? diffRes.save_dir : (stateRes && stateRes.save_dir != null ? stateRes.save_dir : null);
    } finally {
      stateLoading.value = false;
      diffLoading.value = false;
    }
  }

  return {
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
  };
}

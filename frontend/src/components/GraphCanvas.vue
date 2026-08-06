<template>
  <div id="graph-canvas" ref="canvasContainer">
    <button
      class="btn-secondary"
      :style="autoSelectOnAdd ? 'border-color:var(--accent);color:var(--accent2);background:var(--bg3)' : 'color:var(--text-dim)'"
      style="position:absolute;top:12px;right:12px;z-index:200;padding:4px 10px;font-size:12px;border-radius:16px;box-shadow:0 4px 12px rgba(0,0,0,0.4)"
      :title="autoSelectOnAdd ? 'Auto-select on add: ENABLED' : 'Auto-select on add: DISABLED'"
      @click="$emit('toggle-auto-select')"
    >
      {{ autoSelectOnAdd ? '⚡ Auto-select on add' : 'Auto-select on add' }}
    </button>
    <svg id="graph" ref="svgRef"></svg>
    <div
      v-if="!graphData || !graphData.nodes || !graphData.nodes.length"
      style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:14px;pointer-events:none"
    >
      No saves yet
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import * as d3 from 'd3';
import jsep from 'jsep';

const props = defineProps({
  graphData: Object,
  nodeStates: Object,
  nodeDiffs: Object,
  nodeThumbnails: Object,
  nodeTags: Object,
  selectedNodeSha: String,
  selectedAlignments: Array,
  showMilestoneGuides: Boolean,
  graphBaseSort: String,
  graphBaseDir: String,
  filterExpr: String,
  lineageValidityExpr: String,
  routeTargets: Array,
  selectedRouteTargets: {
    type: Array,
    default: () => [],
  },
  hideOffTrack: {
    type: Boolean,
    default: true,
  },
  autoSelectOnAdd: Boolean,
  spaceId: String,
  slotName: String,
  getNodeEquivalenceKey: Function,
});

const emit = defineEmits([
  'select-node',
  'add-node-tag',
  'remove-node-tag',
  'edit-note',
  'toggle-auto-select',
]);

const canvasContainer = ref(null);
const svgRef = ref(null);

let zoomBehavior = null;
let svgSelection = null;
let containerGroup = null;
let savedZoom = null;
let nodePosMap = new Map();
let layoutMeta = { nodeW: 326, nodeH: 222 };

onMounted(() => {
  setupD3Svg();
  if (props.graphData && props.graphData.nodes) {
    renderGraph();
  }
});

watch(
  () => [
    props.graphData,
    props.nodeStates,
    props.nodeDiffs,
    props.selectedNodeSha,
    props.selectedAlignments,
    props.showMilestoneGuides,
    props.graphBaseSort,
    props.graphBaseDir,
    props.filterExpr,
    props.lineageValidityExpr,
    props.routeTargets,
    props.selectedRouteTargets,
    props.hideOffTrack,
    props.nodeTags,
    props.spaceId,
    props.slotName,
  ],
  () => {
    if (props.graphData && props.graphData.nodes) {
      renderGraph();
    }
  },
  { deep: true }
);

function setupD3Svg() {
  if (!svgRef.value) return;
  svgSelection = d3.select(svgRef.value);
  svgSelection.selectAll('*').remove();
  containerGroup = svgSelection.append('g').attr('class', 'graph-container');
}

// -- jsep AST evaluator (ported from ui.html's evalJsep) --------------------

function evalJsep(node, vars, diffInfo) {
  if (!node) return undefined;
  switch (node.type) {
    case 'Literal':
      return node.value;
    case 'Identifier':
      return vars ? vars[node.name] : undefined;
    case 'UnaryExpression':
      if (node.operator === '!') return !evalJsep(node.argument, vars, diffInfo);
      if (node.operator === '-') return -evalJsep(node.argument, vars, diffInfo);
      return undefined;
    case 'LogicalExpression':
    case 'BinaryExpression': {
      const op = node.operator;
      if (op === '&&') return evalJsep(node.left, vars, diffInfo) && evalJsep(node.right, vars, diffInfo);
      if (op === '||') return evalJsep(node.left, vars, diffInfo) || evalJsep(node.right, vars, diffInfo);
      const l = evalJsep(node.left, vars, diffInfo);
      const r = evalJsep(node.right, vars, diffInfo);
      switch (op) {
        case '>=': return l >= r;
        case '<=': return l <= r;
        case '>': return l > r;
        case '<': return l < r;
        case '==': case '===': return l == r;
        case '!=': case '!==': return l != r;
        case '+': return l + r;
        case '-': return l - r;
        default: return undefined;
      }
    }
    case 'CallExpression': {
      const fnName = node.callee && node.callee.name;
      const args = (node.arguments || []).map(a => evalJsep(a, vars, diffInfo));
      const varName = args[0];
      if (!varName) return undefined;
      const info = diffInfo || { deltas: {}, changed: {}, added: new Set() };
      if (fnName === 'delta') {
        return (info.deltas && info.deltas[varName] !== undefined) ? info.deltas[varName] : 0;
      }
      if (fnName === 'changed') {
        const chg = info.changed && info.changed[varName];
        if (!chg) return false;
        if (args.length >= 3) return chg.old === args[1] && chg.new === args[2];
        return true;
      }
      if (fnName === 'added') {
        return info.added ? info.added.has(varName) : false;
      }
      return undefined;
    }
    default:
      return undefined;
  }
}

// -- milestone guide viewport rescale (ported from updateMilestoneGuidesViewport) --

function updateMilestoneGuidesViewport() {
  const svgEl = svgRef.value;
  if (!svgEl || !savedZoom) return;
  const { k, y } = savedZoom;
  const h = svgEl.clientHeight || 600;

  const lineTopY = (38 - y) / k;
  const lineBottomY = (h - 38 - y) / k;
  const labelTopY = (18 - y) / k;
  const labelBottomY = (h - 18 - y) / k;
  const fontSize = (11 / k) + 'px';
  const strokeWidth = 2.0 / k;
  const dashArray = `${6 / k},${4 / k}`;

  const guideG = d3.select(svgEl).select('g.milestone-guides');
  if (guideG.empty()) return;

  guideG.selectAll('line.guide-line')
    .attr('y1', lineTopY).attr('y2', lineBottomY)
    .attr('stroke-width', strokeWidth).attr('stroke-dasharray', dashArray);
  guideG.selectAll('text.guide-label-top').attr('y', labelTopY).attr('font-size', fontSize);
  guideG.selectAll('text.guide-label-bottom').attr('y', labelBottomY).attr('font-size', fontSize);
}

// -- main render --------------------------------------------------------

function renderGraph() {
  if (!svgRef.value || !containerGroup) return;
  containerGroup.selectAll('*').remove();

  const graphData = props.graphData;
  if (!graphData || !graphData.nodes || !graphData.nodes.length) return;
  const nodes = graphData.nodes;

  const hasHint = nodes.some(n => n.hint);
  const hasNotes = nodes.some(n => n.note);
  const imgW = 320;
  const imgH = 172;
  const nodeW = 326;
  const nodeH = hasHint ? (imgH + 85) : (imgH + 50);
  const nodesep = hasNotes ? 100 : 30;
  const ranksep = 50;

  // Sibling ordering: chronological, or Jaccard leaf-similarity rank propagated
  // up from graphData.leaf_order (ported from ui.html's renderGraph).
  const leafOrder = graphData.leaf_order || [];
  const leafRankMap = new Map(leafOrder.map((sha, idx) => [sha, idx]));
  const nodeRankMap = new Map();
  const allParentShas = new Set(nodes.flatMap(n => n.parents));
  const leafNodes = nodes.filter(n => !allParentShas.has(n.sha));
  leafNodes.forEach(leaf => {
    const rank = leafRankMap.has(leaf.sha) ? leafRankMap.get(leaf.sha) : 0;
    const stack = [leaf.sha];
    const visited = new Set();
    while (stack.length) {
      const curr = stack.pop();
      if (visited.has(curr)) continue;
      visited.add(curr);
      if (!nodeRankMap.has(curr) || rank < nodeRankMap.get(curr)) nodeRankMap.set(curr, rank);
      const nObj = nodes.find(x => x.sha === curr);
      if (nObj && nObj.parents) nObj.parents.forEach(p => stack.push(p));
    }
  });

  const isJaccard = props.graphBaseSort === 'jaccard';
  const dir = props.graphBaseDir === 'asc' ? 1 : -1;
  const siblingCompare = (a, b) => {
    if (isJaccard) {
      const rA = nodeRankMap.get(a.sha) ?? 0;
      const rB = nodeRankMap.get(b.sha) ?? 0;
      if (rA !== rB) return (rA - rB) * dir;
    }
    return (a.when - b.when) * dir;
  };

  function buildChildrenMap(nodeList) {
    const map = new Map();
    const rootList = [];
    nodeList.forEach(n => {
      const p = n.parents && n.parents.length ? n.parents[0] : null;
      if (!p) { rootList.push(n); return; }
      if (!map.has(p)) map.set(p, []);
      map.get(p).push(n);
    });
    for (const arr of map.values()) arr.sort(siblingCompare);
    rootList.sort(siblingCompare);
    return { map, rootList };
  }

  let { map: childrenOf, rootList: roots } = buildChildrenMap(nodes);
  // Stable reference to the full (unpruned) tree, so we can later tell
  // whether a visible divergence node actually had children that got
  // hidden — childrenOf itself gets rebuilt from visibleNodes below.
  const originalChildrenOf = childrenOf;

  // Route Targets: walk root-to-leaf. The first node along a branch whose
  // own diff breaks a selected target is the divergence point — it stays
  // visible with a badge naming what it broke. When hideOffTrack is on
  // (the default), everything below that node is pruned outright, since
  // once a branch has diverged it can't recover; the "Hide off-track
  // subtrees" checkbox lets the user turn that pruning off and see the
  // rest of the tree anyway. brokenTargetsBySha only ever holds entries
  // for the divergence points themselves — any
  // entry with a non-empty set is by construction that branch's divergence
  // point (its ancestors were all clean, or it wouldn't have been visited).
  const activeRouteTargets = (props.routeTargets || []).filter(
    rt => (props.selectedRouteTargets || []).includes(rt.name)
  );
  const brokenTargetsBySha = new Map();
  let visibleNodes = nodes;
  if (activeRouteTargets.length) {
    let routeTargetAsts = null;
    const getRouteTargetAsts = () => {
      if (!routeTargetAsts) {
        routeTargetAsts = activeRouteTargets.map(rt => {
          try { return { name: rt.name, ast: jsep(rt.expr) }; } catch { return { name: rt.name, ast: null }; }
        });
      }
      return routeTargetAsts;
    };

    const prunedShaSet = new Set();
    const walk = (n, ancestorDiverged) => {
      if (ancestorDiverged) {
        prunedShaSet.add(n.sha);
        (childrenOf.get(n.sha) || []).forEach(c => walk(c, true));
        return;
      }
      const vars = (props.nodeStates && props.nodeStates[n.sha]) || {};
      const diffInfo = (props.nodeDiffs || {})[n.sha];
      const broken = new Set();
      getRouteTargetAsts().forEach(({ name, ast }) => {
        if (!ast) return;
        let ok = true;
        try { ok = !!evalJsep(ast, vars, diffInfo); } catch { ok = true; }
        if (!ok) broken.add(name);
      });
      brokenTargetsBySha.set(n.sha, broken);
      const diverged = broken.size > 0;
      (childrenOf.get(n.sha) || []).forEach(c => walk(c, diverged));
    };
    roots.forEach(r => walk(r, false));

    if (prunedShaSet.size && props.hideOffTrack) {
      visibleNodes = nodes.filter(n => !prunedShaSet.has(n.sha));
      ({ map: childrenOf, rootList: roots } = buildChildrenMap(visibleNodes));
    }
  }

  const selectedAlignments = props.selectedAlignments || [];
  let rootData;

  if (!selectedAlignments.length) {
    const buildSimple = (n) => ({ sha: n.sha, node: n, children: (childrenOf.get(n.sha) || []).map(buildSimple) });
    const synthetic = roots.length !== 1;
    rootData = synthetic
      ? { sha: '__synthetic_root__', node: null, children: roots.map(buildSimple) }
      : (roots.length ? buildSimple(roots[0]) : null);
  } else {
    // Pre-layout milestone padding pass (ported from ui.html renderGraph).
    const shaKeyMap = new Map();
    const shaKeyPartsMap = new Map();
    const rawDepths = new Map();

    const computeRawDepth = (n, depth) => {
      rawDepths.set(n.sha, depth);
      const vars = (props.nodeStates && props.nodeStates[n.sha]) || {};
      const keyParts = props.getNodeEquivalenceKey
        ? props.getNodeEquivalenceKey(n, vars, props.nodeStates, props.nodeTags)
        : null;
      if (keyParts && keyParts.length) {
        shaKeyMap.set(n.sha, keyParts.join(','));
        shaKeyPartsMap.set(n.sha, keyParts);
      }
      (childrenOf.get(n.sha) || []).forEach(c => computeRawDepth(c, depth + 1));
    };
    roots.forEach(r => computeRawDepth(r, 1));

    const keyDepthsMap = new Map();
    shaKeyMap.forEach((key, sha) => {
      if (!keyDepthsMap.has(key)) keyDepthsMap.set(key, []);
      keyDepthsMap.get(key).push(rawDepths.get(sha));
    });

    const keyInfo = [];
    keyDepthsMap.forEach((depths, key) => {
      const avgDepth = depths.reduce((a, b) => a + b, 0) / depths.length;
      const minDepth = Math.min(...depths);
      keyInfo.push({ key, avgDepth, minDepth });
    });
    keyInfo.sort((a, b) => {
      if (a.minDepth !== b.minDepth) return a.minDepth - b.minDepth;
      if (a.avgDepth !== b.avgDepth) return a.avgDepth - b.avgDepth;
      return a.key.localeCompare(b.key, undefined, { numeric: true, sensitivity: 'base' });
    });

    const milestoneTargetDepths = new Map();
    let runningTargetDepth = 0;
    keyInfo.forEach((info) => {
      const matchingShas = Array.from(shaKeyMap.entries()).filter(([, k]) => k === info.key).map(([s]) => s);
      const maxRawDepthOfKey = Math.max(1, ...matchingShas.map(sha => rawDepths.get(sha) || 1));
      runningTargetDepth = Math.max(runningTargetDepth + 1, maxRawDepthOfKey);
      milestoneTargetDepths.set(info.key, runningTargetDepth);
    });

    const buildPadded = (n, currentMilestoneDepth) => {
      const children = childrenOf.get(n.sha) || [];
      const paddedChildren = [];
      children.forEach(c => {
        const cKey = shaKeyMap.get(c.sha);
        const childTargetDepth = (cKey && milestoneTargetDepths.has(cKey))
          ? milestoneTargetDepths.get(cKey)
          : currentMilestoneDepth + 1;
        const dummyHops = Math.max(0, childTargetDepth - currentMilestoneDepth - 1);
        let childTree = buildPadded(c, childTargetDepth);
        for (let i = 0; i < dummyHops; i++) {
          childTree = { sha: `__dummy_${c.sha}_${i}__`, node: null, isDummy: true, children: [childTree] };
        }
        paddedChildren.push(childTree);
      });
      return {
        sha: n.sha,
        node: n,
        milestoneKey: shaKeyMap.get(n.sha) || null,
        milestoneKeyParts: shaKeyPartsMap.get(n.sha) || null,
        children: paddedChildren,
      };
    };

    const synthetic = roots.length !== 1;
    const firstTarget = (roots.length && shaKeyMap.get(roots[0].sha))
      ? (milestoneTargetDepths.get(shaKeyMap.get(roots[0].sha)) || 1)
      : 1;
    rootData = synthetic
      ? { sha: '__synthetic_root__', node: null, children: roots.map(r => buildPadded(r, firstTarget)) }
      : (roots.length ? buildPadded(roots[0], firstTarget) : null);
  }

  if (!rootData) return;

  const synthetic = roots.length !== 1;
  const hierarchy = d3.hierarchy(rootData, d => d.children);
  d3.tree().nodeSize([nodeH + nodesep, nodeW + ranksep])(hierarchy);

  const realNodes = hierarchy.descendants().filter(d => !d.data.isDummy && !(synthetic && d.depth === 0));

  const posMap = new Map();
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  realNodes.forEach(d => {
    const screenX = d.y, screenY = d.x;
    minX = Math.min(minX, screenX); maxX = Math.max(maxX, screenX);
    minY = Math.min(minY, screenY); maxY = Math.max(maxY, screenY);
    posMap.set(d.data.sha, { rawX: screenX, rawY: screenY });
  });
  if (!realNodes.length) { minX = maxX = minY = maxY = 0; }
  const shiftX = -(minX - nodeW / 2);
  const shiftY = -(minY - nodeH / 2);
  posMap.forEach(p => {
    p.x = p.rawX + shiftX;
    p.y = p.rawY + shiftY;
  });

  nodePosMap = posMap;
  layoutMeta = { nodeW, nodeH, imgW, imgH };

  // Milestone guide lines (ported from ui.html renderGraph).
  if (selectedAlignments.length && props.showMilestoneGuides) {
    const guideG = containerGroup.append('g').attr('class', 'milestone-guides');
    const rankInfoMap = new Map();
    realNodes.forEach(d => {
      if (d.data.milestoneKey && posMap.has(d.data.sha)) {
        if (!rankInfoMap.has(d.data.milestoneKey)) {
          rankInfoMap.set(d.data.milestoneKey, { x: posMap.get(d.data.sha).x, parts: d.data.milestoneKeyParts || [] });
        }
      }
    });
    rankInfoMap.forEach(({ x, parts }) => {
      const lineX = x - nodeW / 2 - 25;
      guideG.append('line').attr('class', 'guide-line')
        .attr('x1', lineX).attr('y1', 0).attr('x2', lineX).attr('y2', 0)
        .attr('stroke', '#8ab4f8').attr('stroke-opacity', '0.6')
        .attr('stroke-dasharray', '6,4').attr('stroke-width', 2.0);

      const topText = guideG.append('text').attr('class', 'guide-label-top')
        .attr('x', lineX).attr('y', 0).attr('text-anchor', 'middle')
        .attr('fill', 'var(--accent2)').attr('font-size', '11px').attr('font-weight', '600');
      parts.forEach((p, idx) => topText.append('tspan').attr('x', lineX).attr('dy', idx === 0 ? 0 : 14).text(p));

      const botText = guideG.append('text').attr('class', 'guide-label-bottom')
        .attr('x', lineX).attr('y', 0).attr('text-anchor', 'middle')
        .attr('fill', 'var(--accent2)').attr('font-size', '11px').attr('font-weight', '600');
      parts.forEach((p, idx) => botText.append('tspan').attr('x', lineX).attr('dy', idx === 0 ? 0 : 14).text(p));
    });
  }

  // Shared fade gradient for the "hidden subtree" stub drawn off suboptimal
  // nodes below. Every node's stub uses the same local start/end x (it's
  // drawn in that node's own translated <g>), so one userSpaceOnUse
  // gradient with fixed coordinates works for all of them — objectBoundingBox
  // (the SVG default) doesn't apply here since a perfectly horizontal line
  // has a zero-height bounding box, which the spec says to just not render.
  const stubLineStartX = nodeW / 2;
  const stubLineEndX = stubLineStartX + 90;
  const defs = containerGroup.append('defs');
  const fadeGradient = defs.append('linearGradient')
    .attr('id', 'route-target-fade')
    .attr('gradientUnits', 'userSpaceOnUse')
    .attr('x1', stubLineStartX).attr('y1', 0).attr('x2', stubLineEndX).attr('y2', 0);
  fadeGradient.append('stop').attr('offset', '0%').attr('stop-color', '#2a3a6a').attr('stop-opacity', 1);
  fadeGradient.append('stop').attr('offset', '100%').attr('stop-color', '#2a3a6a').attr('stop-opacity', 0);

  // Edges
  const edgesG = containerGroup.append('g').attr('class', 'edgePaths');
  realNodes.forEach(d => {
    if (synthetic && d.depth === 0) return;
    let p = d.parent;
    while (p && (p.data.isDummy || (synthetic && p.depth === 0))) p = p.parent;
    if (!p || !p.data || !p.data.sha) return;
    const sp = posMap.get(p.data.sha);
    const tp = posMap.get(d.data.sha);
    if (!sp || !tp) return;
    const sx = sp.x + nodeW / 2, sy = sp.y;
    const tx = tp.x - nodeW / 2, ty = tp.y;
    const midX = (sx + tx) / 2;
    edgesG.append('g').attr('class', 'edgePath').append('path')
      .attr('d', `M${sx},${sy} C${midX},${sy} ${midX},${ty} ${tx},${ty}`)
      .attr('stroke', '#2a3a6a').attr('stroke-width', 1.5).attr('fill', 'none');
  });

  // Parse filter / lineage-validity expressions once per render.
  let filterAst = null;
  const filterExprTrim = (props.filterExpr || '').trim();
  if (filterExprTrim) {
    try { filterAst = jsep(filterExprTrim); } catch { filterAst = null; }
  }
  let lineageAst = null;
  if (props.lineageValidityExpr) {
    try { lineageAst = jsep(props.lineageValidityExpr); } catch { lineageAst = null; }
  }

  // Nodes
  const nodesG = containerGroup.append('g').attr('class', 'nodes');
  const nodeSel = nodesG.selectAll('g.node')
    .data(realNodes, d => d.data.sha)
    .enter()
    .append('g')
    .attr('class', d => {
      const n = d.data.node;
      return ['node', n.is_head ? 'head' : '', n.sha === props.selectedNodeSha ? 'selected' : ''].filter(Boolean).join(' ');
    })
    .style('cursor', 'pointer')
    .attr('transform', d => `translate(${posMap.get(d.data.sha).x},${posMap.get(d.data.sha).y})`)
    .on('click', (event, d) => {
      event.stopPropagation();
      emit('select-node', d.data.sha);
    });

  nodeSel.each(function (d) {
    const n = d.data.node;
    const sha = n.sha;
    const el = this;
    const vars = (props.nodeStates && props.nodeStates[sha]) || {};
    const diffInfo = (props.nodeDiffs || {})[sha];
    const parentSha = n.parents && n.parents.length ? n.parents[0] : null;

    let isSuspect = n.is_suspect;
    if (!isSuspect && lineageAst && parentSha) {
      try { isSuspect = !evalJsep(lineageAst, vars, diffInfo); } catch { isSuspect = false; }
    }
    d3.select(el).classed('suspect', isSuspect);

    const brokenTargets = Array.from(brokenTargetsBySha.get(sha) || []);
    const isSuboptimal = !isSuspect && brokenTargets.length > 0;

    const strokeColor = sha === props.selectedNodeSha
      ? '#50a0ff'
      : (isSuspect ? '#c04040' : (isSuboptimal ? '#8b5a2b' : '#2a3060'));

    d3.select(el).append('rect')
      .attr('class', 'node-bg')
      .attr('rx', 6).attr('ry', 6)
      .attr('x', -nodeW / 2).attr('y', -nodeH / 2)
      .attr('width', nodeW).attr('height', nodeH)
      .attr('stroke', strokeColor)
      .attr('stroke-width', sha === props.selectedNodeSha ? 3 : 2);

    // Ring goes before decorateNode so its stroke stays underneath the
    // tag pills (left edge) and pencil/notes button (bottom edge) that
    // decorateNode draws — it never overlaps the thumbnail either way.
    const headPad = 4;
    const headRingStrokeWidth = 5;
    if (n.is_head) {
      d3.select(el).append('rect')
        .attr('class', 'head-ring')
        .attr('x', -nodeW / 2 - headPad).attr('y', -nodeH / 2 - headPad)
        .attr('width', nodeW + headPad * 2).attr('height', nodeH + headPad * 2)
        .attr('rx', 9).attr('ry', 9)
        .attr('fill', 'none').attr('stroke', '#c8a020').attr('stroke-width', headRingStrokeWidth);
    }

    decorateNode(el, n, { nodeW, nodeH, imgW, imgH });

    if (n.is_head) {
      // Triangle only, drawn after decorateNode so it renders on top of
      // the thumbnail image. Its top touches the bottom of the ring's
      // top stroke edge.
      const triY = -nodeH / 2 - headPad + headRingStrokeWidth / 2;
      d3.select(el).append('polygon')
        .attr('points', `-11,${triY} 11,${triY} 0,${triY + 14}`)
        .attr('fill', '#c8a020');
    }

    if (isSuspect) {
      const invalidStrokeW = 5, pad = invalidStrokeW / 2;
      d3.select(el).append('rect')
        .attr('class', 'invalid-ring')
        .attr('x', -nodeW / 2 + pad).attr('y', -nodeH / 2 + pad)
        .attr('width', nodeW - pad * 2).attr('height', nodeH - pad * 2)
        .attr('rx', 4).attr('ry', 4)
        .attr('fill', 'none').attr('stroke', '#c04040').attr('stroke-width', invalidStrokeW);

      const iconSize = 30, gap = 6, badgeH = 30;
      const badgeBottomY = -nodeH / 2 - 4;
      const badgeY = badgeBottomY - badgeH;
      const iconX = -nodeW / 2;
      const boxX = iconX + iconSize + gap;
      const badgeG = d3.select(el).append('g').attr('class', 'lineage-invalid-badge');
      badgeG.append('text').attr('x', iconX).attr('y', badgeY + badgeH / 2 + 10)
        .attr('text-anchor', 'start').attr('font-size', iconSize).attr('fill', '#ff3b3b').text('⚠');
      badgeG.append('text').attr('x', boxX).attr('y', badgeY + badgeH / 2 + 5)
        .attr('text-anchor', 'start').attr('font-size', '15').attr('font-weight', 'bold')
        .attr('fill', '#ff3b3b').text('Invalid lineage detected');
    } else if (isSuboptimal) {
      const prefix = '😬 Suboptimal for ';
      const routeNames = brokenTargets.join(', ');
      const fontSize = 14;
      const badgeG = d3.select(el).append('g').attr('class', 'route-target-badge');
      badgeG.append('rect')
        .attr('x', -nodeW / 2).attr('y', -nodeH / 2 - 30)
        .attr('width', Math.min(nodeW, 24 + (prefix.length + routeNames.length) * 7.5)).attr('height', 23)
        .attr('rx', 4)
        .attr('fill', '#2a1f10').attr('stroke', '#8b5a2b').attr('stroke-width', 1);
      const textEl = badgeG.append('text')
        .attr('x', -nodeW / 2 + 6).attr('y', -nodeH / 2 - 14)
        .attr('text-anchor', 'start').attr('font-size', fontSize)
        .attr('fill', '#c9a876');
      textEl.append('tspan').text(prefix);
      textEl.append('tspan').attr('font-weight', 'bold').text(routeNames);

      // This is the divergence point — if hiding is on and it actually had
      // children (checked against the pre-pruning tree, since childrenOf
      // itself no longer has them), stub out a line like a normal edge
      // would use, fading into floating text marking what's hidden past here.
      if (props.hideOffTrack && (originalChildrenOf.get(sha) || []).length > 0) {
        const stubG = d3.select(el).append('g').attr('class', 'hidden-subtree-stub');
        stubG.append('path')
          .attr('d', `M${stubLineStartX},0 L${stubLineEndX},0`)
          .attr('stroke', 'url(#route-target-fade)')
          .attr('stroke-width', 1.5)
          .attr('fill', 'none');
        stubG.append('text')
          .attr('x', stubLineEndX + 6).attr('y', 4)
          .attr('text-anchor', 'start').attr('font-size', '13px')
          .attr('fill', '#607080')
          .text('(suboptimal tree hidden)');
      }
    }

    if (filterAst) {
      let passes = true;
      try { passes = !!evalJsep(filterAst, vars, diffInfo); } catch { passes = true; }
      if (!passes) d3.select(el).style('opacity', '0.25').style('filter', 'blur(2px)');
    }
  });

  // Zoom / pan — decide the initial transform before this first render so
  // nodes don't start out cut off at the edge (ported from ui.html).
  const zoom = d3.zoom().on('zoom', (event) => {
    containerGroup.attr('transform', event.transform);
    savedZoom = event.transform;
    updateMilestoneGuidesViewport();
  });
  zoomBehavior = zoom;
  svgSelection.call(zoom);

  if (!savedZoom) {
    const svgEl = svgRef.value;
    const sw = svgEl.clientWidth || 800, sh = svgEl.clientHeight || 600;
    const margin = 60;
    const totalW = Math.max(1, (maxX - minX) + nodeW);
    const totalH = Math.max(1, (maxY - minY) + nodeH);
    const scale = Math.max(0.01, Math.min(1, Math.min((sw - margin * 2) / totalW, (sh - margin * 2) / totalH)));
    savedZoom = d3.zoomIdentity
      .translate(sw / 2 - (totalW / 2) * scale, sh / 2 - (totalH / 2) * scale)
      .scale(scale);
  }
  svgSelection.call(zoom.transform, savedZoom);
  updateMilestoneGuidesViewport();
}

// -- node decoration (ported from ui.html's _decorateNode) ------------------

function decorateNode(el, n, meta) {
  const { nodeW, nodeH, imgW, imgH } = meta;
  const sha = n.sha;
  const nodeSel = d3.select(el);
  const imgX = -imgW / 2;
  const imgY = -nodeH / 2 + 3;
  const tsY = imgY + imgH + 20;

  nodeSel.append('image')
    .attr('href', (props.nodeThumbnails && props.nodeThumbnails[sha]) || `/api/spaces/${props.spaceId}/slots/${props.slotName}/screenshot/${sha}`)
    .attr('x', imgX).attr('y', imgY)
    .attr('width', imgW).attr('height', imgH)
    .attr('preserveAspectRatio', 'xMidYMid meet');

  const ts = new Date(n.when * 1000);
  const label = ts.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    + ' ' + ts.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  nodeSel.append('text')
    .attr('x', 0).attr('y', tsY)
    .attr('text-anchor', 'middle').attr('font-size', '14')
    .attr('fill', '#8a9ac0').text(label);

  if (n.hint) {
    const fo = nodeSel.append('foreignObject')
      .attr('x', -nodeW / 2 + 6).attr('y', tsY + 14)
      .attr('width', nodeW - 12).attr('height', 38);
    fo.append('xhtml:div')
      .style('font-size', '13px').style('color', '#607080')
      .style('text-align', 'center').style('line-height', '1.35')
      .style('overflow', 'hidden').style('max-height', '38px')
      .style('padding', '0 6px').style('word-break', 'break-word')
      .text(n.hint);
  }

  // Left-edge tag manager overlay
  const tags = (props.nodeTags && props.nodeTags[sha]) || [];
  const tagFoH = 30 + tags.length * 26;
  const tagFo = nodeSel.append('foreignObject')
    .attr('class', 'node-tag-manager')
    .attr('x', -nodeW / 2 - 10).attr('y', -nodeH / 2 + 23)
    .attr('width', 220).attr('height', Math.max(120, tagFoH))
    .style('overflow', 'visible');
  const tagContainer = tagFo.append('xhtml:div')
    .style('display', 'flex').style('flex-direction', 'column')
    .style('align-items', 'flex-start').style('gap', '4px')
    .style('pointer-events', 'auto');

  const addPill = tagContainer.append('xhtml:div')
    .style('background', 'rgba(15, 15, 34, 0.92)').style('border', '1px solid var(--accent)')
    .style('color', 'var(--accent2)').style('font-size', '11px').style('font-weight', '600')
    .style('padding', '2px 8px').style('border-radius', '10px').style('cursor', 'pointer')
    .style('backdrop-filter', 'blur(4px)').style('box-shadow', '0 2px 8px rgba(0,0,0,0.5)')
    .style('display', 'inline-flex').style('align-items', 'center').style('gap', '4px')
    .style('white-space', 'nowrap').html('+tag');

  addPill.on('click', function (event) {
    event.stopPropagation();
    const currentPill = d3.select(this);
    currentPill.html('');
    const input = currentPill.append('xhtml:input')
      .attr('type', 'text').attr('placeholder', 'tag...')
      .style('background', 'transparent').style('border', 'none').style('outline', 'none')
      .style('color', '#fff').style('font-size', '11px').style('font-weight', '600')
      .style('width', '40px').style('padding', '0');
    input.node().focus();
    input.on('input', function () {
      const val = this.value;
      const charLen = Math.max(1, val.length);
      this.style.width = (charLen * 7.5 + 24) + 'px';
    });
    input.on('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault(); e.stopPropagation();
        const tagVal = this.value.trim();
        if (tagVal) emit('add-node-tag', sha, tagVal);
      } else if (e.key === 'Escape') {
        e.stopPropagation();
        currentPill.html('+tag');
      }
    });
  });

  tags.forEach(t => {
    const tagPill = tagContainer.append('xhtml:div')
      .style('background', 'rgba(168, 85, 247, 0.92)').style('color', '#fff')
      .style('font-size', '11px').style('font-weight', '600').style('padding', '2px 8px')
      .style('border-radius', '10px').style('backdrop-filter', 'blur(4px)')
      .style('box-shadow', '0 2px 8px rgba(0,0,0,0.5)').style('display', 'inline-flex')
      .style('align-items', 'center').style('gap', '4px').style('white-space', 'nowrap')
      .html(`#${t}`);
    const delBtn = tagPill.append('xhtml:span')
      .style('cursor', 'pointer').style('margin-left', '4px').style('opacity', '0.7')
      .style('font-size', '10px').html('×');
    delBtn.on('click', (event) => {
      event.stopPropagation();
      emit('remove-node-tag', sha, t);
    });
  });

  // Pencil / note
  const hasNote = !!n.note;
  const pencilColor = hasNote ? '#c8a020' : '#445566';
  const pencilG = nodeSel.append('g').attr('cursor', 'pointer').attr('class', 'node-pencil');
  pencilG.append('circle')
    .attr('cx', -nodeW / 2 - 2).attr('cy', nodeH / 2 + 6).attr('r', 13)
    .style('fill', '#0f0f22').attr('stroke', pencilColor).attr('stroke-width', 1.5);
  pencilG.append('text')
    .attr('x', -nodeW / 2 - 2).attr('y', nodeH / 2 + 11)
    .attr('text-anchor', 'middle').attr('font-size', '16')
    .attr('fill', pencilColor).attr('pointer-events', 'none').text('✎');

  if (hasNote) {
    const nfo = nodeSel.append('foreignObject')
      .attr('x', -nodeW / 2).attr('y', nodeH / 2 + 22)
      .attr('width', nodeW).attr('height', 80);
    nfo.append('xhtml:div')
      .style('font-size', '14px').style('color', '#8a9ac0').style('line-height', '1.4')
      .style('overflow', 'hidden').style('max-height', '80px').style('padding', '0 6px')
      .style('word-break', 'break-word').style('white-space', 'pre-line').text(n.note);
  }

  pencilG.on('click', function (event) {
    event.stopPropagation();
    const rectEl = el.querySelector('rect.node-bg') || el;
    const rr = rectEl.getBoundingClientRect();
    const scale = savedZoom ? savedZoom.k : 1;
    emit('edit-note', {
      sha,
      x: Math.round(rr.left),
      y: Math.round(rr.bottom + 4),
      scale,
      text: n.note || '',
    });
  });
}

// -- jump-to-node camera control (ported from centerGraphOnNode(s)) --------

function centerGraphOnNodes(shas) {
  if (!shas || !shas.length || !svgRef.value || !zoomBehavior) return;
  const svgEl = svgRef.value;
  const width = svgEl.clientWidth || 800;
  const height = svgEl.clientHeight || 600;

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  let found = false;
  shas.forEach(sha => {
    const p = nodePosMap.get(sha);
    if (p) {
      found = true;
      minX = Math.min(minX, p.x - layoutMeta.nodeW / 2);
      maxX = Math.max(maxX, p.x + layoutMeta.nodeW / 2);
      minY = Math.min(minY, p.y - layoutMeta.nodeH / 2);
      maxY = Math.max(maxY, p.y + layoutMeta.nodeH / 2);
    }
  });
  if (!found) return;

  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;
  const k = (shas.length === 1)
    ? 1.0
    : Math.min(1.2, Math.max(0.4, Math.min((width - 100) / (maxX - minX || 1), (height - 100) / (maxY - minY || 1))));
  const tx = width / 2 - centerX * k;
  const ty = height / 2 - centerY * k;

  const newTransform = d3.zoomIdentity.translate(tx, ty).scale(k);
  savedZoom = newTransform;
  svgSelection.transition().duration(500).call(zoomBehavior.transform, newTransform);

  if (shas.length === 1) {
    svgSelection.selectAll('g.node').filter(d => d.data.sha === shas[0]).select('rect.node-bg')
      .transition().duration(300).style('stroke', '#ffcc00').style('stroke-width', '5px')
      .transition().duration(500).style('stroke', null).style('stroke-width', null);
  }
}

function centerGraphOnNode(sha) {
  centerGraphOnNodes([sha]);
}

function jumpToHead() {
  if (!props.graphData || !props.graphData.nodes) return;
  const headNode = props.graphData.nodes.find(n => n.is_head);
  if (headNode) centerGraphOnNode(headNode.sha);
}

function jumpToRoot() {
  if (!props.graphData || !props.graphData.nodes) return;
  const rootNode = [...props.graphData.nodes].sort((a, b) => a.when - b.when)[0];
  if (rootNode) centerGraphOnNode(rootNode.sha);
}

function jumpToDateRange(fromTs, toTs) {
  if (!props.graphData || !props.graphData.nodes) return 0;
  const matching = props.graphData.nodes.filter(n => n.when >= fromTs && n.when <= toTs);
  if (matching.length) centerGraphOnNodes(matching.map(n => n.sha));
  return matching.length;
}

defineExpose({ jumpToHead, jumpToRoot, jumpToDateRange, centerGraphOnNode });
</script>

<style scoped>
#graph-canvas {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: var(--bg);
}
</style>

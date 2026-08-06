<template>
  <div id="graph-canvas" ref="canvasContainer">
    <svg id="graph" ref="svgRef"></svg>
    <div
      v-if="autoSelectOnAdd"
      style="position:absolute;bottom:12px;left:12px;z-index:10;display:flex;align-items:center;gap:6px;background:var(--bg2);border:1px solid var(--border);border-radius:14px;padding:4px 10px;font-size:12px;color:var(--accent2);box-shadow:0 4px 12px rgba(0,0,0,0.4)"
    >
      <span>⚡ Auto-select on add enabled</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import * as d3 from 'd3';

const props = defineProps({
  graphData: Object,
  nodeStates: Object,
  nodeThumbnails: Object,
  nodeTags: Object,
  selectedNodeSha: String,
  selectedAlignments: Array,
  showMilestoneGuides: Boolean,
  graphBaseSort: String,
  graphBaseDir: String,
  autoSelectOnAdd: Boolean,
  getNodeEquivalenceKey: Function,
});

const emit = defineEmits([
  'select-node',
  'delete-node',
  'add-node-tag',
  'remove-node-tag',
]);

const canvasContainer = ref(null);
const svgRef = ref(null);

let zoomBehavior = null;
let svgSelection = null;
let containerGroup = null;

const nodeW = 160;
const nodeH = 100;
const ranksep = 60;
const nodesep = 40;

onMounted(() => {
  setupD3Svg();
  if (props.graphData && props.graphData.nodes) {
    renderGraph();
  }
});

watch(
  () => [
    props.graphData,
    props.selectedNodeSha,
    props.selectedAlignments,
    props.showMilestoneGuides,
    props.graphBaseSort,
    props.graphBaseDir,
    props.nodeTags,
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

  zoomBehavior = d3.zoom()
    .scaleExtent([0.1, 3])
    .on('zoom', (event) => {
      containerGroup.attr('transform', event.transform);
    });

  svgSelection.call(zoomBehavior);
}

function renderGraph() {
  if (!svgRef.value || !containerGroup || !props.graphData || !props.graphData.nodes) return;

  containerGroup.selectAll('*').remove();

  const nodes = props.graphData.nodes;
  if (!nodes.length) return;

  const childrenOf = new Map();
  const roots = [];

  nodes.forEach(n => {
    const p = n.parents && n.parents.length ? n.parents[0] : null;
    if (!p) { roots.push(n); return; }
    if (!childrenOf.has(p)) childrenOf.set(p, []);
    childrenOf.get(p).push(n);
  });

  const dir = props.graphBaseDir === 'asc' ? 1 : -1;
  const siblingCompare = (a, b) => (a.when - b.when) * dir;

  for (const arr of childrenOf.values()) arr.sort(siblingCompare);
  roots.sort(siblingCompare);

  function buildSimple(n) {
    return { sha: n.sha, node: n, children: (childrenOf.get(n.sha) || []).map(buildSimple) };
  }

  const synthetic = roots.length !== 1;
  const rootData = synthetic
    ? { sha: '__synthetic_root__', node: null, children: roots.map(buildSimple) }
    : buildSimple(roots[0]);

  const hierarchy = d3.hierarchy(rootData, d => d.children);
  d3.tree().nodeSize([nodeH + nodesep, nodeW + ranksep])(hierarchy);

  const realNodes = hierarchy.descendants().filter(d => !d.data.isDummy && !(synthetic && d.depth === 0));

  const posMap = new Map();
  let minX = Infinity, minY = Infinity;
  realNodes.forEach(d => {
    const screenX = d.y, screenY = d.x;
    minX = Math.min(minX, screenX);
    minY = Math.min(minY, screenY);
    posMap.set(d.data.sha, { rawX: screenX, rawY: screenY });
  });

  const shiftX = -(minX - nodeW / 2) + 40;
  const shiftY = -(minY - nodeH / 2) + 40;
  posMap.forEach(p => {
    p.x = p.rawX + shiftX;
    p.y = p.rawY + shiftY;
  });

  // Render Edges
  const edgeG = containerGroup.append('g').attr('class', 'edges');
  realNodes.forEach(d => {
    if (d.parent && d.parent.data.sha && !d.parent.data.isDummy && !(synthetic && d.parent.depth === 0)) {
      const src = posMap.get(d.parent.data.sha);
      const tgt = posMap.get(d.data.sha);
      if (src && tgt) {
        const linkPath = d3.linkHorizontal()
          .x(p => p.x)
          .y(p => p.y)({
            source: { x: src.x + nodeW / 2, y: src.y },
            target: { x: tgt.x - nodeW / 2, y: tgt.y },
          });

        edgeG.append('path')
          .attr('d', linkPath)
          .attr('stroke', '#2a3a6a')
          .attr('stroke-width', 2)
          .attr('fill', 'none');
      }
    }
  });

  // Render Nodes
  const nodeG = containerGroup.append('g').attr('class', 'nodes');
  realNodes.forEach(d => {
    const n = d.data.node;
    const pos = posMap.get(n.sha);

    const nodeGroup = nodeG.append('g')
      .attr('class', `node ${n.is_head ? 'head' : ''} ${n.sha === props.selectedNodeSha ? 'selected' : ''}`)
      .attr('transform', `translate(${pos.x}, ${pos.y})`)
      .style('cursor', 'pointer')
      .on('click', (event) => {
        event.stopPropagation();
        emit('select-node', n.sha);
      });

    // Node Card BG
    nodeGroup.append('rect')
      .attr('class', 'node-bg')
      .attr('x', -nodeW / 2)
      .attr('y', -nodeH / 2)
      .attr('width', nodeW)
      .attr('height', nodeH)
      .attr('rx', 6)
      .attr('fill', '#141428')
      .attr('stroke', n.sha === props.selectedNodeSha ? '#50a0ff' : '#2a3060')
      .attr('stroke-width', n.sha === props.selectedNodeSha ? 3 : 2);

    // Subject Header Text
    nodeGroup.append('text')
      .attr('x', -nodeW / 2 + 10)
      .attr('y', -nodeH / 2 + 20)
      .attr('fill', '#8ab4f8')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .text(n.subject || n.sha.slice(0, 7));

    // Left-edge Tag Manager ForeignObject Overlay
    const tagFo = nodeGroup.append('foreignObject')
      .attr('class', 'node-tag-manager')
      .attr('x', -nodeW / 2 - 10)
      .attr('y', -nodeH / 2 + 23)
      .attr('width', 100)
      .attr('height', 80)
      .style('overflow', 'visible');

    const foDiv = tagFo.append('xhtml:div')
      .style('display', 'flex')
      .style('flex-direction', 'column')
      .style('gap', '3px')
      .style('align-items', 'flex-start');

    // Render +tag pill
    const addPill = foDiv.append('xhtml:div')
      .attr('class', 'tag-pill add-tag')
      .style('background', '#1e2248')
      .style('border', '1px solid #6080e8')
      .style('border-radius', '10px')
      .style('padding', '1px 6px')
      .style('font-size', '10px')
      .style('color', '#8ab4f8')
      .style('cursor', 'pointer')
      .html('+tag');

    addPill.on('click', (event) => {
      event.stopPropagation();
      addPill.style('display', 'none');
      const input = foDiv.append('xhtml:input')
        .attr('type', 'text')
        .style('width', '50px')
        .style('background', '#0a0a14')
        .style('border', '1px solid #6080e8')
        .style('border-radius', '10px')
        .style('color', '#fff')
        .style('font-size', '10px')
        .style('padding', '1px 5px')
        .style('outline', 'none');

      input.node().focus();
      input.on('keydown', (e) => {
        if (e.key === 'Enter') {
          const val = input.node().value.trim();
          if (val) emit('add-node-tag', n.sha, val);
          input.remove();
          addPill.style('display', 'inline-block');
        }
      });
    });

    // Render stacked tags
    const tags = (props.nodeTags && props.nodeTags[n.sha]) || [];
    tags.forEach(t => {
      const tagPill = foDiv.append('xhtml:div')
        .style('background', '#142040')
        .style('border', '1px solid #2a3a8a')
        .style('border-radius', '10px')
        .style('padding', '1px 6px')
        .style('font-size', '10px')
        .style('color', '#8ab4f8')
        .style('display', 'inline-flex')
        .style('align-items', 'center')
        .style('gap', '3px')
        .html(`<span>#${t}</span><span style="cursor:pointer;opacity:0.6">×</span>`);

      tagPill.select('span:last-child').on('click', (event) => {
        event.stopPropagation();
        emit('remove-node-tag', n.sha, t);
      });
    });
  });
}
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

import { ref, computed } from 'vue';

export function useAlignments() {
  const selectedAlignments = ref([]);
  const showAlignmentPopover = ref(false);
  const showMilestoneGuides = ref(true);

  const alignmentButtonLabel = computed(() => {
    if (!selectedAlignments.value || !selectedAlignments.value.length) {
      return 'None (tree depth)';
    }
    if (selectedAlignments.value.length === 1) {
      return selectedAlignments.value[0];
    }
    return `${selectedAlignments.value.length} Active Alignments`;
  });

  function isAlignmentSelected(item) {
    return selectedAlignments.value.includes(item);
  }

  function toggleAlignment(item, onChange) {
    const idx = selectedAlignments.value.indexOf(item);
    if (idx === -1) {
      selectedAlignments.value.push(item);
    } else {
      selectedAlignments.value.splice(idx, 1);
    }
    if (onChange) onChange();
  }

  function clearAlignments(onChange) {
    selectedAlignments.value = [];
    showAlignmentPopover.value = false;
    if (onChange) onChange();
  }

  function getNodeEquivalenceKey(node, vars, nodeStates, nodeTagsMap) {
    if (!node) return null;
    if (!selectedAlignments.value || !selectedAlignments.value.length) return null;

    const sha = node.sha;
    const parentSha = node.parents && node.parents[0];
    const parentVars = parentSha ? (nodeStates[parentSha] || null) : null;
    const nodeTags = (nodeTagsMap && nodeTagsMap[sha]) || [];

    const parts = [];

    for (const item of selectedAlignments.value) {
      if (item.startsWith('#')) {
        const rawTag = item.slice(1).toLowerCase();
        if (nodeTags.map(t => t.toLowerCase()).includes(rawTag)) {
          parts.push('#' + rawTag);
        }
      } else {
        // Story variable
        if (vars && vars[item] != null && String(vars[item]).trim() !== '') {
          const val = vars[item];
          const pVal = parentVars ? parentVars[item] : undefined;
          const isIncrease = !parentVars || pVal === undefined || pVal !== val;
          if (isIncrease) {
            parts.push(`${item}: ${val}`);
          }
        }
      }
    }

    return parts.length ? parts : null;
  }

  return {
    selectedAlignments,
    showAlignmentPopover,
    showMilestoneGuides,
    alignmentButtonLabel,
    isAlignmentSelected,
    toggleAlignment,
    clearAlignments,
    getNodeEquivalenceKey,
  };
}

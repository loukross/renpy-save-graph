import { ref } from 'vue';

export function useTags() {
  const nodeTags = ref({});
  const allSpaceTags = ref([]);

  // Split so a caller can commit tags in the same tick as the graph.
  async function fetchTags(spaceId, slotName) {
    if (!spaceId || !slotName) return null;
    try {
      const resp = await fetch(`/api/spaces/${spaceId}/slots/${slotName}/tags`);
      return resp.ok ? await resp.json() : null;
    } catch (e) {
      console.error('Error loading tags:', e);
      return null;
    }
  }

  function commitTags(data) {
    if (!data) return;
    nodeTags.value = data.tags || {};
    allSpaceTags.value = data.all_tags || [];
  }

  async function loadTags(spaceId, slotName) {
    commitTags(await fetchTags(spaceId, slotName));
  }

  async function addNodeTag(spaceId, slotName, sha, tag, onComplete) {
    if (!tag || !spaceId || !slotName) return;
    try {
      await fetch(`/api/spaces/${spaceId}/slots/${slotName}/nodes/${sha}/tags`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag }),
      });
      await loadTags(spaceId, slotName);
      if (onComplete) onComplete();
    } catch (e) {
      console.error('Error adding tag:', e);
    }
  }

  async function removeNodeTag(spaceId, slotName, sha, tag, onComplete) {
    if (!tag || !spaceId || !slotName) return;
    try {
      await fetch(`/api/spaces/${spaceId}/slots/${slotName}/nodes/${sha}/tags/${encodeURIComponent(tag)}`, {
        method: 'DELETE',
      });
      await loadTags(spaceId, slotName);
      if (onComplete) onComplete();
    } catch (e) {
      console.error('Error removing tag:', e);
    }
  }

  return {
    nodeTags,
    allSpaceTags,
    fetchTags,
    commitTags,
    loadTags,
    addNodeTag,
    removeNodeTag,
  };
}

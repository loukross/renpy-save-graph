import { ref } from 'vue';

export function useTags() {
  const nodeTags = ref({});
  const allSpaceTags = ref([]);

  async function loadTags(spaceId, slotName) {
    if (!spaceId || !slotName) return;
    try {
      const resp = await fetch(`/api/spaces/${spaceId}/slots/${slotName}/tags`);
      if (!resp.ok) return;
      const data = await resp.json();
      nodeTags.value = data.tags || {};
      allSpaceTags.value = data.all_tags || [];
    } catch (e) {
      console.error('Error loading tags:', e);
    }
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
    loadTags,
    addNodeTag,
    removeNodeTag,
  };
}

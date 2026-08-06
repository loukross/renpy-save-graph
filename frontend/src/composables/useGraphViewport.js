/**
 * Where the graph camera sits, and when it may move on its own.
 *
 *   - First time a space+slot graph is shown: fit it to the screen.
 *   - Every later render of it: restore where the user left the view.
 *   - Panning, zooming, fitting and centring all update what gets restored.
 *
 * Module scope, not per instance: GraphCanvas is keyed on space+slot, so Vue
 * remounts it whenever either changes.  In memory only; a reload starts fresh.
 */
const saved = new Map();

export function useGraphViewport() {
  let key = null;
  let current = null;

  return {
    /** The live transform, or null before this graph's first render. */
    get current() {
      return current;
    },

    /** Record `transform` as the view to restore for the current graph. */
    remember(transform) {
      current = transform;
      if (key) saved.set(key, transform);
    },

    /** `{action: 'fit'}` the first time a graph is seen, else `{action: 'restore', transform}`. */
    plan(spaceId, slotName) {
      const next = `${spaceId}::${slotName}`;
      if (next !== key) {
        key = next;
        current = saved.get(next) || null;
      }
      return current ? { action: 'restore', transform: current } : { action: 'fit' };
    },
  };
}

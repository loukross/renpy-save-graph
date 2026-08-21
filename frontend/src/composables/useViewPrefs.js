import { watch, toValue } from 'vue';

const KEY = 'renpy_save_graph_view_prefs';

function readAll() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '{}');
  } catch {
    return {};
  }
}

/**
 * Remember the graph view's alignment, sort and filter choices per space.
 *
 * Kept in localStorage rather than the space config: these are view state, not
 * something worth writing to the shared config file (and PATCHing on every
 * checkbox click). They're keyed by space because they name that space's own
 * variables and tags — restoring one space's filter onto another would just
 * evaluate against undefined.
 *
 * `fields` maps a stored name to the ref holding it.
 */
export function useViewPrefs(spaceId, fields) {
  const names = Object.keys(fields);
  const clone = (v) => JSON.parse(JSON.stringify(v));
  // What an unvisited space should look like. Restoring has to reset as well as
  // apply — switching spaces mid-session would otherwise leave the previous
  // space's alignment and filter in place, evaluating against variables the new
  // space doesn't have.
  const defaults = clone(Object.fromEntries(names.map(n => [n, fields[n].value])));

  function restore(id) {
    const saved = readAll()[id] || {};
    for (const name of names) {
      // Cloned per assignment: selectedAlignments is mutated in place, and
      // handing out the defaults object itself would let a toggle corrupt it.
      fields[name].value = clone(saved[name] !== undefined ? saved[name] : defaults[name]);
    }
  }

  function save() {
    const id = toValue(spaceId);
    if (!id) return;
    const all = readAll();
    all[id] = Object.fromEntries(names.map(n => [n, fields[n].value]));
    try {
      localStorage.setItem(KEY, JSON.stringify(all));
    } catch {
      // Private mode or a full quota — losing view state is not worth throwing.
    }
  }

  // deep: selectedAlignments is mutated in place by its toggles.
  watch(names.map(n => fields[n]), save, { deep: true });

  return { restore };
}

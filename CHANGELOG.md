# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Bug Fixes

- Remove redundant _DAG_CACHE memory layer (cdebdc8)
- Prevent branch overwriting on restore and log all slot fork branches (80ef5b3)
- Use a PAT for the changelog PR to avoid required workflow approval (ad0b8c6)
- Build frontend before running tests; add Route Targets help & tour step (dc6b063)
- Keep the viewport where the user left it (745f7ef)
- Keep per-node metadata across rebases and clones (3eb151a)
- Adopt a clone's root instead of minting a second one (b07a701)

### Documentation

- Add usage note against sharing save-graph libraries (a7000af)
- Link the licence relatively (bd8577c)

### Features

- Add multi-alignment popover box and game-space tag management (a72b520)
- Stack multi-item milestone guideline labels vertically (bf48864)
- Add example space reset API and interactive tour node tag step (37b898e)
- Exclude args and kwargs store variables during save extraction (2b3f062)
- Finish Vue frontend, add Route Targets, fix save-extraction crash (7c635bf)
- Add Duplicate space button, inline config fields, jump to latest save, and auto-fit graph viewport (76dce60)
- Watch additional saves directories (9b0bae4)
- Add "Hide removed" toggle to the variable diff (2bd599e)
- Make a library carry its own tags and settings (d2d8b24)
- Import a cloned library (a4a8664)

### Miscellaneous

- Add automated CHANGELOG.md generation and commit-msg hook (131edda)
- Add Dependabot, CodeQL, and release provenance workflows (405be19)
- Reduce test matrix to Python 3.11, route changelog through a PR (46b5dd4)
- Update author and repo links for loukross (b60191a)
- Update CHANGELOG links to loukross (792eb29)

### Other

- Initial release: Ren'Py Save Graph (0021380)
- Update README.md with game-agnostic Usage section based on Reddit post and remove Features section (e4de396)
- Add example game space, GitHub asset endpoint, and about modal; extend interactive tour (acb2bdd)
- Add demo video link to README Usage section (7430486)
- Replace dagre-d3 layout with d3.tree() and add viewport-based decoration (51f875e)
- Update README with save slot and quicksave details (3660056)
- Replace monotonic_vars with a lineage validity check expression (3ed8aba)
- Merge branch 'main' of github.com:loukross/renpy-save-graph (ddba734)
- Merge branch 'main' of github.com:loukross/renpy-save-graph (dd886d4)

### Performance

- Stop redrawing the whole graph, and store save dirs locally (ba6b1c0)

### Refactor

- Extract monolithic ui.html into Vue 3 Single File Components with Vite build (91838d9)

### Testing

- Use auto-waiting assertions and repair two vacuous tests (c3a3d80)



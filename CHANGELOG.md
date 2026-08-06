# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Bug Fixes

- Remove redundant _DAG_CACHE memory layer (09b3bbf)
- Prevent branch overwriting on restore and log all slot fork branches (7f541d5)
- Use a PAT for the changelog PR to avoid required workflow approval (fd0cf11)
- Build frontend before running tests; add Route Targets help & tour step (c729d56)

### Documentation

- Add usage note against sharing save-graph libraries (21b98e1)

### Features

- Add multi-alignment popover box and game-space tag management (14cb898)
- Stack multi-item milestone guideline labels vertically (2108684)
- Add example space reset API and interactive tour node tag step (44626cf)
- Exclude args and kwargs store variables during save extraction (8412de3)
- Finish Vue frontend, add Route Targets, fix save-extraction crash (b7056f5)

### Miscellaneous

- Add automated CHANGELOG.md generation and commit-msg hook (f7792e2)
- Add Dependabot, CodeQL, and release provenance workflows (953f9f0)
- Reduce test matrix to Python 3.11, route changelog through a PR (57bd42f)

### Other

- Initial release: Ren'Py Save Graph (623e3c0)
- Update README.md with game-agnostic Usage section based on Reddit post and remove Features section (e68b42c)
- Add example game space, GitHub asset endpoint, and about modal; extend interactive tour (9234c5e)
- Add demo video link to README Usage section (7948820)
- Replace dagre-d3 layout with d3.tree() and add viewport-based decoration (ccd9a97)
- Update README with save slot and quicksave details (3b9cfa0)
- Replace monotonic_vars with a lineage validity check expression (793637c)
- Merge branch 'main' of github.com:lucjross/renpy-save-graph (16d97e4)
- Merge branch 'main' of github.com:lucjross/renpy-save-graph (4ec3e83)

### Refactor

- Extract monolithic ui.html into Vue 3 Single File Components with Vite build (116272e)



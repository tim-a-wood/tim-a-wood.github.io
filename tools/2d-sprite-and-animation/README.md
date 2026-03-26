# Sprite Workbench Layout

This folder now separates the live workbench from historical planning material.

## Live app

- `index.html`
  - main workbench entrypoint
- `app/`
  - runtime JS modules and the integrated product-shell stylesheet
- `assets/`
  - static visual assets used by the workbench shell
- `projects-data/`
  - local-first project storage, exports, and workbench settings
- `workflows/`
  - Comfy/authoring workflow templates consumed by the server
- `requirements.txt`
  - optional Python dependencies for local workbench integrations
- `stage-maturity.json`
  - server-consumed workflow maturity metadata

## Workbench docs

- `docs/`
  - current workbench reference docs
- `docs/archive/`
  - historical specs, handover notes, and retired planning material
- `docs/archive/design-options/`
  - static design explorations kept for reference only

## Notes

- `product-prototype.html` was removed after its shell was merged into `index.html`.
- The runtime app should only reference files in `app/`, `assets/`, `projects-data/`, `workflows/`, and `docs/`.

# Whetstone field guide

An explanatory, offline-capable product and operator guide with ten original SVG architecture plates. The promoted specification family and public contracts retain authority. This site does not run Whetstone or contact model providers.

Open `index.html` directly in a browser for the complete offline guide, including local source links. Keep the surrounding repository in place. No build, installation, CDN, or network connection is needed.

For an interface preview that serves only public documentation assets:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory docs/site
```

Open [the local preview](http://127.0.0.1:8766/). This restricted preview does not serve repository source files; use the direct-file guide for offline source navigation. Published source links instead point to GitHub at the deployment commit.

## Contents and interactions

Eight chapters cover a model-free first run, live configuration, workflow choice, intake, seed-spec assessment, both phases, focused rechecks, evidence interpretation, recovery, strop, decomposition, commands and capability status. The ten plates cover context, runtime, concepts, phases, preparation, refinement, feedback, lineage, source ownership and execution failure boundaries.

Search with Command/Ctrl K. Section and diagram URLs are deep links. Commands are copyable. Five Cortext1 themes are remembered in browser storage where available; `?theme=inverted` (or another theme key) overrides the remembered selection.

Expand any plate to access a ten-diagram title picker, zoom, fit, scrolling, tracing, export, and native fullscreen. Switching resets fit and scrolling while retaining independent trace settings. Inline and expanded tracing share state throughout the page session, including across closing/reopening and fullscreen. Traces are illustrative; reduced motion produces static highlights. Browser fullscreen denial or unavailability produces an explanation while keeping the interface usable.

Dense inline SVGs scroll horizontally on small screens. Expanded Fit shows the whole plate; zoom for readable detail. SVG export resolves the chosen theme and embeds fonts. The export font bundle loads only when requested and works from disk.

## Authority and research baseline

Researched against the local package 0.1.0 working tree on 2026-09-08, with unpublished preservation development explicitly distinguished from the published CLI. Sources include the actual CLI, Operator Quickstart, promoted spec family, contracts, runtime modules, and executable fixture.

The guide explicitly distinguishes implemented public workflows, developer preservation components, inactive candidate-safe design, and exploratory/future ideas. Public preservation bridge activation is unavailable in the publishing revision. The optional source-baseline check in strop requires `--expected-source-hash`; the guide does not present it as automatic.

The Spine field guide supplied the interaction and verification foundation, plus reusable SVG primitives. All Whetstone product prose and ten diagram compositions were authored for this system. Surface tokens, typography and five themes follow the Cortext1 brand specification 1.1.0. Diagram relationship colors use darker companion colors in the inverted theme for readability; status tokens retain their canonical values.

Syne, Inter, and JetBrains Mono are bundled with their OFL licenses under `assets/fonts/`. Regenerate the lazy export bundle after a font change with:

```sh
node docs/site/generate-font-data.mjs
```

## Publishing

The public guide is hosted at [calebini.github.io/whetstone](https://calebini.github.io/whetstone/). The repository README links to this guide, with this folder retained for offline use and verification.

`.github/workflows/docs.yml` is manual only. It requires `public_content_approved=true`, the full reviewed SHA equal to the dispatched commit, and the main branch. It packages an explicit allowlist of 16 public HTML/CSS/JS/font/icon/license assets plus `.nojekyll`; no source specs, run roots, telemetry, screenshots, tests, or other repository files are uploaded. Source targets are validated before packaging and rewritten to the deployment SHA. Local files are unchanged.

Pages uses GitHub Actions. For an approved update, commit the documentation changes on main and dispatch this workflow with that full SHA as `reviewed_revision` and `public_content_approved=true`. Ensure every cited source is present in that commit. The first publication was authorized by the content owner on 2026-09-08; unrelated local preservation implementation commits are excluded from the documentation release.

To inspect packaging locally without deploying:

```sh
node --test docs/site/build-pages.test.mjs
node docs/site/build-pages.mjs /tmp/whetstone-pages-preview
```

Choose a new output directory; the packager refuses to overwrite one. By default it uses the current HEAD SHA. A local package made from uncommitted changes is a packaging preview, not proof that every cited file exists at HEAD on GitHub.

## Verification

Production has no npm dependencies. Browser tests use externally installed `playwright-core`, Chrome, and optional `axe-core`:

```sh
npm install --prefix /tmp/whetstone-docs-qa playwright-core axe-core --no-save
export WHETSTONE_PLAYWRIGHT_PATH=/tmp/whetstone-docs-qa/node_modules/playwright-core
export WHETSTONE_AXE_PATH=/tmp/whetstone-docs-qa/node_modules/axe-core/axe.min.js
node docs/site/verify.mjs
node docs/site/verify-flows.mjs
node docs/site/verify-fullscreen.mjs
node docs/site/verify-exports.mjs
node docs/site/verify-content.mjs
```

Start the asset-only preview above first. `WHETSTONE_DOCS_URL` overrides its URL; `WHETSTONE_CHROME_PATH` selects a Chromium executable. QA outputs are ignored and excluded from publication.

- `verify.mjs`: overview plus 19 routes, source file targets, desktop/narrow overflow, SVG label bounds, navigation, deep links, search, copy, expansion, zoom, themes, direct-file access, and accessibility.
- `verify-flows.mjs`: all ten moving traces and picker options, shared and independent state, fullscreen switching, reopening, reduced-motion changes, and controls at 741, 390 and 320 pixels.
- `verify-fullscreen.mjs`: real native entry/exit, top-layer visibility, full-display fit, external exits, and blocked/unavailable API fallbacks.
- `verify-exports.mjs`: all 50 theme/diagram exports, standalone embedded-font rendering, picker-driven export, persisted themes, actual inline movement, real offline source navigation, offline export, and visual proof sheets.
- `verify-content.mjs`: rendered shell syntax and internal deep-link targets without invoking models.
- `build-pages.test.mjs`: exact publication allowlist, immutable source URLs, local-link preservation, and refusal of unsafe metadata or an existing destination.

The documented deterministic first run was executed successfully: six fixture rounds and a `CONVERGED` response. This checks documentation examples and UI behavior, not live-model quality or a new qualification of the Whetstone runtime.

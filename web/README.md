# MTG Draft Assistant — Web UI

React + Vite + TypeScript frontend. Hand-built (no component library). The interface
**wears the deck's colors**: accents are driven by the archetype agent's `committed_colors`.

## Run it — one command

From the repo root:
```bash
uv run mtg-draft-app
```
That builds the UI the first time, starts one server, and opens your browser at
**http://localhost:8000**. No env vars, no second terminal, no Node running after the build.

It boots on the **free mock backend**. To analyze a real screenshot, flip **"Use real models"**
in the top-right (only enabled when `ANTHROPIC_API_KEY` is set in `.env`) and upload a shot.
The demo draft is always free. Nothing spends tokens unless you toggle real models on.

## Using it
- **Try the demo draft** — runs `/api/demo` (canned R/B draft, always free, no screenshot).
- **Drop / paste / choose** an Arena screenshot — runs `/api/recommend`. With "Use real models"
  on, this is the live vision → archetype → evaluation → synthesis pipeline against the Marvel
  Super Heroes (`msh`) card DB; off, it returns the mock result regardless of the image.
- Expand **Agent trace** to see each agent's intermediate output, and **Cost & model routing**
  to see the Haiku/Sonnet split and token spend.

## Dev mode (hot reload)

For frontend work you can still run the two-process setup with Vite's hot reload:
```bash
# terminal 1 (repo root) — API only
uv run uvicorn mtg_draft_assistant.api:app --reload --port 8000
# terminal 2 (web/) — Vite dev server, proxies /api to :8000
cd web && npm install && npm run dev   # http://localhost:5173
```

## Notes
- First `npm install` on newer npm may skip esbuild's postinstall (a security default). If the
  dev server complains about a missing esbuild binary, run `npm rebuild esbuild` once.
- `npm run build` type-checks (strict) and produces a production bundle in `dist/`.

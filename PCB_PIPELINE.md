# From design to PCB — pipeline (manual-editable + AI-designable)

Goal: turn the tscircuit design into a real board where **both** a human can hand-edit the layout
**and** the AI can lay it out using good practices. Researched Sept 2026 (three parallel councils).

## The honest capability picture first
AI in 2026 is a **routing-and-cleanup assistant, not an autonomous board designer.**
- PCB-Bench (the actual layout benchmark) verdict: current LLMs "cannot yet generate
  manufacturable layouts." (The EEBench "69%" number people cite is a *circuit/SPICE* score, not
  layout — don't be fooled.)
- Realistic split: **human** places the major blocks and routes the hard nets (RF antenna, USB
  differential pair, high-current/power); **AI** autoroutes the remaining ~70–80% of tedious
  signal nets and iterates against DRC. **Human review before fabrication is non-negotiable.**
- **Big break for us:** we use *modules* (XIAO, driver, MP3, OLED). The antenna and USB live
  *inside* the XIAO, already done — so the two things AI is worst at don't exist on our board.
  Our PCB is just module footprints + a few passives + power/motor traces. That's squarely in
  "AI does a solid first pass, human refines" territory.

## "Good practices" are enforced by encoded rules, not by AI judgment
Trustworthiness comes from a rule-gate, the same pattern as our schematic verification loop:
- **Net classes** — trace width by current, clearance, via size (wide motor traces, thin signals).
- **Custom design rules** (`.kicad_dru`) — thermal vias under the motor driver, clearances,
  copper-pour rules, keep-outs.
- **Copper pours / ground plane.**
- **A DRC gate that blocks on any violation** — `kicad-cli pcb drc --exit-code-violations`
  (headless, reads the sibling `.kicad_dru`), run on every change, human or AI. This is what makes
  an AI-produced (or human-produced) layout safe to trust *after* the gate passes.

## Two pipelines (pick by board complexity)

### Pipeline A — all-in-tscircuit  ← recommended for the smart bin
- Schematic stays as tscircuit **code** (source of truth — what we already have).
- **Layout, both editors, name-keyed so they never clobber each other:**
  - AI writes layout props (`pcbX`/`pcbY`/`pcbRotation`/`layer`) + pours directly in `board.tsx`
    (diffable, reviewable).
  - Human drags parts in tscircuit's runframe GUI → saved to `manual-edits.json`, imported via
    `<board manualEdits={...}>`. Survives schematic edits as long as component names are stable.
  - **This is the only setup where AI and human layout edits both round-trip cleanly** — the one
    hard requirement KiCad hand-editing cannot meet.
- Autoroute with the knobs pinned (trace thickness, ViaGrid, `allowBlindAndBuriedVias=false`,
  ground pour) → DRC-check **every** export → order via tscircuit → JLCPCB (it also emits BOM +
  pick-and-place).
- Caveat: tscircuit's autorouter is **beta and can emit shorts / unfabricable vias** — so DRC
  every time and eyeball the Gerbers. Fine for a simple module board like ours; don't trust it
  unattended.

### Pipeline B — tscircuit → KiCad handoff  (for a complex/high-reliability board later)
- `tsci export` a KiCad project zip (schematic + PCB) → open in **KiCad**.
- AI first pass via `pcbnew` Python scripting (or kicad-tools / kicad-mcp-pro): placement, net
  classes, pours. Autoroute via **Freerouting** (export `.dsn` → route → import `.ses`).
- Gate with `kicad-cli pcb drc` + `.kicad_dru`; **kicad-happy** for an AI design-review pass.
- Human refines in the KiCad GUI. **Coexistence is turn-based / single-writer** (git as the
  handoff; never co-edit the same `.kicad_pcb` — it doesn't 3-way-merge).
- Trade-off: **KiCad is a one-way terminal.** Re-exporting from tscircuit overwrites it, so later
  schematic changes mean redoing layout there. You gain a real routing GUI + stronger DRC; you
  lose the clean code round-trip.

## Recommendation for the smart bin
Start with **Pipeline A**. The board is module-level (no RF/USB routing — the AI weak spots are
absent), it's the only path that satisfies "both AI and human can edit the layout," and it orders
in one step. Move to Pipeline B only if the board grows complex or you want KiCad's manual routing.

Bonus for the enclosure: `tsci export -f step` gives a 3D board model to design the Fusion 360
cover around — the board→case→order goal in one toolchain.

## Do we even need a custom PCB?
For first prototype, no — the modules breadboard/perfboard directly. A custom PCB is worth it once
the wiring works and you want it neat inside the bin. Same tscircuit design feeds both.

## Suggested next steps
1. First AI layout pass in tscircuit: place the modules, ground pour, pin trace widths, autoroute,
   DRC — deliver the board SVG + Gerbers for review.
2. Add PCB net classes + a `.kicad_dru` (motor trace width, thermal vias, clearances) to the repo.
3. Export STEP for the Fusion 360 enclosure.
(None of this blocks firmware — that can proceed in parallel.)

## Sources
- PCB-Bench (layout benchmark): https://github.com/digailab/PCB-Bench
- EEBench is not a layout benchmark: https://explainx.ai/blog/eebench-ai-circuit-board-design-benchmark-2026
- Hackaday, can AI design PCBs: https://hackaday.com/2026/09/05/can-ai-now-design-pcbs-that-just-work/
- Flux AI auto-layout (80/20 human/AI): https://www.flux.ai/p/blog/ai-auto-layout-winter-update
- tscircuit export docs: https://docs.tscircuit.com/command-line/tsci-export
- tscircuit manual-edits round-trip: https://docs.tscircuit.com/guides/tscircuit-essentials/manual-edits
- tscircuit KiCad exporter: https://blog.tscircuit.com/p/kicad-integration-parsing-and-exporting
- Freerouting: https://github.com/freerouting/freerouting
- kicad-cli DRC / rules: https://docs.kicad.org/master/en/cli/cli.html
- kicad-tools (agent-side DRC gate): https://github.com/rjwalters/kicad-tools
- kicad-happy (AI review): https://github.com/aklofas/kicad-happy

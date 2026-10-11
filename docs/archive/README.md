# Archive

Done or superseded, kept so nothing is lost. **None of it describes the bin as it is now** — the current
picture is [`CLAUDE.md`](../../CLAUDE.md), [`HANDOVER.md`](../../HANDOVER.md) and the code. Paths and names
inside these files are as they were when they were written; they were moved here whole, not edited.
Archived 2026-10-11 (the PO's cleanup: "no old files or docs that are stale or go in a different direction").

| File | What it was | Why it is here |
| --- | --- | --- |
| `BOM.md` | The first bill of materials, for the XIAO / DFR0534 / OLED / TB6612 design | Superseded by `SHOPPING.md` (what to buy) and the `bom.csv` inside `board-gerbers.zip` (what the board orders) |
| `PCB_PIPELINE.md` | Research on the tscircuit-versus-KiCad pipeline and what AI can lay out | Done: its recommendation (the tscircuit route) is what `board.tsx` uses, and its "suggested next steps" became the checks in `make check` |
| `FIRMWARE_PLAN.md` | The v2 firmware design note and its two audits | Done: the firmware it describes is built; the code, starting at the tour in `smartbin/__init__.py`, is the reference. The file called itself historical already |
| `FORMATS.md` | Research on design formats and the plan for the Wokwi converter | Done: the converter is built (`tools/circuit-to-wokwi`, moving to spark as P32b / bin #6); the KiCad and STEP ideas belong to spark's check epic and bin B23 |
| `board-v1-tb6612.tsx` | The v1 board: XIAO ESP32-C6, TB6612 driver, OLED | Superseded by `board.tsx` (v4). Imports `XIAO-ESP32-C6-SMD.tsx` beside it |
| `XIAO-ESP32-C6-SMD.tsx` | The XIAO footprint the v1 board used | Only the v1 board imports it; the brain is now the FireBeetle 2 ESP32-S3 |
| `arduino-v1/` | The first firmware: an Arduino sketch for the XIAO, TB6612, OLED and a UART MP3 module | Superseded by the MicroPython firmware in `firmware/micropython/`. The state machine's shape came from it; nothing else does |

Deleted rather than archived: `_url.txt`, an empty file from the first commit (git history has it).

Still at the root on purpose, until their cards close: `board-v3-dfr0534.tsx` (B29, #23) and the Wokwi chips and
`tools/circuit-to-wokwi/ARCHITECTURE.md` (P32b, #6).

/**
 * Where parts sit in the diagram.
 *
 * Deliberately dumb, and that is the design: generated files have to be **diffable**. A layout
 * engine (elkjs can do this properly, with fixed port positions) would move everything whenever
 * one pin changed, and the diff would be unreadable. A deterministic heuristic moves one part.
 *
 * The board sits at the origin; everything else stacks in a column either side of it, in the
 * order the mapping table prefers, snapped to Wokwi's grid.
 *
 * `Placer` is an interface so a better implementation can be dropped in without the emitter
 * noticing — and `merge.ts` means a human's own positions win over either of them.
 */

import { GRID_PX, sizeOf, snapToGrid } from "./geometry";

export interface Placement {
  top: number;
  left: number;
}

export interface PlacedPart {
  id: string;
  wokwiType: string;
  side: "left" | "right";
}

export interface Placer {
  place(parts: PlacedPart[]): Map<string, Placement>;
}

/** Gap between stacked parts, and between a column and the board. */
const PART_GAP_PX = GRID_PX * 4;
const COLUMN_GAP_PX = GRID_PX * 12;

export class ColumnPlacer implements Placer {
  constructor(private boardType = "board-xiao-esp32-c6") {}

  place(parts: PlacedPart[]): Map<string, Placement> {
    const placements = new Map<string, Placement>();
    const board = parts.find((part) => part.wokwiType === this.boardType);
    const boardSize = sizeOf(this.boardType);

    if (board) placements.set(board.id, { top: 0, left: 0 });

    const columns = {
      left: { x: -(COLUMN_GAP_PX + sizeOf("board-ssd1306").width), y: 0 },
      right: { x: boardSize.width + COLUMN_GAP_PX, y: 0 },
    };

    for (const part of parts) {
      if (part === board) continue;
      const column = columns[part.side];
      placements.set(part.id, {
        left: snapToGrid(column.x),
        top: snapToGrid(column.y),
      });
      column.y += sizeOf(part.wokwiType).height + PART_GAP_PX;
    }

    return placements;
  }
}

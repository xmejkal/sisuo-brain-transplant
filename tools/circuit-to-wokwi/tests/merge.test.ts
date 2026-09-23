import { describe, expect, test } from "bun:test";

import type { WokwiDiagram } from "../lib/emitters/wokwi";
import { HAND_ADDED_ATTR, mergeWithExisting } from "../lib/merge";

function diagram(overrides: Partial<WokwiDiagram> = {}): WokwiDiagram {
  return {
    version: 1,
    author: "test",
    editor: "wokwi",
    parts: [{ type: "board-xiao-esp32-c6", id: "xiao", top: 0, left: 0, attrs: {} }],
    connections: [["xiao:D4", "oled:SDA", "green", []]],
    ...overrides,
  };
}

describe("regenerating without destroying a person's work", () => {
  test("keeps positions someone tuned in the editor", () => {
    const existing = diagram({
      parts: [{ type: "board-xiao-esp32-c6", id: "xiao", top: 250, left: 130, attrs: {} }],
    });

    const { diagram: merged, summary } = mergeWithExisting(diagram(), existing);

    expect(merged.parts[0]).toMatchObject({ top: 250, left: 130 });
    expect(summary.keptPositions).toBe(1);
  });

  test("keeps a hand-routed wire, because routing is hand work", () => {
    const existing = diagram({ connections: [["xiao:D4", "oled:SDA", "green", ["v20", "*", "h10"]]] });

    const { diagram: merged, summary } = mergeWithExisting(diagram(), existing);

    expect(merged.connections[0]![3]).toEqual(["v20", "*", "h10"]);
    expect(summary.keptRoutes).toBe(1);
  });

  test("matches a wire however round the person wrote it", () => {
    const existing = diagram({ connections: [["oled:SDA", "xiao:D4", "green", ["v30"]]] });

    const { diagram: merged } = mergeWithExisting(diagram(), existing);

    expect(merged.connections[0]![3]).toEqual(["v30"]);
  });

  test("keeps a part added by hand, with its wires", () => {
    const existing = diagram({
      parts: [
        ...diagram().parts,
        {
          type: "wokwi-logic-analyzer",
          id: "logic",
          top: 300,
          left: 0,
          attrs: { [HAND_ADDED_ATTR]: "true" },
        },
      ],
      connections: [...diagram().connections, ["logic:D0", "xiao:D3", "purple", []]],
    });

    const { diagram: merged, summary } = mergeWithExisting(diagram(), existing);

    expect(summary.keptHandAddedParts).toEqual(["logic"]);
    expect(merged.connections.some(([from]) => from === "logic:D0")).toBe(true);
  });

  test("but the board still decides what is connected", () => {
    // A wire that the design no longer has must disappear, even if it is in the existing file:
    // that is the whole point of regenerating.
    const existing = diagram({
      connections: [["xiao:D9", "oled:SDA", "green", []], ["xiao:D4", "oled:SDA", "green", []]],
    });

    const { diagram: merged } = mergeWithExisting(diagram(), existing);

    expect(merged.connections).toHaveLength(1);
    expect(merged.connections[0]![0]).toBe("xiao:D4");
  });

  test("a first run with no existing file just works", () => {
    const { diagram: merged, summary } = mergeWithExisting(diagram(), undefined);

    expect(merged.parts).toHaveLength(1);
    expect(summary.keptPositions).toBe(0);
  });
});

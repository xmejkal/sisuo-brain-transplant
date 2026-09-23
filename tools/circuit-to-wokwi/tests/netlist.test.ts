import { describe, expect, test } from "bun:test";

import { buildNetlist } from "../lib/netlist";
import { circuit, net, part, tinyCircuit } from "./fixtures";

describe("reading a design", () => {
  test("finds every component and its pins", () => {
    const { netlist } = buildNetlist(tinyCircuit());

    expect(netlist.components.map((component) => component.name)).toEqual(["XIAO", "OledDisplay"]);
    expect(netlist.components[0]!.pins.map((pin) => pin.name)).toEqual(["D4", "GND"]);
  });

  test("groups pins into nets", () => {
    const { netlist } = buildNetlist(tinyCircuit());

    expect(netlist.nets).toHaveLength(2);
    const ground = netlist.nets.find((net) => net.name === "GND");
    expect(ground?.members.map((member) => member.pinName).sort()).toEqual(["GND", "GND"]);
  });

  test("keeps the designer's name for a net, where there is one", () => {
    const { netlist } = buildNetlist(tinyCircuit());

    expect(netlist.nets.some((net) => net.name === "GND")).toBe(true);
  });

  test("reports a component with no pins rather than emitting a part nothing can reach", () => {
    const { problems } = buildNetlist(
      circuit([part("XIAO", ["D4"]), part("Orphan", [])], [net(undefined, ["XIAO:D4"])]),
    );

    expect(problems.some((problem) => problem.context?.component === "Orphan")).toBe(true);
  });

  test("passes on the design's own warnings, because the person regenerating should see them", () => {
    const { problems } = buildNetlist([
      ...tinyCircuit(),
      { type: "source_unnamed_trace_warning", message: "unnamed trace" },
    ]);

    expect(problems.some((problem) => problem.message.includes("source_unnamed_trace_warning"))).toBe(
      true,
    );
  });
});

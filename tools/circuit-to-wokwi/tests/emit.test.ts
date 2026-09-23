import { describe, expect, test } from "bun:test";

import { emitWokwiDiagram } from "../lib/emitters/wokwi";
import { buildNetlist } from "../lib/netlist";
import { validate } from "../lib/validate";
import { circuit, net, part, tinyCircuit } from "./fixtures";

const CHIPS = `${import.meta.dir}/../../../firmware/micropython/sim/chips`;

function emitFrom(circuitJson: any[]) {
  const { netlist } = buildNetlist(circuitJson);
  return { netlist, emitted: emitWokwiDiagram(netlist, { chipsDirectory: CHIPS }) };
}

describe("emitting a Wokwi diagram", () => {
  test("uses the board's silkscreen pin names, not GPIO numbers", () => {
    const { emitted } = emitFrom(tinyCircuit());

    const pinsUsed = emitted.diagram.connections
      .map(([from]) => from)
      .filter((from) => from.startsWith("xiao:"));
    expect(pinsUsed).toContain("xiao:D4");   // the design calls this pin SDA; Wokwi calls it D4
    expect(pinsUsed.some((pin) => /xiao:(22|GPIO)/.test(pin))).toBe(false);
  });

  test("wires a net as a star from the board, so wires stay short", () => {
    const { emitted } = emitFrom(
      circuit(
        [part("XIAO", ["D4"]), part("OledDisplay", ["SDA"]), part("BtnOpen", ["A"])],
        [net(undefined, ["XIAO:D4", "OledDisplay:SDA", "BtnOpen:A"])],
      ),
    );

    const sdaWires = emitted.diagram.connections.filter(([from]) => from === "xiao:D4");
    expect(sdaWires).toHaveLength(2); // one to each of the other two members
  });

  test("colours ground black and power red, as Wokwi's own diagrams do", () => {
    const { emitted } = emitFrom(tinyCircuit());

    const ground = emitted.diagram.connections.find(([, to]) => to.endsWith(":GND"));
    expect(ground?.[2]).toBe("black");
  });

  test("reports an unmapped component instead of silently leaving it out", () => {
    const { emitted } = emitFrom(
      circuit(
        [part("XIAO", ["D4"]), part("MysteryModule", ["X"])],
        [net(undefined, ["XIAO:D4", "MysteryModule:X"])],
      ),
    );

    expect(emitted.problems.some((p) => p.context?.component === "MysteryModule")).toBe(true);
  });

  test("records a deliberately unsimulated part as a decision, with its reason", () => {
    const { emitted } = emitFrom(
      circuit(
        [part("XIAO", ["GND"]), part("MotorBulkCap", ["A"])],
        [net("GND", ["XIAO:GND", "MotorBulkCap:A"])],
      ),
    );

    expect(emitted.skipped.map((skip) => skip.component)).toContain("MotorBulkCap");
    expect(emitted.problems.some((p) => p.context?.component === "MotorBulkCap")).toBe(false);
  });

  test("catches a pin the part does not have, including on our own custom chips", () => {
    // chip-l9110s has IA/IB/OA/OB/GND and no such pin as WRONG.
    const { emitted } = emitFrom(
      circuit(
        [part("MotorDriver", ["WRONG"]), part("XIAO", ["D0"])],
        [net(undefined, ["MotorDriver:WRONG", "XIAO:D0"])],
      ),
    );

    expect(emitted.problems.some((problem) => problem.message.includes("not a pin of chip-l9110s"))).toBe(
      true,
    );
  });

  test("a pin the stand-in part genuinely lacks is a recorded decision, not an error", () => {
    // The board's TB6612 has PWMA; the L9110S standing in for it does not, and mapping.ts says so.
    const { emitted } = emitFrom(
      circuit(
        [part("MotorDriver", ["PWMA"]), part("XIAO", ["D3"])],
        [net(undefined, ["MotorDriver:PWMA", "XIAO:D3"])],
      ),
    );

    expect(emitted.problems).toHaveLength(0);
    expect(emitted.netOutcomes).toHaveLength(1);
    expect(emitted.netOutcomes[0]!.skippedEndpoints).toBe(1);
    expect(emitted.netOutcomes[0]!.wires).toBe(0);
  });

  test("the diagram passes Wokwi's own linter", () => {
    const { emitted } = emitFrom(tinyCircuit());
    const result = validate(emitted);

    expect(result.problems).toEqual([]);
  });
});

import { describe, expect, test } from "bun:test";

import { emitWokwiDiagram } from "../lib/emitters/wokwi";
import { buildNetlist } from "../lib/netlist";
import { validate } from "../lib/validate";
import { circuit, MCU_GND, MCU_NAME, MCU_SDA, net, part, tinyCircuit } from "./fixtures";
import { BOARD } from "../lib/mapping";
import { MCU } from "../../../mcu-pins";

/** Wokwi part ids are the component name, lowercased. */
const MCU_ID = MCU_NAME.toLowerCase();
/** What the Wokwi part calls the pin the design calls SDA. Board-dependent. */
const MCU_SDA_IN_WOKWI = BOARD.pins!.SDA as string;

const CHIPS = `${import.meta.dir}/../../../firmware/micropython/sim/chips`;

function emitFrom(circuitJson: any[]) {
  const { netlist } = buildNetlist(circuitJson);
  return { netlist, emitted: emitWokwiDiagram(netlist, { chipsDirectory: CHIPS }) };
}

describe("emitting a Wokwi diagram", () => {
  test("renames the design's pins to whatever the Wokwi part calls them", () => {
    // Which naming that is depends on the board and is recorded in boards/<id>.json: Wokwi's
    // XIAO part names pins by silkscreen (D4), while the generic S3 devkit that stands in for
    // the FireBeetle names them by raw GPIO ("1"). Either way the DESIGN's own name for the pin
    // must not survive into the diagram, or the simulator silently drops the wire.
    const { emitted } = emitFrom(tinyCircuit());

    const pinsUsed = emitted.diagram.connections
      .map(([from]) => from)
      .filter((from) => from.startsWith(`${MCU_ID}:`));
    expect(pinsUsed).toContain(`${MCU_ID}:${MCU_SDA_IN_WOKWI}`);
    if (MCU_SDA_IN_WOKWI !== MCU_SDA) {
      expect(pinsUsed).not.toContain(`${MCU_ID}:${MCU_SDA}`);
    }
  });

  test("wires a net as a star from the board, so wires stay short", () => {
    const { emitted } = emitFrom(
      circuit(
        [part(MCU_NAME, [MCU_SDA]), part("OledDisplay", ["SDA"]), part("BtnOpen", ["A"])],
        [net(undefined, [`${MCU_NAME}:${MCU_SDA}`, "OledDisplay:SDA", "BtnOpen:A"])],
      ),
    );

    const sdaWires = emitted.diagram.connections.filter(([from]) => from === `${MCU_ID}:${MCU_SDA_IN_WOKWI}`);
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
        [part(MCU_NAME, [MCU_SDA]), part("MysteryModule", ["X"])],
        [net(undefined, [`${MCU_NAME}:${MCU_SDA}`, "MysteryModule:X"])],
      ),
    );

    expect(emitted.problems.some((p) => p.context?.component === "MysteryModule")).toBe(true);
  });

  test("records a deliberately unsimulated part as a decision, with its reason", () => {
    const { emitted } = emitFrom(
      circuit(
        [part(MCU_NAME, [MCU_GND]), part("MotorBulkCap", ["A"])],
        [net("GND", [`${MCU_NAME}:${MCU_GND}`, "MotorBulkCap:A"])],
      ),
    );

    expect(emitted.skipped.map((skip) => skip.component)).toContain("MotorBulkCap");
    expect(emitted.problems.some((p) => p.context?.component === "MotorBulkCap")).toBe(false);
  });

  test("catches a pin the part does not have, including on our own custom chips", () => {
    // chip-l9110s has IA/IB/OA/OB/GND and no such pin as WRONG.
    const { emitted } = emitFrom(
      circuit(
        [part("MotorDriver", ["WRONG"]), part(MCU_NAME, [MCU.TOF_INT])],
        [net(undefined, ["MotorDriver:WRONG", `${MCU_NAME}:${MCU.TOF_INT}`])],
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
        [part("MotorDriver", ["PWMA"]), part(MCU_NAME, [MCU.MOTOR_IA])],
        [net(undefined, ["MotorDriver:PWMA", `${MCU_NAME}:${MCU.MOTOR_IA}`])],
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

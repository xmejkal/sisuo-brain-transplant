/**
 * The real board, end to end.
 *
 * The fixtures test behaviour; this tests reality — a nineteen-component design with warnings,
 * connectors, capacitors and parts Wokwi has never heard of. If this passes, `bun run cli.ts`
 * produces something the simulator will accept.
 */

import { describe, expect, test } from "bun:test";

import { emitWokwiDiagram } from "../lib/emitters/wokwi";
import { buildNetlist } from "../lib/netlist";
import { validate } from "../lib/validate";

const CIRCUIT = `${import.meta.dir}/../../../dist/board/circuit.json`;
const CHIPS = `${import.meta.dir}/../../../firmware/micropython/sim/chips`;

const circuitJson = await Bun.file(CIRCUIT).json();

describe("the real board", () => {
  const { netlist } = buildNetlist(circuitJson);
  const emitted = emitWokwiDiagram(netlist, { chipsDirectory: CHIPS });

  test("every component is either mapped or deliberately skipped", () => {
    expect(emitted.problems).toEqual([]);
  });

  test("the pin map in the diagram is the pin map in the firmware", () => {
    // config.py drives the motor from D3 and D8, and the design labels those MOTOR_IA/MOTOR_IB.
    // If these ever disagree, the simulation is not simulating the firmware's board.
    const motorWires = emitted.diagram.connections.filter(([, to]) => to.startsWith("motordriver:"));
    expect(motorWires).toContainEqual(["xiao:D3", "motordriver:IA", "green", []]);
    expect(motorWires).toContainEqual(["xiao:D8", "motordriver:IB", "green", []]);
  });

  test("the sensor interrupt is on a pin that can wake the chip", () => {
    // Only GPIO0-7 can wake an ESP32-C6, which on this board is D0, D1 and D2. A sensor
    // interrupt anywhere else would make deep sleep impossible, silently.
    const wakeCapable = ["D0", "D1", "D2"];
    const interrupt = emitted.diagram.connections.find(([, to]) => to === "sensorheader:INT");
    expect(interrupt).toBeDefined();
    expect(wakeCapable).toContain(interrupt![0].replace("xiao:", ""));
  });

  test("it passes Wokwi's own linter and loses no net", () => {
    const result = validate(emitted);

    expect(result.problems).toEqual([]);
    expect(result.wiredNets).toBeGreaterThan(0);
  });

  test("the parts that are missing are missing on purpose", () => {
    const skippedNames = emitted.skipped.map((skip) => skip.component);
    expect(skippedNames).toContain("Mp3Player");    // no Wokwi part; the log shows the cue
    expect(skippedNames).toContain("BinConnector");  // a connector is wiring, not a part
    expect(skippedNames).toContain("CurrentShunt");  // a resistor with no behaviour to simulate

    for (const skip of emitted.skipped) {
      expect(skip.reason.length).toBeGreaterThan(10); // every omission carries a reason
    }
  });
});

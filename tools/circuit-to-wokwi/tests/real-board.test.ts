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
import { board } from "../lib/board";
import { BOARD } from "../lib/mapping";
import { MCU } from "../../../mcu-pins";

/** Wokwi part ids are the component name, lowercased. */
const MCU_ID = (BOARD.match as string).toLowerCase();

/** The name the Wokwi part gives the pin carrying a signal, e.g. MOTOR_IA -> "14". */
const wokwiPinFor = (signal: keyof typeof MCU) => BOARD.pins![MCU[signal]] as string;

const CIRCUIT = `${import.meta.dir}/../../../dist/board/circuit.json`;
const CHIPS = `${import.meta.dir}/../../../firmware/micropython/sim/chips`;

const circuitJson = await Bun.file(CIRCUIT).json();

describe("the real board", () => {
  const { netlist } = buildNetlist(circuitJson);
  const emitted = emitWokwiDiagram(netlist, { chipsDirectory: CHIPS });

  test("every component is either mapped or deliberately skipped", () => {
    expect(emitted.problems).toEqual([]);
  });

  test("the pin map in the diagram is the pin map in the design", () => {
    // Which pins these are is board-specific and deliberately not written here; what must hold
    // on every board is that the motor driver is wired to whatever mcu-pins.ts calls MOTOR_IA
    // and MOTOR_IB. If these disagree, the simulation is not simulating the firmware's board.
    const motorWires = emitted.diagram.connections.filter(([, to]) => to.startsWith("motordriver:"));
    expect(motorWires).toContainEqual([`${MCU_ID}:${wokwiPinFor("MOTOR_IA")}`, "motordriver:IA", "green", []]);
    expect(motorWires).toContainEqual([`${MCU_ID}:${wokwiPinFor("MOTOR_IB")}`, "motordriver:IB", "green", []]);
  });

  test("the sensor interrupt is on a pin that can wake the chip", () => {
    // The bin sleeps between uses, so the pin the sensor interrupts on must be one this chip
    // can wake from — otherwise deep sleep is impossible, silently. Which pins those are comes
    // from boards/<id>.json, because it is a fact about the chip and changes with the board:
    // the ESP32-C6 could wake from eight GPIOs, the S3 from twenty-two.
    const interrupt = emitted.diagram.connections.find(([, to]) => to === "sensorheader:INT");
    expect(interrupt).toBeDefined();

    const interruptPin = interrupt![0].replace(`${MCU_ID}:`, "");
    expect(interruptPin).toBe(wokwiPinFor("TOF_INT"));

    const gpio = board.pins[MCU.TOF_INT];
    expect(gpio).toBeDefined();
    expect(board.wake_capable_gpio).toContain(gpio!);
  });

  test("it passes Wokwi's own linter and loses no net", () => {
    const result = validate(emitted);

    expect(result.problems).toEqual([]);
    expect(result.wiredNets).toBeGreaterThan(0);
  });

  test("the parts that are missing are missing on purpose", () => {
    const skippedNames = emitted.skipped.map((skip) => skip.component);
    expect(skippedNames).toContain("AudioAmp");     // no Wokwi part; the log shows the cue
    expect(skippedNames).toContain("BinConnector");  // a connector is wiring, not a part
    expect(skippedNames).toContain("CurrentShunt");  // a resistor with no behaviour to simulate

    for (const skip of emitted.skipped) {
      expect(skip.reason.length).toBeGreaterThan(10); // every omission carries a reason
    }
  });
});

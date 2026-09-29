import { afterEach, describe, expect, test } from "bun:test";

import { emitWokwiDiagram } from "../lib/emitters/wokwi";
import { findMapping, findSkipRule, loadMappingFile, useMappings } from "../lib/mapping";
import { buildNetlist } from "../lib/netlist";
import { circuit, MCU_GND, MCU_NAME, MCU_SDA, net, part } from "./fixtures";

/** What the spark spine writes from the part records: one entry per component name. */
const FROM_RECORDS = {
  Valve1: { wokwiType: "wokwi-led", pins: { SIGNAL: "A", GND: "C", VCC: null }, attrs: { color: "red" } },
  DcBarrelJack12vInlet: { skip: "a connector is wiring, not a part to simulate" },
};

afterEach(() => useMappings({}));

describe("a mapping from the part records", () => {
  test("an entry for the component's name is used before the hand table", () => {
    useMappings(FROM_RECORDS);
    const mapping = findMapping("Valve1");
    expect(mapping?.wokwiType).toBe("wokwi-led");
    expect(mapping?.pins?.SIGNAL).toBe("A");
    expect(mapping?.pins?.VCC).toBeNull();
    expect(mapping?.attrs?.color).toBe("red");
  });

  test("a skip from the records is a decision with its reason", () => {
    useMappings(FROM_RECORDS);
    expect(findSkipRule("DcBarrelJack12vInlet")?.reason).toContain("wiring");
    expect(findMapping("DcBarrelJack12vInlet")).toBeUndefined();
  });

  test("a name the records do not speak for still falls through to the hand table", () => {
    useMappings(FROM_RECORDS);
    expect(findMapping("BtnMode")?.wokwiType).toBe("wokwi-pushbutton");
    expect(findMapping("NoSuchThing")).toBeUndefined();
  });

  test("the spine's file is read and counted", async () => {
    const path = `${import.meta.dir}/.mapping-under-test.json`;
    await Bun.write(path, JSON.stringify(FROM_RECORDS));
    expect(loadMappingFile(path)).toBe(2);
    expect(findMapping("Valve1")?.wokwiType).toBe("wokwi-led");
  });

  test("the emitted diagram carries the stand-in and the skip", () => {
    useMappings(FROM_RECORDS);
    const { netlist } = buildNetlist(circuit(
      [part(MCU_NAME, [MCU_SDA, MCU_GND]), part("Valve1", ["SIGNAL", "GND"]), part("DcBarrelJack12vInlet", ["VIN", "GND"])],
      [net("VALVE1", [`${MCU_NAME}:${MCU_SDA}`, "Valve1:SIGNAL"]),
       net("GND", [`${MCU_NAME}:${MCU_GND}`, "Valve1:GND", "DcBarrelJack12vInlet:GND"])],
    ));
    const emitted = emitWokwiDiagram(netlist);
    expect(emitted.problems).toEqual([]);
    expect(emitted.diagram.parts.map((p) => p.type)).toContain("wokwi-led");
    expect(emitted.skipped.map((s) => s.component)).toEqual(["DcBarrelJack12vInlet"]);
    const wires = emitted.diagram.connections.map((c) => `${c[0]}-${c[1]}`);
    expect(wires.some((w) => w.includes("valve1:A"))).toBe(true);
  });
});

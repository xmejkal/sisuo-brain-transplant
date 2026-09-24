/**
 * A builder for small, realistic circuit.json fixtures.
 *
 * "Realistic" is the important word: connectivity in Circuit JSON comes from `source_trace`
 * elements, so a fixture that invents net keys on ports would test a world that does not exist.
 * This builder emits ports and traces the way tscircuit does, so a passing test means something.
 *
 *   circuit([
 *     part(MCU_NAME, [MCU_SDA, MCU_GND]),
 *     part("OledDisplay", ["SDA", "GND"]),
 *   ], [
 *     net("SDA", ["XIAO:D4", "OledDisplay:SDA"]),
 *     net("GND", ["XIAO:GND", "OledDisplay:GND"]),
 *   ])
 */

import { BOARD } from "../lib/mapping";
import { MCU } from "../../../mcu-pins";

export interface PartSpec {
  name: string;
  pins: string[];
}

export interface NetSpec {
  name?: string;
  /** Endpoints as "ComponentName:pinName". */
  members: string[];
}


export function part(name: string, pins: string[]): PartSpec {
  return { name, pins };
}

export function net(name: string | undefined, members: string[]): NetSpec {
  return { name, members };
}

export function circuit(parts: PartSpec[], nets: NetSpec[]): any[] {
  const elements: any[] = [];
  const portIds = new Map<string, string>(); // "Component:pin" -> source_port_id

  parts.forEach((partSpec, partIndex) => {
    const componentId = `source_component_${partIndex}`;
    elements.push({
      type: "source_component",
      source_component_id: componentId,
      name: partSpec.name,
      ftype: "simple_chip",
    });

    partSpec.pins.forEach((pinName, pinIndex) => {
      const portId = `source_port_${partIndex}_${pinIndex}`;
      portIds.set(`${partSpec.name}:${pinName}`, portId);
      elements.push({
        type: "source_port",
        source_port_id: portId,
        source_component_id: componentId,
        name: `pin${pinIndex + 1}`,
        pin_number: pinIndex + 1,
        port_hints: [pinName, `pin${pinIndex + 1}`],
      });
    });
  });

  nets.forEach((netSpec, netIndex) => {
    const connectedPortIds = netSpec.members.map((member) => {
      const portId = portIds.get(member);
      if (!portId) throw new Error(`fixture error: no such pin ${member}`);
      return portId;
    });

    const connectedNetIds: string[] = [];
    if (netSpec.name) {
      const netId = `source_net_${netIndex}`;
      connectedNetIds.push(netId);
      elements.push({ type: "source_net", source_net_id: netId, name: netSpec.name });
    }

    elements.push({
      type: "source_trace",
      source_trace_id: `source_trace_${netIndex}`,
      connected_source_port_ids: connectedPortIds,
      connected_source_net_ids: connectedNetIds,
    });
  });

  return elements;
}

/**
 * The circuit most tests start from: a board, a display, and the two nets between them.
 *
 * The board is named by `BOARD.match` and its pin by a signal from `mcu-pins.ts`, not by any
 * particular board's silkscreen — otherwise every one of these tests has to be rewritten the
 * next time the microcontroller changes, which is exactly what happened once already.
 */
export const MCU_NAME = BOARD.match as string;
export const MCU_SDA = MCU.SDA;
/** The module's ground pad. Named, not literal: this board has three of them. */
export const MCU_GND = MCU.GND;

export function tinyCircuit(): any[] {
  return circuit(
    [part(MCU_NAME, [MCU_SDA, MCU_GND]), part("OledDisplay", ["SDA", "GND"])],
    [
      net(undefined, [`${MCU_NAME}:${MCU_SDA}`, "OledDisplay:SDA"]),
      net("GND", [`${MCU_NAME}:${MCU_GND}`, "OledDisplay:GND"]),
    ],
  );
}

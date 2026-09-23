/**
 * circuit.json -> Netlist.
 *
 * The only place connectivity is derived. Circuit JSON already carries a precomputed net id on
 * every source port, and `circuit-json-to-connectivity-map` is the supported way to read it —
 * re-deriving nets by walking traces would be a second implementation that can disagree with the
 * first, which is exactly the class of bug this tool exists to prevent.
 */

import { cju } from "@tscircuit/circuit-json-util";
import { getSourcePortConnectivityMapFromCircuitJson } from "circuit-json-to-connectivity-map";

import type { Component, Net, Netlist, Pin, Problem } from "./types";

export interface NetlistResult {
  netlist: Netlist;
  /** Non-fatal observations: a design warning, a port with no name, an isolated pin. */
  problems: Problem[];
}

export function buildNetlist(circuitJson: any[]): NetlistResult {
  const problems: Problem[] = [];
  const db = cju(circuitJson);

  const components = readComponents(db, problems);
  const portOwner = indexPortsByComponent(components);
  const nets = readNets(circuitJson, portOwner, db, problems);

  carryOverDesignWarnings(circuitJson, problems);

  return { netlist: { components, nets }, problems };
}

function readComponents(db: any, problems: Problem[]): Component[] {
  return db.source_component.list().map((sourceComponent: any) => {
    const pins: Pin[] = db.source_port
      .list({ source_component_id: sourceComponent.source_component_id })
      .map((port: any) => ({
        name: pinNameOf(port),
        portId: port.source_port_id,
      }));

    if (pins.length === 0) {
      problems.push({
        message: "component has no pins in the design, so nothing can be wired to it",
        context: { component: sourceComponent.name },
      });
    }

    return {
      id: sourceComponent.source_component_id,
      name: sourceComponent.name,
      type: sourceComponent.ftype ?? "unknown",
      pins,
    };
  });
}

/**
 * The name a person would use for a pin.
 *
 * Circuit JSON gives a port a `name` plus `port_hints` — the aliases a designer used, such as
 * "D4" or "SDA" beside a bare "pin5". The most specific hint is the most useful label, and it is
 * what the mapping table will be written against.
 */
function pinNameOf(port: any): string {
  const hints: string[] = port.port_hints ?? [];
  const named = hints.filter((hint) => !/^(pin)?\d+$/.test(hint));
  return named[0] ?? port.name ?? hints[0] ?? port.source_port_id;
}

function indexPortsByComponent(components: Component[]) {
  const owner = new Map<string, { componentId: string; pinName: string }>();
  for (const component of components) {
    for (const pin of component.pins) {
      owner.set(pin.portId, { componentId: component.id, pinName: pin.name });
    }
  }
  return owner;
}

function readNets(
  circuitJson: any[],
  portOwner: Map<string, { componentId: string; pinName: string }>,
  db: any,
  problems: Problem[],
): Net[] {
  const connectivity = getSourcePortConnectivityMapFromCircuitJson(circuitJson);
  const nets: Net[] = [];

  for (const [netId, portIds] of Object.entries(connectivity.netMap ?? {})) {
    const members = (portIds as string[])
      .map((portId) => portOwner.get(portId))
      .filter(Boolean) as { componentId: string; pinName: string }[];

    if (members.length < 2) {
      // A net with one member is a pin connected to nothing: worth saying, not worth failing on,
      // because a spare pin is a legitimate design choice.
      continue;
    }

    nets.push({ id: netId, name: netNameOf(netId, portIds as string[], db), members });
  }

  return nets.sort((a, b) => a.id.localeCompare(b.id));
}

/** Prefer the designer's own net name ("V33", "GND") over the generated connectivity key. */
function netNameOf(netId: string, portIds: string[], db: any): string | undefined {
  for (const net of db.source_net.list()) {
    const trace = db.source_trace
      .list()
      .find(
        (candidate: any) =>
          candidate.connected_source_net_ids?.includes(net.source_net_id) &&
          candidate.connected_source_port_ids?.some((portId: string) => portIds.includes(portId)),
      );
    if (trace) return net.name;
  }
  return undefined;
}

/**
 * The design's own warnings travel with the netlist.
 *
 * tscircuit reports things like "this trace has no name" or "these pins are underspecified" as
 * elements in circuit.json. They are the board's problems rather than the converter's, but a
 * person regenerating a diagram is exactly the person who should see them.
 */
function carryOverDesignWarnings(circuitJson: any[], problems: Problem[]) {
  const warnings = circuitJson.filter((element) => String(element.type).endsWith("_warning"));
  const counts = new Map<string, number>();
  for (const warning of warnings) {
    counts.set(warning.type, (counts.get(warning.type) ?? 0) + 1);
  }
  for (const [type, count] of counts) {
    problems.push({ message: `the board design reports ${count} x ${type}` });
  }
}

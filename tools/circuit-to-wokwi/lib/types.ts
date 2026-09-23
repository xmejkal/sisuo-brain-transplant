/**
 * The intermediate representation, and the only abstraction this tool asks anyone to learn.
 *
 * It is deliberately thin: what is connected to what, with names a human recognises. No
 * geometry, no Wokwi concepts, nothing from tscircuit's internals. Every emitter reads this and
 * only this, which is what makes adding a second output cost one file.
 */

/** One physical thing on the board. */
export interface Component {
  /** Stable id from the design, used to correlate across regenerations. */
  id: string;
  /** What a person calls it: "U1", "SW_OPEN", "MotorDriver". */
  name: string;
  /** The design's own component type, e.g. "simple_chip", "simple_resistor". */
  type: string;
  pins: Pin[];
}

export interface Pin {
  /** The pin's name in the design: "D4", "SDA", "pin1". */
  name: string;
  /** The underlying source_port id, so nets can be matched back. */
  portId: string;
}

/** A set of pins that are electrically one node. */
export interface Net {
  id: string;
  /** A readable name where the design gave one ("V33", "GND"), otherwise undefined. */
  name?: string;
  members: NetMember[];
}

export interface NetMember {
  componentId: string;
  pinName: string;
}

export interface Netlist {
  components: Component[];
  nets: Net[];
}

/**
 * A problem worth reporting, collected rather than thrown.
 *
 * One run should tell you everything that is wrong — being told about one unmapped component,
 * fixing it, and then being told about the next is a bad way to spend an afternoon.
 */
export interface Problem {
  /** What the reader should do about it, in plain words. */
  message: string;
  /** Where it came from, to make the message actionable. */
  context?: { component?: string; pin?: string; net?: string };
}

export class ConversionFailed extends Error {
  constructor(public problems: Problem[]) {
    super(
      `${problems.length} problem(s) converting the board:\n` +
        problems.map((problem) => `  - ${describe(problem)}`).join("\n"),
    );
    this.name = "ConversionFailed";
  }
}

function describe(problem: Problem): string {
  const context = problem.context ?? {};
  const parts = [
    context.component && `component ${context.component}`,
    context.pin && `pin ${context.pin}`,
    context.net && `net ${context.net}`,
  ].filter(Boolean);
  return parts.length ? `${problem.message} (${parts.join(", ")})` : problem.message;
}

/**
 * Keep what a human decided, replace what the design decides.
 *
 * The generator owns *what is connected to what*. A person owns *what it looks like* — where the
 * parts sit, how the wires are routed, and any part added by hand that the board does not have
 * (a logic analyser, a probe LED). Regenerating must not throw that away, or nobody will
 * regenerate.
 *
 * So: positions, rotations and wire routes are carried over from the existing file by part id,
 * and hand-added parts are kept if they are marked. Everything else comes from the board.
 */

import type { WokwiConnection, WokwiDiagram, WokwiPart } from "./emitters/wokwi";

/** Mark a part with this attribute to keep it across regenerations. */
export const HAND_ADDED_ATTR = "handAdded";

export interface MergeSummary {
  keptPositions: number;
  keptHandAddedParts: string[];
  keptRoutes: number;
}

export function mergeWithExisting(
  generated: WokwiDiagram,
  existing: WokwiDiagram | undefined,
): { diagram: WokwiDiagram; summary: MergeSummary } {
  const summary: MergeSummary = { keptPositions: 0, keptHandAddedParts: [], keptRoutes: 0 };
  if (!existing) return { diagram: generated, summary };

  const existingParts = new Map(existing.parts.map((part) => [part.id, part]));

  const parts: WokwiPart[] = generated.parts.map((part) => {
    const previous = existingParts.get(part.id);
    if (!previous) return part;
    summary.keptPositions += 1;
    return {
      ...part,
      top: previous.top ?? part.top,
      left: previous.left ?? part.left,
      ...(previous.rotate !== undefined ? { rotate: previous.rotate } : {}),
      // A person may have set a control on a chip (a distance, an LED colour); keep it, but let
      // the mapping table add anything new.
      attrs: { ...part.attrs, ...previous.attrs },
    };
  });

  for (const part of existing.parts) {
    const isHandAdded = part.attrs?.[HAND_ADDED_ATTR] === "true";
    if (isHandAdded && !parts.some((candidate) => candidate.id === part.id)) {
      parts.push(part);
      summary.keptHandAddedParts.push(part.id);
    }
  }

  const connections = generated.connections.map((connection) => {
    const previous = findMatchingConnection(existing.connections, connection);
    if (previous && previous[3]?.length) {
      summary.keptRoutes += 1;
      return [connection[0], connection[1], connection[2], previous[3]] as WokwiConnection;
    }
    return connection;
  });

  // Wires between hand-added parts are the person's too, and the board knows nothing about them.
  for (const connection of existing.connections) {
    const involvesHandAdded = summary.keptHandAddedParts.some((partId) =>
      connection.some((end) => typeof end === "string" && end.startsWith(`${partId}:`)),
    );
    if (involvesHandAdded) connections.push(connection);
  }

  return {
    diagram: { ...generated, parts, connections },
    summary,
  };
}

/** The same wire, regardless of which end was written first. */
function findMatchingConnection(
  connections: WokwiConnection[],
  wanted: WokwiConnection,
): WokwiConnection | undefined {
  return connections.find(
    (candidate) =>
      (candidate[0] === wanted[0] && candidate[1] === wanted[1]) ||
      (candidate[0] === wanted[1] && candidate[1] === wanted[0]),
  );
}

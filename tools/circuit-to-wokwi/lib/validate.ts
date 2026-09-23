/**
 * Prove the generated diagram is worth trusting, offline, before it is written.
 *
 * Two checks, answering different questions:
 *
 *   lint      — "is this a valid Wokwi project?"   Wokwi's own rules and part registry
 *   coverage  — "does it simulate *this* board?"   every net that could be wired, was
 *
 * The second is the one this tool exists for. A diagram that lints perfectly but silently lost a
 * net is a simulation quietly disagreeing with the hardware, which is worse than no simulation.
 */

import { DiagramLinter } from "@wokwi/diagram-lint";

import type { EmitResult } from "./emitters/wokwi";
import type { Problem } from "./types";

export interface ValidationResult {
  problems: Problem[];
  checkedNets: number;
  wiredNets: number;
  lintIssues: number;
}

export function validate(emitted: EmitResult): ValidationResult {
  const lintProblems = lint(emitted);
  const coverageProblems = checkNetCoverage(emitted);

  return {
    problems: [...lintProblems, ...coverageProblems],
    checkedNets: emitted.netOutcomes.length,
    wiredNets: emitted.netOutcomes.filter((outcome) => outcome.wires > 0).length,
    lintIssues: lintProblems.length,
  };
}

function lint(emitted: EmitResult): Problem[] {
  const result = new DiagramLinter().lint(emitted.diagram as any);
  return result.issues
    .filter((issue) => issue.severity !== "info")
    .map((issue) => ({
      message: `${issue.rule}: ${issue.message}`,
      context: { component: (issue as any).partId },
    }));
}

/**
 * A net with two or more simulated endpoints must have produced a wire.
 *
 * Nets that lost members to skip rules are not failures — that is the skip rules working, and
 * the emitter records exactly how many went that way.
 */
function checkNetCoverage(emitted: EmitResult): Problem[] {
  return emitted.netOutcomes
    .filter((outcome) => outcome.simulatedEndpoints >= 2 && outcome.wires === 0)
    .map((outcome) => ({
      message: "this net connects two simulated parts but produced no wire",
      context: { net: outcome.name ?? outcome.netId },
    }));
}

#!/usr/bin/env python3
"""
The documents that describe the bin AS IT IS NOW name no part it no longer has (spark backlog B6).

The board changed twice in one week — a XIAO ESP32-C6 became a FireBeetle 2 ESP32-S3, a DFR0534 MP3
module became an I2S amplifier — and the code, the board and the simulation were swept while the
prose was not. A week later the README still called the brain a XIAO, the brief that spark's
reviewers read still listed the MP3 module, and STATUS.md sent the reader to a tool deleted days
before. Nothing compared a document with the board it describes, so nothing noticed.

This does, cheaply: a retired part's name may appear in a current-state document only where it is
rejected ("no OLED", "not TB6612") or in a passage listed below by its exact words, with a reason.
A rule a person can read and argue with, rather than a judgement made by word-matching.

    python3 tools/check-current-docs.py        # exit 0, or 1 naming file:line
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Parts the bin had and no longer has, with when they went. A new retirement is one line here.
RETIRED = {
    "XIAO": "the XIAO ESP32-C6, replaced by the FireBeetle 2 ESP32-S3 on 2026-09-24",
    "ESP32-C6": "the chip of the XIAO, replaced on 2026-09-24",
    "DFR0534": "the UART MP3 module, replaced by the I2S amplifier on 2026-09-25",
    "MP3": "the UART MP3 module, replaced by the I2S amplifier on 2026-09-25",
    "TB6612": "the v1 motor driver, never on any routed board",
    "OLED": "the v1 display, dropped before v2",
    "VBAT": "the raw-battery rail, gone with the XIAO on 2026-09-24",
    "findings.py": "spark's findings store, deleted on 2026-09-29",
}

#: The passages that name a retired part ON PURPOSE, by an exact quote, each with its reason. A
#: history word cannot be the test — "its brain was replaced: a XIAO" carried one and was the very
#: claim this exists to catch. So a new mention fails until someone reads it and lists it here,
#: and a listed quote that no longer exists fails too, so the list cannot outlive its text.
ON_PURPOSE = {
    ("STATUS.md", "described a board two changes old"): "names what the previous version wrongly described",
    ("STATUS.md", "Retire the DFR0534 fallback"): "B29's exact title; B1 closed 2026-10-06 and no DFR0534 was ever bought",
    ("STATUS.md", "not the XIAO ESP32-C6 on hand"): "the decision that replaced it, and why",
    ("STATUS.md", "when the XIAO ESP32-C6 was replaced by"): "how the board change went",
    ("DESIGN_RULES.md", "Until then this was the XIAO ESP32-C6's checklist"): "what the section used to be",
}

#: A part named in order to reject it — "no OLED", "rather than TB6612" — is a decision, not a claim
#: that it is there. Only when the negation sits immediately before the name.
NEGATED = r"\b(?:no|not|never|without|rather\s+than|instead\s+of)\s+(?:the\s+|a\s+|an\s+)?$"

#: The documents that describe the bin as it is now. History lives elsewhere — the v1 and v3 board
#: files, the Arduino sketch — and in git.
CURRENT = ("README.md", "STATUS.md", "DESIGN_RULES.md", "PCB_PIPELINE.md")

#: The brief, read as data: `parts_on_hand` is an inventory — the XIAO is in the drawer;
#: a DFR0534 never was (B1, 2026-10-06) — so it is the one field allowed to name them without saying they are history.
BRIEF = ".spark/project.json"
INVENTORY_FIELDS = ("parts_on_hand",)


def retired_in(text):
    """Retired names this text uses as if they were here: every occurrence not directly negated."""
    found = []
    for name in RETIRED:
        for match in re.finditer(r"(?<![A-Za-z])%s(?![a-z])" % re.escape(name), text):
            if not re.search(NEGATED, text[:match.start()], re.IGNORECASE):
                found.append(name)
                break
    return found


def passages(text):
    """
    (first line number, text) per paragraph, list item and table row — the unit a reader takes as
    one statement. Lines are the wrong unit: a wrapped sentence names a part on one line and says
    it is history on the next.
    """
    blocks, current, start = [], [], 0
    for number, line in enumerate(text.splitlines(), 1):
        starts_new = (not line.strip() or line.lstrip().startswith("|")
                      or re.match(r"\s*(?:[-*]|\d+\.)\s", line))
        if starts_new and current:
            blocks.append((start, " ".join(current)))
            current = []
        if line.strip():
            if not current:
                start = number
            current.append(line.strip())
            if line.lstrip().startswith("|"):
                blocks.append((start, " ".join(current)))
                current = []
    if current:
        blocks.append((start, " ".join(current)))
    return blocks


def document_problems(relative):
    problems = []
    for number, passage in passages((ROOT / relative).read_text()):
        on_purpose = any(doc == relative and quote in passage for doc, quote in ON_PURPOSE)
        for name in retired_in(passage):
            if not on_purpose:
                problems.append("%s:%d names %s — %s — and is not a passage listed as on purpose"
                                % (relative, number, name, RETIRED[name]))
    return problems


def stale_exceptions():
    return ["ON_PURPOSE quotes %s from %s, which no longer says it" % (repr(quote), doc)
            for doc, quote in ON_PURPOSE if quote not in " ".join(
                text for _, text in passages((ROOT / doc).read_text()))]


def brief_problems():
    brief = json.loads((ROOT / BRIEF).read_text())
    problems = []
    for field, value in brief.items():
        if field in INVENTORY_FIELDS:
            continue
        for text in value if isinstance(value, list) else [value]:
            # The brief's `decided` entries say what replaced what: "not the XIAO ... on hand".
            if field == "decided" and " on hand" in str(text):
                continue
            for name in retired_in(str(text)):
                problems.append("%s %s names %s — %s" % (BRIEF, field, name, RETIRED[name]))
    return problems


def main():
    problems = ([p for doc in CURRENT for p in document_problems(doc)] + brief_problems()
                + stale_exceptions())
    for problem in problems:
        print("  - " + problem)
    if problems:
        print("\n%d problem(s). Say what replaced the part, or — if naming it is deliberate — list "
              "the passage in ON_PURPOSE with its reason." % len(problems))
        return 1
    print("   %d current documents and the brief name no retired part as if it were here."
          % len(CURRENT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

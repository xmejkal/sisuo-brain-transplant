"""
Print the lid's state machine as a Mermaid diagram, read from the real transition table.

Run on the Mac, not the device:
    cd firmware/micropython && python3 tools/fsm_diagram.py

Paste the output into any Markdown file that renders Mermaid. Because it reads states.py, the
picture cannot drift from the behaviour.
"""

import sys
from os import path

sys.path.insert(0, path.dirname(path.dirname(path.abspath(__file__))))

from smartbin import states  # noqa: E402


def mermaid():
    lines = ["stateDiagram-v2", "    [*] --> idle"]
    for state in states.ALL_STATES:
        for trigger, destination in sorted(states.TRANSITIONS.get(state, {}).items()):
            arrow = "-->" if destination != state else "-->"
            lines.append("    %s %s %s: %s" % (state, arrow, destination, trigger))
    return "\n".join(lines)


if __name__ == "__main__":
    print("```mermaid")
    print(mermaid())
    print("```")

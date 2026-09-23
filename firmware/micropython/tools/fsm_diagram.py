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
            lines.append("    %s --> %s: %s" % (state, destination, trigger))
    return "\n".join(lines)


def check(markdown_path):
    """
    Is the diagram embedded in a document still the one the table produces?

    The README claimed the picture could not drift because it was generated. It had drifted, for
    weeks, through five trigger renames — a claim nobody checked is just a claim.
    """
    text = open(markdown_path).read()
    expected = mermaid()
    if expected in text:
        print("   the diagram in %s matches states.py" % path.basename(markdown_path))
        return 0
    print("%s contains a state diagram that no longer matches states.py." % markdown_path)
    print("Regenerate it:  python3 tools/fsm_diagram.py")
    return 1


if __name__ == "__main__":
    if "--check" in sys.argv:
        target = sys.argv[sys.argv.index("--check") + 1]
        sys.exit(check(target))

    print("```mermaid")
    print(mermaid())
    print("```")

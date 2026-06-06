"""Dashboard GUI for Flowkey (Linux) — DEPRECATED (replaced by Textual TUI).

Built with tkinter. Superseded by flowkey-tui (Textual dashboard).
Kept as a stub for backward compatibility.

See TODO.md Phase 4 for the full implementation plan.
"""

from __future__ import annotations

import sys


def main() -> int:
    print("flowkey-dashboard: DEPRECATED — replaced by 'flowkey-tui' (Textual TUI)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

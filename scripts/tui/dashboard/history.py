from __future__ import annotations

import json

from textual.app import ComposeResult
from textual.widgets import Static

import paths as _paths
from tui.dashboard._pane import Pane


class HistoryPane(Pane):
    """History pane: recent entries from JSONL."""

    def __init__(self) -> None:
        super().__init__()
        self._entries: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("Loading History…", id="history-content", classes="panel-content")

    def _fetch(self) -> None:
        """Read recent history entries from the JSONL file."""
        history_path = _paths.DATA_DIR / "grammar_fix_history.jsonl"
        entries: list[dict] = []
        if history_path.exists():
            try:
                with history_path.open("r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        self._entries = entries[-50:]  # last 50
        self.call_later(self._on_data)

    def _on_data(self) -> None:
        content = self.query_one("#history-content", Static)
        entries = self._entries

        if not entries:
            content.update("[dim]No history entries yet.[/]")
            return

        # Show newest first
        lines = [f"[bold]Recent {len(entries)} entries[/]", ""]
        for entry in reversed(entries[-20:]):
            ts = str(entry.get("timestamp") or entry.get("mode") or "?")[:19]
            mode = str(entry.get("mode", "?")).ljust(12)
            elapsed = entry.get("elapsed_seconds")
            elapsed_str = f"{elapsed:.2f}s" if isinstance(elapsed, (int, float)) else "?s"
            tokens = entry.get("prompt_tokens", 0) or 0
            lines.append(f"  {ts}  {mode}  {elapsed_str}  ({tokens} tok)")

        content.update("\n".join(lines))

from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from tui.dashboard._pane import Pane
from tui.dashboard._daemon import _daemon_post


class NotesPane(Pane):
    """Notes pane: vault info."""

    def __init__(self) -> None:
        super().__init__()
        self._data: dict = {}

    def compose(self) -> ComposeResult:
        yield Static("Loading Notes…", id="notes-content", classes="panel-content")

    def _fetch(self) -> None:
        config_resp = _daemon_post("config_snapshot")
        if config_resp.get("ok"):
            cfg = config_resp["result"]
            self._data = cfg.get("notes", {})
        else:
            self._data = {"_error": config_resp.get("error", "daemon unreachable")}
        self.call_later(self._on_data)

    def _on_data(self) -> None:
        content = self.query_one("#notes-content", Static)
        d = self._data

        if d.get("_error"):
            content.update(f"[red]Daemon unreachable — {d['_error']}[/]")
            return

        lines = [
            "[bold]Notes & Vault[/]",
            "",
            f"Vault directory:     {d.get('vault_dir', '?')}",
            f"Categories:          {', '.join(d.get('categories', []) or []) or '(none configured)'}",
            "",
            f"Fetch timeout:       {d.get('fetch_timeout_seconds', 8)}s",
            f"Max extracted:       {d.get('max_extracted_chars', 2000)} chars",
            f"Low conf → inbox:    {d.get('low_confidence_to_inbox', True)}",
            f"Generate title:      {d.get('generate_title', True)}",
            f"Generate summary:    {d.get('generate_summary', True)}",
            "",
            "[dim]Note management and vault browsing available in the TUI chat.[/]",
        ]
        content.update("\n".join(lines))

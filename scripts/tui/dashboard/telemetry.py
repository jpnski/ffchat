from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from tui.dashboard._daemon import _daemon_post
from tui.dashboard._pane import Pane


class TelemetryPane(Pane):
    """Telemetry pane: latency percentiles, tokens, tok/s."""

    def __init__(self) -> None:
        super().__init__()
        self._data: dict = {}

    def compose(self) -> ComposeResult:
        yield Static("Loading Telemetry…", id="telemetry-content", classes="panel-content")

    def _fetch(self) -> None:
        resp = _daemon_post("stats")
        if resp.get("ok"):
            self._data = resp.get("result") or {}
        else:
            self._data = {"error": resp.get("error", "daemon unreachable")}
        self.call_later(self._on_data)

    def _on_data(self) -> None:
        content = self.query_one("#telemetry-content", Static)
        d = self._data

        if not d or "error" in d:
            content.update(f"[red]Telemetry unavailable: {d.get('error', 'no data')}[/]")
            return

        by_mode = d.get("by_mode", {})
        mode_lines = "\n".join(f"  {k}: {v}" for k, v in sorted(by_mode.items()))

        lines = [
            "[bold]Telemetry[/]",
            "",
            f"Total requests:       {d.get('total', 0)}",
            "",
            "[bold]By Mode[/]",
            mode_lines or "  (no data)",
            "",
            "[bold]Latency (seconds)[/]",
            f"  Average:            {d.get('avg_latency_seconds', 0):.3f}",
            f"  P50:                {d.get('p50_latency_seconds', 0):.3f}",
            f"  P95:                {d.get('p95_latency_seconds', 0):.3f}",
            "",
            "[bold]Tokens[/]",
            f"  Prompt tokens:      {d.get('total_prompt_tokens', 0)}",
            f"  Completion tokens:  {d.get('total_completion_tokens', 0)}",
            "",
            "[bold]Speed[/]",
            f"  Avg tok/s:          {d.get('avg_tok_per_sec', 0):.1f}",
            f"  P50 tok/s:          {d.get('p50_tok_per_sec', 0):.1f}",
        ]
        content.update("\n".join(lines))

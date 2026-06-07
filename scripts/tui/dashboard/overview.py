from __future__ import annotations

from textual.app import ComposeResult
from textual.widgets import Static

from tui.dashboard._pane import Pane
from tui.dashboard._daemon import _daemon_post, _resolve_result


class OverviewPane(Pane):
    """Overview pane: daemon status, model, version, counters."""

    def __init__(self) -> None:
        super().__init__()
        self._data: dict = {}

    def compose(self) -> ComposeResult:
        yield Static("Loading Overview…", id="overview-content", classes="panel-content")

    def _fetch(self) -> None:
        config_resp = _daemon_post("config_snapshot")
        version_resp = _daemon_post("version")
        status_resp = _daemon_post("status")
        stats_resp = _daemon_post("stats")

        result = {}
        if config_resp.get("ok"):
            result["config"] = config_resp["result"]
        else:
            result["_error"] = config_resp.get("error", "daemon unreachable")
        if version_resp.get("ok"):
            result["version"] = _resolve_result(version_resp)
        if status_resp.get("ok"):
            result["status"] = _resolve_result(status_resp)
        if stats_resp.get("ok"):
            result["stats"] = stats_resp["result"]

        self._data = result
        self.call_later(self._on_data)

    def _on_data(self) -> None:
        content = self.query_one("#overview-content", Static)
        d = self._data
        config = d.get("config", {})
        stats = d.get("stats", {})

        if d.get("_error") or not config:
            content.update(f"[red]Daemon unreachable — {d.get('_error', 'no data')}[/]")
            return

        lines = [
            "[bold]Overview[/]",
            "",
            f"Version:   {d.get('version', '?')}",
            f"Status:    {d.get('status', '?')}",
            f"Model:     {config.get('flm_model', '?')}",
            f"Base URL:  {config.get('flm_base_url', '?')}",
            "",
            "[bold]Activity Counters[/]",
            f"Total requests:    {stats.get('total', 0)}",
            f"By mode:           {stats.get('by_mode', {})}",
            f"Avg latency:       {stats.get('avg_latency_seconds', 0):.2f}s",
            "",
            "[bold]Preferences[/]",
            f"Performance mode:  {config.get('server', {}).get('performance_mode', '?')}",
            f"History text:      {'visible' if config.get('history_store_text') else 'redacted'}",
            f"Routing:           {'enabled' if config.get('routing', {}).get('enabled') else 'disabled'}",
            "",
            "[bold]Hotkeys[/]",
        ]
        hotkeys = config.get("hotkeys", {})
        for action, key in sorted(hotkeys.items()):
            lines.append(f"  {action}: {key}")

        hotkey_lines = config.get("hotkeys", {})
        if isinstance(hotkey_lines, dict):
            for action, key in sorted(hotkey_lines.items()):
                lines.append(f"  {action}: {key}")

        content.update("\n".join(lines))

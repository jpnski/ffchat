"""Hotkeys panel — editable transform and interaction hotkeys."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Input, Static

from tui.dashboard import DashboardWidget
from tui.dashboard._daemon import _daemon_post

log = logging.getLogger("flowkey.tui.dashboard")

_TRANSFORM_HOTKEYS: list[tuple[str, str]] = [
    ("summarize", "Summarize"),
    ("grammar", "Grammar fix"),
    ("explain", "Explain code"),
    ("prompt", "Prompt format"),
    ("tone", "Tone shift"),
]

_INTERACTION_HOTKEYS: list[tuple[str, str]] = [
    ("open_chat", "Open chat"),
    ("ask_chat", "Ask model"),
    ("capture_note", "Capture note"),
]


class HotkeysPanel(Vertical):
    """Editable hotkey editor grouped by transform vs interaction actions."""

    DEFAULT_CSS = """
    HotkeysPanel {
        height: auto;
        border: solid $surface;
        padding: 0 1;
        margin: 0;
    }
    HotkeysPanel > .panel-header {
        margin-top: 1;
        margin-bottom: 0;
    }
    .hk-section {
        height: auto;
        margin-top: 1;
    }
    .hk-subsection-title {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
        margin-bottom: 0;
    }
    .hk-grid {
        layout: grid;
        grid-size: 3;
        grid-gutter: 1;
        height: auto;
        margin-top: 1;
    }
    .hk-cell {
        height: auto;
    }
    .hk-label {
        color: $text-muted;
        margin-bottom: 0;
    }
    .hk-input {
        width: 100%;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._saved_values: dict[tuple[str, str], str] = {}
        self._dirty_keys: set[tuple[str, str]] = set()

    def compose(self) -> ComposeResult:
        yield Static("Hotkeys", classes="panel-header")
        yield Static("Transform hotkeys", classes="hk-subsection-title")
        with Vertical(classes="hk-section"):
            with Vertical(classes="hk-grid"):
                for action, label in _TRANSFORM_HOTKEYS:
                    with Vertical(classes="hk-cell"):
                        yield Static(label, classes="hk-label")
                        yield Input(value="", id=f"hk-transform_hotkeys--{action}", classes="hk-input")

        yield Static("Interactive hotkeys", classes="hk-subsection-title")
        with Vertical(classes="hk-section"):
            with Vertical(classes="hk-grid"):
                for action, label in _INTERACTION_HOTKEYS:
                    with Vertical(classes="hk-cell"):
                        yield Static(label, classes="hk-label")
                        yield Input(value="", id=f"hk-interaction_hotkeys--{action}", classes="hk-input")

    # ---- Data ingestion (called by ConfigPane) ----

    def update_hotkeys(self, transform_hotkeys: dict[str, str], interaction_hotkeys: dict[str, str]) -> None:
        """Populate the editor from the config snapshot."""
        for action, _label in _TRANSFORM_HOTKEYS:
            raw = str(transform_hotkeys.get(action, ""))
            key = ("transform_hotkeys", action)
            self._saved_values[key] = raw
            try:
                input_widget = self.query_one(f"#hk-transform_hotkeys--{action}", Input)
                if key not in self._dirty_keys and not getattr(input_widget, "has_focus", False):
                    input_widget.value = raw
            except Exception as exc:
                log.warning("could not update hotkey display for transform_hotkeys/%s: %s", action, exc)

        for action, _label in _INTERACTION_HOTKEYS:
            raw = str(interaction_hotkeys.get(action, ""))
            key = ("interaction_hotkeys", action)
            self._saved_values[key] = raw
            try:
                input_widget = self.query_one(f"#hk-interaction_hotkeys--{action}", Input)
                if key not in self._dirty_keys and not getattr(input_widget, "has_focus", False):
                    input_widget.value = raw
            except Exception as exc:
                log.warning("could not update hotkey display for interaction_hotkeys/%s: %s", action, exc)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Track in-progress edits so refreshes do not overwrite them."""
        input_id = str(event.input.id or "")
        if not input_id.startswith("hk-") or "--" not in input_id:
            return
        body = input_id[3:]
        group, action = body.split("--", 1)
        key = (group, action)
        if key not in self._saved_values:
            return
        if event.value != self._saved_values.get(key, ""):
            self._dirty_keys.add(key)
        else:
            self._dirty_keys.discard(key)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Save hotkey when the user presses Enter in an input field."""
        self._commit_input(event.input.id, event.value)

    def on_input_blurred(self, event: Input.Blurred) -> None:
        """Save hotkey when the user leaves an input field."""
        self._commit_input(event.input.id, event.input.value)

    def _commit_input(self, input_id: str | None, raw_value: str) -> None:
        if not input_id:
            return
        input_id = str(input_id)
        if not input_id.startswith("hk-") or "--" not in input_id:
            return
        body = input_id[3:]
        group, action = body.split("--", 1)
        if group not in {"transform_hotkeys", "interaction_hotkeys"}:
            return

        raw = raw_value.strip()

        key = (group, action)
        current = self._saved_values.get(key, "")
        if raw == current:
            self._dirty_keys.discard(key)
            return  # unchanged

        self._dirty_keys.add(key)
        self.run_worker(
            partial(self._do_save, group, action, raw, current),
            exclusive=True,
        )

    # ---- Persist ----

    async def _do_save(self, group: str, action: str, hotkey_str: str, old_hotkey: str) -> None:
        try:
            resp = await asyncio.to_thread(
                _daemon_post, "apply_config_patch",
                {"patch": {group: {action: hotkey_str}}},
                timeout=2.0,
            )
        except asyncio.CancelledError:
            return  # cancelled by another exclusive worker — ignore

        if resp.get("ok"):
            self._saved_values[(group, action)] = hotkey_str
            self._dirty_keys.discard((group, action))
            self.app.notify(
                f"Hotkey {action}: {hotkey_str}",
                severity="information",
            )
            try:
                self.app.query_one(DashboardWidget).refresh_now()
            except Exception as exc:
                log.warning("could not refresh dashboard after hotkey save: %s", exc)
        else:
            self._dirty_keys.discard((group, action))
            try:
                self.query_one(f"#hk-{group}--{action}", Input).value = old_hotkey
            except Exception as exc:
                log.warning("could not revert hotkey display after error: %s", exc)
            self.app.notify(
                f"Failed to update: {resp.get('error', 'unknown')}",
                severity="error", timeout=5,
            )

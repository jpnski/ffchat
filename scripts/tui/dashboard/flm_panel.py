"""FLM Model panel (top of Config tab)."""

from __future__ import annotations

import asyncio
import logging
import time
from functools import partial
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Button, Collapsible, ListItem, ListView, ProgressBar, Select, Static

from tui.dashboard._daemon import _daemon_post, _DAEMON_TIMEOUT_DEFAULT, _DAEMON_TIMEOUT_MODEL_CHANGE, _DAEMON_TIMEOUT_PULL_START, _DAEMON_TIMEOUT_PULL_CANCEL

class ModelListItem(ListItem):
    """ListItem that carries a model name. Avoids invalid DOM ids for `gemma4-it:e4b`."""

    def __init__(self, model_name: str) -> None:
        super().__init__(Static(model_name), id=f"flm-dl-{_safe_id(model_name)}")
        self.model_name = model_name


def _safe_id(name: str) -> str:
    """Encode a string so it is a valid Textual DOM identifier (no colons, etc.)."""
    return "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in name)


_RESTART_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class FlmModelPanel(Vertical):
    """Interactive FLM model block for the Config tab.

    Provides:
    - A `Select` to switch the active model (lists installed models).
    - A `Button` that toggles a `Collapsible` containing a `ListView` of
      not-yet-installed models. Pressing Enter on a row starts a pull.
    - A `ProgressBar` + status line for in-flight pull progress.
    - A second indeterminate `ProgressBar` + spinner while the FLM server
      is being restarted on an active-model change.
    """

    DEFAULT_CSS = """
    FlmModelPanel {
        height: auto;
        border: solid $surface;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    .flm-section-label {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }
    #flm-active-model-select { margin-bottom: 1; }
    #flm-pull-status-line { color: $text-muted; margin-top: 1; }
    #flm-pull-progress { display: none; }
    #flm-restart-progress { display: none; }
    #flm-cancel-pull-btn { display: none; }
    #flm-pull-progress.active,
    #flm-restart-progress.active,
    #flm-cancel-pull-btn.active { display: block; }
    """

    # Reactive state for the restarting spinner.
    restarting: reactive[bool] = reactive(False)
    restart_label: reactive[str] = reactive("")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._installed_models: list[str] = []
        self._not_installed_models: list[str] = []
        self._active_model: str = ""
        self._prior_active: str = ""
        self._spinner_index: int = 0
        self._pull_in_flight: bool = False
        self._list_populated: bool = False
        self._daemon_reachable: bool = True
        self._last_model_change_at: float = 0.0
        # Whether the FLM server is reachable and the model is confirmed loaded.
        self._model_loaded: bool = False
        # Tracks the last time _refresh_select (or the revert path in
        # _apply_model_change) programmatically mutated the Select widget.
        # Any Select.Changed firing within 1 s of this timestamp is treated
        # as a spurious side-effect of set_options() and suppressed.
        self._last_select_refresh_at: float = 0.0
        # Set of model names last passed to Select.set_options. If unchanged
        # on the next _refresh_select call, set_options is skipped entirely,
        # avoiding the spurious first-option default Select.Changed event.
        self._last_select_options: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("FLM Model", classes="panel-header")
        yield Static("Active model", classes="flm-section-label")
        yield Select(
            options=[("(no model loaded)", "")],
            value="",
            allow_blank=False,
            prompt="Choose installed model…",
            id="flm-active-model-select",
            disabled=True,
        )
        yield ProgressBar(total=None, show_eta=False, id="flm-restart-progress")
        yield Static("", id="flm-restart-status-line", classes="flm-section-label")
        yield Static("Download a model", classes="flm-section-label")
        yield Collapsible(
            Vertical(
                Static("", id="flm-empty-download-msg"),
                ListView(id="flm-download-list"),
            ),
            title="Download a model",
            collapsed=True,
            id="flm-download-collapse",
        )
        yield Static("", id="flm-pull-status-line")
        yield ProgressBar(total=100, show_eta=False, id="flm-pull-progress")
        yield Button("Cancel pull", id="flm-cancel-pull-btn")

    def on_mount(self) -> None:
        self.set_interval(1.0, self._refresh_pull_status)
        self.set_interval(0.15, self._tick_restart_spinner)

    # ---- Data ingestion (called by DashboardWidget) ----

    def update_models(self, installed: list[str], not_installed: list[str],
                      active: str, model_loaded: bool = False,
                      *, daemon_reachable: bool = True) -> None:
        """Refresh installed/not-installed lists and active model.

        Idempotent: only re-populates the Select / ListView when something
        actually changed. Preserves user focus on the Select where possible.
        """
        self._daemon_reachable = daemon_reachable
        self._installed_models = list(installed)
        self._not_installed_models = list(not_installed)
        self._model_loaded = model_loaded
        self._active_model = active if model_loaded else ""

        self._refresh_select()
        if not self._list_populated:
            self._refresh_download_list()
            self._list_populated = True

    def mark_daemon_down(self) -> None:
        """Render the panel into its unreachable state."""
        self._daemon_reachable = False
        self._active_model = ""
        self._installed_models = []
        self._not_installed_models = []
        self._list_populated = False
        status = self.query_one("#flm-pull-status-line", Static)
        status.update("[red]Daemon unreachable — cannot list models[/]")
        self._set_select_enabled(False)
        try:
            self.query_one("#flm-cancel-pull-btn", Button).remove_class("active")
        except Exception:
            pass

    # ---- Internal renderers ----

    def _refresh_select(self) -> None:
        select = self.query_one("#flm-active-model-select", Select)
        if not self._installed_models:
            self._last_select_refresh_at = time.monotonic()
            select.set_options([("(no models installed)", "")])
            self._set_select_enabled(False)
            self._last_select_options = []
            return

        # Always include the persistent "(none)" option at position 0, followed
        # by installed model names.  Users can select "(none)" to explicitly
        # unload the active model from memory.
        options = [("(none)", "")] + [
            (name, name) for name in self._installed_models
        ]

        # Rebuild options only when the installed list changes.  Calling
        # set_options unnecessarily triggers a spurious Select.Changed
        # (suppressed below by _last_select_refresh_at).
        if self._installed_models != self._last_select_options:
            self._last_select_refresh_at = time.monotonic()
            select.set_options(options)
            self._last_select_options = list(self._installed_models)

        if not self._model_loaded:
            # No model loaded — select "(none)".
            select.value = ""
        elif self._active_model and self._active_model in self._installed_models:
            select.value = self._active_model
        else:
            select.value = self._installed_models[0]
        self._set_select_enabled(not self.restarting)

    def _refresh_download_list(self) -> None:
        list_view = self.query_one("#flm-download-list", ListView)
        list_view.clear()
        for name in self._not_installed_models:
            list_view.append(ModelListItem(name))
        # Update the empty-list message inside the Collapsible.
        empty_msg = self.query_one("#flm-empty-download-msg", Static)
        if not self._not_installed_models:
            empty_msg.update("[dim]All available models are already installed.[/]")
        else:
            empty_msg.update("")

    def _set_select_enabled(self, enabled: bool) -> None:
        try:
            select = self.query_one("#flm-active-model-select", Select)
            select.disabled = not enabled
        except Exception:
            pass

    # ---- Pollers ----

    def _refresh_pull_status(self) -> None:
        resp = _daemon_post("pull_status")
        if not resp.get("ok"):
            return
        result = resp.get("result") or {}
        state = str(result.get("state") or "idle")
        model = str(result.get("model") or "")
        percent = float(result.get("percent") or 0.0)
        message = str(result.get("message") or "")
        error = str(result.get("error") or "")

        progress = self.query_one("#flm-pull-progress", ProgressBar)
        status = self.query_one("#flm-pull-status-line", Static)
        cancel_btn = self.query_one("#flm-cancel-pull-btn", Button)

        if state == "running":
            progress.add_class("active")
            progress.update(progress=percent)
            cancel_btn.add_class("active")
            status.update(f"Pulling [bold]{model}[/]: {percent:.1f}% — {message or 'starting…'}")
            self._pull_in_flight = True
        elif state == "done":
            progress.add_class("active")
            progress.update(progress=100.0)
            cancel_btn.remove_class("active")
            status.update(f"[green]✓ Pulled {model}[/]")
            self._pull_in_flight = False
            self._list_populated = False
            self._refresh_download_list()
            self._list_populated = True
        elif state == "cancelled":
            progress.remove_class("active")
            cancel_btn.remove_class("active")
            status.update("[yellow]⊘ Pull cancelled[/]")
            self._pull_in_flight = False
        elif state == "error":
            progress.remove_class("active")
            cancel_btn.remove_class("active")
            status.update(f"[red]✗ Pull failed: {error or 'unknown error'}[/]")
            self._pull_in_flight = False
        else:  # idle
            if self._pull_in_flight:
                self._pull_in_flight = False
            cancel_btn.remove_class("active")
            if not self.restarting and not self._not_installed_models and not self._installed_models:
                pass  # leave the "unreachable" / "all installed" message in place

    def _tick_restart_spinner(self) -> None:
        if not self.restarting:
            return
        self._spinner_index = (self._spinner_index + 1) % len(_RESTART_SPINNER)
        glyph = _RESTART_SPINNER[self._spinner_index]
        try:
            line = self.query_one("#flm-restart-status-line", Static)
            line.update(f"[yellow]{glyph} {self.restart_label}[/]")
        except Exception:
            pass

    # ---- Event handlers ----

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "flm-active-model-select":
            return
        new_value = str(event.value or "")

        # Suppress spurious Select.Changed triggered by set_options() in
        # _refresh_select or the revert path.  These fire within the same
        # event-loop iteration as the programmatic mutation, always < 1 s.
        if time.monotonic() - self._last_select_refresh_at < 1.0:
            return

        if not self._installed_models:
            return

        select = event.select

        # Chat-stream guard (applies to both unloading and switching).
        is_streaming = False
        try:
            from tui.chat import ChatWidget  # local import to avoid cycles
            chat = self.app.query_one(ChatWidget)
            if chat.is_streaming():
                is_streaming = True
        except Exception:
            pass

        # --- "(none)" selected → unload the model ---
        if not new_value:
            if self._model_loaded:
                if is_streaming:
                    self.app.notify(
                        "Chat is streaming — finish or cancel before unloading the model",
                        severity="warning", timeout=6,
                    )
                    select.value = self._active_model
                    return
                self.run_worker(self._unload_model, exclusive=True)
            return

        # --- A real model was selected ---
        if new_value == self._active_model:
            return
        now = time.monotonic()
        if now - self._last_model_change_at < 10.0:
            return
        if is_streaming:
            self.app.notify(
                "Chat is streaming — finish or cancel before changing the model",
                severity="warning", timeout=6,
            )
            if self._active_model:
                select.value = self._active_model
            else:
                select.value = self._installed_models[0]
            return

        self._prior_active = self._active_model
        self._last_model_change_at = time.monotonic()
        self.run_worker(partial(self._apply_model_change, new_value), exclusive=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "flm-cancel-pull-btn":
            self.run_worker(self._cancel_pull, exclusive=True)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "flm-download-list":
            return
        item = event.item
        if not isinstance(item, ModelListItem):
            return
        model = item.model_name
        if not model:
            return
        if self._pull_in_flight:
            self.app.notify("A pull is already in progress", severity="warning", timeout=4)
            return
        self.run_worker(partial(self._start_pull, model), exclusive=True)

    # ---- Workers ----

    async def _apply_model_change(self, new_value: str) -> None:
        self._set_select_enabled(False)
        self.restarting = True
        self.restart_label = f"Restarting FLM server on {new_value}…"
        self.query_one("#flm-restart-progress", ProgressBar).add_class("active")
        self.query_one("#flm-restart-status-line", Static).update(
            f"[yellow]{_RESTART_SPINNER[0]} {self.restart_label}[/]"
        )

        try:
            resp = await asyncio.to_thread(
                _daemon_post, "apply_config_patch", {"patch": {"flm_model": new_value}},
                timeout=_DAEMON_TIMEOUT_MODEL_CHANGE,
            )
            if not resp.get("ok"):
                raise RuntimeError(str(resp.get("error") or "unknown error"))
            self.app.notify(f"Active model: {new_value}", severity="information")
            # Push the new model name to the chat footer FIRST — this is a
            # simple in-process assignment that returns instantly.  Must run
            # before refresh_now() which blocks the event loop for seconds
            # making 11 synchronous HTTP requests while FLM restarts.
            try:
                from tui.chat import ChatWidget
                chat = self.app.query_one(ChatWidget)
                chat.set_model(new_value)
            except Exception:
                pass
            # Refresh the parent's view of the active model and the installed
            # list.  This makes multiple HTTP requests and may take seconds.
            try:
                from tui.dashboard import DashboardWidget  # local import to avoid cycles
                self.app.query_one(DashboardWidget).refresh_now()
            except Exception:
                pass
        except Exception as exc:
            self.app.notify(
                f"Model change failed: {exc}", severity="error", timeout=8
            )
            # Revert the Select visually.
            try:
                select = self.query_one("#flm-active-model-select", Select)
                self._last_select_refresh_at = time.monotonic()
                if self._prior_active:
                    select.value = self._prior_active
                elif self._installed_models:
                    select.value = self._installed_models[0]
            except Exception:
                pass
        finally:
            self.restarting = False
            self.restart_label = ""
            self.query_one("#flm-restart-progress", ProgressBar).remove_class("active")
            self.query_one("#flm-restart-status-line", Static).update("")
            self._set_select_enabled(True)

    async def _unload_model(self) -> None:
        """Stop the FLM server and reset UI state.

        Called when the user explicitly selects (none) from the Select
        dropdown while a model is loaded.
        """
        try:
            resp = await asyncio.to_thread(
                _daemon_post, "stop", {"args": {}}, timeout=5.0,
            )
            if resp.get("ok") and resp.get("result") == "stopped":
                self.app.notify(
                    "Model unloaded from memory",
                    severity="information", timeout=4,
                )
            elif resp.get("ok") and resp.get("result") == "not_running":
                self.app.notify(
                    "No model was loaded",
                    severity="information", timeout=4,
                )
            else:
                self.app.notify(
                    f"Failed to unload: {resp.get('error', 'unknown')}",
                    severity="error", timeout=6,
                )
        except Exception as exc:
            self.app.notify(
                f"Failed to unload: {exc}", severity="error", timeout=6,
            )
            return

        self._model_loaded = False
        self._active_model = ""
        try:
            from tui.chat import ChatWidget
            chat = self.app.query_one(ChatWidget)
            chat.set_model("")
        except Exception:
            pass
        # Suppress the Select.Changed that _refresh_select triggers when it
        # sets select.value = "" — the user *just* picked (none) intentionally.
        self._last_select_refresh_at = time.monotonic()
        self._refresh_select()

    async def _start_pull(self, model: str) -> None:
        self._set_select_enabled(False)
        try:
            resp = await asyncio.to_thread(
                _daemon_post, "pull_start", {"model": model},
                timeout=_DAEMON_TIMEOUT_PULL_START,
            )
            if not resp.get("ok"):
                raise RuntimeError(str(resp.get("error") or "unknown error"))
            self.app.notify(f"Started pulling {model}", severity="information")
        except Exception as exc:
            self.app.notify(
                f"Pull start failed: {exc}", severity="error", timeout=8
            )
        finally:
            self._set_select_enabled(True)

    async def _cancel_pull(self) -> None:
        try:
            resp = await asyncio.to_thread(
                _daemon_post, "pull_cancel", timeout=_DAEMON_TIMEOUT_PULL_CANCEL,
            )
            if not resp.get("ok"):
                raise RuntimeError(str(resp.get("error") or "unknown error"))
            self.app.notify("Pull cancelled", severity="information", timeout=4)
        except Exception as exc:
            self.app.notify(
                f"Cancel failed: {exc}", severity="error", timeout=6
            )

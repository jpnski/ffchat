from __future__ import annotations

from functools import partial
from types import SimpleNamespace


def test_config_pane_uses_scroll_root(fresh_modules):
    config_pane = fresh_modules("tui.dashboard.config_pane")

    assert "VerticalScroll" in config_pane.ConfigPane.compose.__code__.co_names
    assert "#config-tab-root" in config_pane.ConfigPane.DEFAULT_CSS
    assert "height: 100%;" in config_pane.ConfigPane.DEFAULT_CSS


def test_hotkeys_panel_splits_transform_and_interaction_sections(fresh_modules):
    hotkeys = fresh_modules("tui.dashboard.config_pane.hotkeys")

    consts = {c for c in hotkeys.HotkeysPanel.compose.__code__.co_consts if isinstance(c, str)}

    assert "Transform hotkeys" in consts
    assert "Interactive hotkeys" in consts
    assert "hk-grid" in consts
    assert any("hk-transform_hotkeys" in c for c in consts)
    assert any("hk-interaction_hotkeys" in c for c in consts)


def test_hotkeys_panel_allows_blank_submission(fresh_modules, monkeypatch):
    hotkeys = fresh_modules("tui.dashboard.config_pane.hotkeys")
    panel = hotkeys.HotkeysPanel()

    fake_input = SimpleNamespace(id="hk-transform_hotkeys--grammar")
    panel._saved_values[("transform_hotkeys", "grammar")] = "Ctrl+Shift+G"

    calls = []
    monkeypatch.setattr(panel, "run_worker", lambda fn, exclusive=True: calls.append(fn))

    panel.on_input_submitted(SimpleNamespace(input=fake_input, value=""))

    assert len(calls) == 1
    assert isinstance(calls[0], partial)
    assert calls[0].args[2] == ""


def test_hotkeys_panel_saves_on_blur_without_enter(fresh_modules, monkeypatch):
    hotkeys = fresh_modules("tui.dashboard.config_pane.hotkeys")
    panel = hotkeys.HotkeysPanel()

    fake_input = SimpleNamespace(id="hk-interaction_hotkeys--open_chat", value="Ctrl+Alt+O")
    panel._saved_values[("interaction_hotkeys", "open_chat")] = "ctrl+alt+t"

    calls = []
    monkeypatch.setattr(panel, "run_worker", lambda fn, exclusive=True: calls.append(fn))

    panel.on_input_blurred(SimpleNamespace(input=fake_input))

    assert len(calls) == 1
    assert isinstance(calls[0], partial)
    assert calls[0].args[2] == "Ctrl+Alt+O"


def test_hotkeys_panel_preserves_dirty_input_during_refresh(fresh_modules):
    hotkeys = fresh_modules("tui.dashboard.config_pane.hotkeys")
    panel = hotkeys.HotkeysPanel()

    fake_inputs = {
        "#hk-transform_hotkeys--grammar": SimpleNamespace(id="hk-transform_hotkeys--grammar", value="Ctrl+Shift+G", has_focus=False),
        "#hk-interaction_hotkeys--open_chat": SimpleNamespace(id="hk-interaction_hotkeys--open_chat", value="ctrl+alt+t", has_focus=False),
    }

    panel.query_one = lambda selector, _type=None: fake_inputs[selector]

    panel.update_hotkeys(
        {"grammar": "Ctrl+Shift+G"},
        {"open_chat": "ctrl+alt+t"},
    )

    fake_inputs["#hk-transform_hotkeys--grammar"].value = "Custom value"
    panel.on_input_changed(SimpleNamespace(input=fake_inputs["#hk-transform_hotkeys--grammar"], value="Custom value"))

    panel.update_hotkeys(
        {"grammar": "Ctrl+Shift+G"},
        {"open_chat": "ctrl+alt+t"},
    )

    assert fake_inputs["#hk-transform_hotkeys--grammar"].value == "Custom value"

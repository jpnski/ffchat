from __future__ import annotations


def test_flowkey_tui_argv_uses_configured_terminal(monkeypatch):
    import launcher

    def fake_which(name: str):
        mapping = {
            "flowkey": "/usr/bin/flowkey",
            "kitty": "/usr/bin/kitty",
        }
        return mapping.get(name)

    monkeypatch.setattr(launcher.shutil, "which", fake_which)

    argv = launcher.flowkey_tui_argv("")

    assert argv == ["/usr/bin/kitty", "--", "/usr/bin/flowkey", "tui"]


def test_flowkey_tui_argv_uses_explicit_terminal(monkeypatch):
    import launcher

    def fake_which(name: str):
        return {"flowkey": "/usr/bin/flowkey"}.get(name)

    monkeypatch.setattr(launcher.shutil, "which", fake_which)

    argv = launcher.flowkey_tui_argv("alacritty --class flowkey")

    assert argv == ["alacritty", "--class", "flowkey", "-e", "/usr/bin/flowkey", "tui"]


def test_flowkey_tui_argv_returns_none_without_terminal(monkeypatch):
    import launcher

    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/bin/flowkey" if name == "flowkey" else None)

    assert launcher.flowkey_tui_argv("") is None

"""Shared launcher helpers for Flowkey command invocation."""

from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path


_TERMINAL_FALLBACKS: tuple[str, ...] = ("kitty", "alacritty", "foot", "gnome-terminal")


def flowkey_argv(*args: str) -> list[str]:
    """Return the best command vector for launching the top-level `flowkey` CLI."""
    which = shutil.which("flowkey")
    if which:
        return [which, *args]
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve()), *args]
    return [sys.executable, str(Path(__file__).resolve().with_name("flowkey.py")), *args]


def flowkey_tui_argv(terminal: str = "") -> list[str] | None:
    """Return a terminal command that launches `flowkey tui`, or None if unavailable."""
    flowkey_cmd = flowkey_argv("tui")

    terminal_argv: list[str] = []
    if terminal.strip():
        try:
            terminal_argv = shlex.split(terminal)
        except ValueError:
            terminal_argv = []
    else:
        for name in _TERMINAL_FALLBACKS:
            which = shutil.which(name)
            if which:
                terminal_argv = [which]
                break

    if not terminal_argv:
        return None

    exe = Path(terminal_argv[0]).name
    if exe == "kitty":
        return [*terminal_argv, "--", *flowkey_cmd]
    if exe in {"alacritty", "foot"}:
        return [*terminal_argv, "-e", *flowkey_cmd]
    if exe == "gnome-terminal":
        return [*terminal_argv, "--", *flowkey_cmd]

    return [*terminal_argv, *flowkey_cmd]

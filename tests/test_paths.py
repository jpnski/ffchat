"""Tests for paths.py (Linux-only)."""

from __future__ import annotations

import sys
from pathlib import Path


def test_paths_use_checkout_layout(fresh_modules):
    paths = fresh_modules("paths")
    root = Path(paths.__file__).resolve().parent.parent

    assert paths.INSTALL_MODE == "dev"
    assert paths.APP_DIR == root
    assert paths.USER_ROOT == root
    assert paths.CONFIG_FILE == root / "config.json"
    assert paths.DATA_DIR == root / "data"
    assert paths.LOGS_DIR == root / "logs"


def test_paths_use_xdg_when_frozen(monkeypatch, fresh_modules, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    xdg_data_home = tmp_path / "xdg" / "share"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))

    paths = fresh_modules("paths")
    root = Path(paths.__file__).resolve().parent.parent
    xdg_root = xdg_data_home / "Flowkey"

    assert paths.INSTALL_MODE == "deployed"
    assert paths.APP_DIR == root
    assert paths.USER_ROOT == xdg_root
    assert paths.CONFIG_FILE == xdg_root / "config.json"
    assert paths.DATA_DIR == xdg_root / "data"
    assert paths.LOGS_DIR == xdg_root / "logs"


def test_user_local_root_falls_back_to_home_dot_local(monkeypatch, fresh_modules, tmp_path):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    home = tmp_path / "home" / "testuser"
    monkeypatch.setenv("HOME", str(home))

    paths = fresh_modules("paths")

    assert paths._user_local_root() == home / ".local" / "share" / "Flowkey"


def test_ensure_dirs_creates_runtime_folders(fresh_modules):
    paths = fresh_modules("paths")

    paths.ensure_dirs()

    assert paths.CONFIG_FILE.parent.exists()
    assert paths.DATA_DIR.exists()
    assert paths.LOGS_DIR.exists()

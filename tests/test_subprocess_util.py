from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import subprocess_util


def test_run_flm_strips_bundle_library_path(monkeypatch, tmp_path):
    capture: dict = {}
    bundle_root = tmp_path / "flowkey" / "current" / "_internal"

    def _fake_run(argv, **kwargs):
        capture["argv"] = list(argv)
        capture["kwargs"] = dict(kwargs)
        capture["env"] = dict(kwargs.get("env") or {})
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess_util.subprocess, "run", _fake_run)
    monkeypatch.setattr(
        subprocess_util,
        "_bundle_library_dirs",
        lambda: (bundle_root,),
    )

    env = {
        "CUSTOM": "1",
        "LD_LIBRARY_PATH": str(bundle_root),
        "LD_PRELOAD": "libsomething.so",
    }

    subprocess_util.run_flm(["flm", "version"], env=env)

    assert capture["argv"] == ["flm", "version"]
    assert capture["kwargs"].get("capture_output") is True
    assert capture["kwargs"].get("text") is True
    assert capture["kwargs"].get("check") is False
    assert capture["env"] == {"CUSTOM": "1", "LD_PRELOAD": "libsomething.so"}
    assert env["LD_LIBRARY_PATH"] == str(bundle_root)


def test_popen_flm_strips_bundle_library_path(monkeypatch, tmp_path):
    capture: dict = {}
    bundle_root = tmp_path / "flowkey" / "current" / "_internal"

    def _fake_popen(argv, **kwargs):
        capture["argv"] = list(argv)
        capture["env"] = dict(kwargs.get("env") or {})
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(subprocess_util.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(
        subprocess_util,
        "_bundle_library_dirs",
        lambda: (bundle_root,),
    )

    env = {
        "PATH": "/usr/bin",
        "LD_LIBRARY_PATH": f"{bundle_root}:/opt/xilinx/xrt/lib",
    }

    proc = subprocess_util.popen_flm(["flm", "pull", "gemma4-it:e4b"], env=env)

    assert proc.pid == 12345
    assert capture["argv"] == ["flm", "pull", "gemma4-it:e4b"]
    assert capture["env"] == {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/opt/xilinx/xrt/lib"}


def test_popen_flm_strips_onefile_bundle_path(monkeypatch):
    capture: dict = {}

    def _fake_popen(argv, **kwargs):
        capture["argv"] = list(argv)
        capture["env"] = dict(kwargs.get("env") or {})
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(subprocess_util.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(
        subprocess_util,
        "_bundle_library_dirs",
        lambda: (Path("/tmp/_MEIviVWIw"),),
    )

    env = {
        "PATH": "/usr/bin",
        "LD_LIBRARY_PATH": "/tmp/_MEIviVWIw:/opt/xilinx/xrt/lib",
    }

    proc = subprocess_util.popen_flm(["flm", "serve", "gemma4-it:e4b"], env=env)

    assert proc.pid == 12345
    assert capture["argv"] == ["flm", "serve", "gemma4-it:e4b"]
    assert capture["env"] == {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/opt/xilinx/xrt/lib"}

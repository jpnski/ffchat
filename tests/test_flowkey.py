from __future__ import annotations

from types import SimpleNamespace


def test_flowkey_help_lists_subcommands(capsys):
    import flowkey

    rc = flowkey.main(["--help"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "usage: flowkey <command>" in out
    assert "daemon" in out
    assert "process" in out
    assert "tui" in out


def test_flowkey_unknown_command_returns_2(capsys):
    import flowkey

    rc = flowkey.main(["bogus"])

    err = capsys.readouterr().err
    assert rc == 2
    assert "Unknown command" in err


def test_flowkey_dispatches_to_subcommand(monkeypatch):
    import flowkey

    seen = {}

    def fake_import(name: str):
        def fake_main(argv):
            seen[name] = list(argv)
            return 0

        return SimpleNamespace(main=fake_main)

    monkeypatch.setattr(flowkey.importlib, "import_module", fake_import)

    rc = flowkey.main(["process", "--mode", "grammar", "--input-file", "in.txt"])

    assert rc == 0
    assert seen == {"engine": ["--mode", "grammar", "--input-file", "in.txt"]}


def test_flowkey_process_forwards_empty_argv(monkeypatch):
    import flowkey

    seen = {}

    def fake_import(name: str):
        def fake_main(argv):
            seen[name] = list(argv)
            return 0

        return SimpleNamespace(main=fake_main)

    monkeypatch.setattr(flowkey.importlib, "import_module", fake_import)

    rc = flowkey.main(["process"])

    assert rc == 0
    assert seen == {"engine": []}

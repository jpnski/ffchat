# Flowkey

Flowkey is a Windows desktop assistant that adds local-LLM hotkeys for grammar fixes, prompt rewrites, summaries, explanations, tone changes, chat, ask-in-chat, and note capture.

All model calls stay on the local machine through [FastFlowLM](https://fastflowlm.com). No cloud service, analytics, or telemetry is used by the app.

## Requirements

- Windows 10/11 x64
- AMD Ryzen AI NPU hardware supported by FastFlowLM
- Python 3.11+ for source/developer installs
- AutoHotkey v2+ for source installs
- FastFlowLM (`flm`) with a local model such as `qwen3.5:4b`

## Install

For normal users, use the GitHub release installer when available:

1. Open the repository's **Releases** page.
2. Download `Flowkey-Setup-<version>.exe`.
3. Double-click it and finish the first-run wizard.

For source installs from a clone or zip:

```powershell
cd release
.\INSTALL.cmd
```

More install details are in [`release/README.md`](release/README.md).

## Repository Layout

- `release/` - the runnable application, installer scripts, package metadata, and tests.
- `release/scripts/` - Python modules and AutoHotkey v2 scripts.
- `release/installer/` - Inno Setup, PyInstaller, signing, and installer build scripts.
- `release/setup/defaults/` - first-run seed configuration shipped with the installer.
- `release/tests/` - Python and AutoHotkey regression tests.
- `docs/` - publishing and manual regression documentation.
- `.github/workflows/` - CI and release-installer workflows.

Runtime data, logs, build output, downloaded vendor binaries, caches, and local editor/agent state are intentionally ignored and should not be committed.

## Development Checks

```powershell
python -m pip install -e ".\release[dev]"
ruff check release/scripts release/tests
pytest release/tests -q
```

AutoHotkey tests are run by CI on Windows. Locally, run them with AutoHotkey v2:

```powershell
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" /ErrorStdOut release\tests\test_parse_mode.ahk
& "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" /ErrorStdOut release\tests\test_classify_clipboard.ahk
```

## Publish To GitHub

Use [`docs/GITHUB_DEPLOYMENT.md`](docs/GITHUB_DEPLOYMENT.md) for the full step-by-step checklist: cleanup, validation, repository creation, CI secrets, tagging, and release publishing.

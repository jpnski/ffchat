# GitHub Deployment Guide

This guide prepares Flowkey for a public GitHub repository and a GitHub Release installer.

## 1. Finalize Public Metadata

Replace placeholder repository URLs before the first public release:

- `release/pyproject.toml`: `https://github.com/agr77one/Fastflow`
- `release/installer/installer.iss`: `#define AppURL`
- Any README link that points at the repository URL

Keep these version values in sync for each release:

- `release/scripts/_version.py`
- `release/pyproject.toml`
- `release/installer/installer.iss`
- `release/CHANGELOG.md`

## 2. Clean The Working Tree

From the repository root:

```powershell
git status --short
git status --short --ignored
```

Do not commit these generated or private files:

- `release/data/`
- `release/logs/`
- `release/build/`
- `release/dist/`
- `release/out/`
- `release/vendor/ahk/`
- `release/vendor/flm/`
- `release/scripts/.venv/`
- `release/config/grammar_hotkey.config.json`
- `.cursor/`, `.claude/`, `.ruff_cache/`, `.pytest_cache/`, `__pycache__/`

Preview ignored cleanup safely:

```powershell
git clean -ndX
```

Only after reviewing the preview, remove ignored generated files:

```powershell
git clean -fdX
```

## 3. Validate Locally

Install development tools:

```powershell
python -m pip install -e ".\release[dev]"
```

Run Python validation:

```powershell
ruff check release/scripts release/tests
pytest release/tests -q
```

Run AutoHotkey tests if AutoHotkey v2 is installed:

```powershell
$ahk = "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
& $ahk /ErrorStdOut release\tests\test_parse_mode.ahk
& $ahk /ErrorStdOut release\tests\test_classify_clipboard.ahk
```

Build the installer locally when you want to verify packaging:

```powershell
.\release\installer\bootstrap.ps1 -Build
```

The output should be under `release/out/Flowkey-Setup-<version>.exe`.

## 4. Create The GitHub Repository

Create an empty repository on GitHub, then connect and push:

```powershell
git remote add origin https://github.com/agr77one/Fastflow.git
git branch -M main
git add .
git commit -m "Prepare Flowkey for public release"
git push -u origin main
```

If this repository already has commits, inspect first:

```powershell
git status
git diff
git log --oneline -10
```

## 5. Configure GitHub Actions Secrets

Installer signing is optional. Without signing secrets, CI still builds an unsigned installer artifact.

To sign in GitHub Actions, create a `.pfx` locally:

```powershell
cd release\installer
$env:FFP_SIGN_PFX_PASSWORD = "choose-a-strong-password"
.\sign.ps1 -GenerateCert
```

Add these repository secrets in GitHub under **Settings -> Secrets and variables -> Actions**:

- `FFP_SIGN_PFX_B64`: base64 text for `release/installer/certs/fastflowprompt.pfx`
- `FFP_SIGN_PFX_PASSWORD`: the `.pfx` password

Create `FFP_SIGN_PFX_B64` with:

```powershell
[Convert]::ToBase64String(
  [IO.File]::ReadAllBytes("release\installer\certs\fastflowprompt.pfx")
) | Set-Clipboard
```

Never commit `.pfx` files or passwords.

## 6. Publish A Release

Update `release/CHANGELOG.md`, commit the release, tag it, and push the tag:

```powershell
git add release/scripts/_version.py release/pyproject.toml release/installer/installer.iss release/CHANGELOG.md
git commit -m "Release v1.5.0"
git tag v1.5.0
git push origin main
git push origin v1.5.0
```

The `Build & release installer` workflow builds `Flowkey-Setup-<version>.exe` and uploads it to the GitHub Release.

## 7. Smoke Test The Release

On a clean Windows machine with supported AMD Ryzen AI hardware:

1. Download `Flowkey-Setup-<version>.exe` from GitHub Releases.
2. Run the installer and accept SmartScreen if using a self-signed build.
3. Complete the first-run wizard.
4. Press `Ctrl+Shift+G` on selected text.
5. Open the dashboard from the tray and confirm Overview, Telemetry, History, Notes, Config, and Benchmark render.
6. Uninstall from Windows Apps and confirm app files, autostart, and optional user data cleanup behave as expected.

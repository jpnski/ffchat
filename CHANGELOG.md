# Changelog

## 2.0.0-dev — Linux Port

First Linux-compatible release of the FastFlowPrompt/Flowkey desktop assistant.

### Added (Phase 4 — Textual TUI)

- **`flowkey-tui`** — new Textual-based terminal UI replacing the tkinter chat popup and dashboard
  - Tabbed interface: Chat (streaming markdown) and Dashboard (multi-panel)
  - Streaming LLM responses via SSE from the local FLM endpoint
  - Slash-commands: `/grammar`, `/summarize`, `/explain`, `/prompt`, `/tone`, `/clear`, `/help`
  - Dashboard panels: Overview, Telemetry, History, Notes, Config, Benchmark
  - Keyboard-driven: `Ctrl+1/2` for tabs, `Ctrl+P` command palette, `Ctrl+Q` quit
- **`scripts/tray.py`** — system tray indicator using `pystray` (X11) with graceful Wayland fallback
  - Menu: Open TUI, Server submenu (Status/Start/Stop/Warmup), Performance toggles, Exit
- `textual>=8.0` added as core dependency
- `evdev` and `dasbus` in Wayland optional deps

### Changed

- `pyproject.toml`: fixed `python-evdev>=1.7` → `evdev>=1.7` (correct PyPI name)
- `chat_popup.py` and `dashboard.py`: marked DEPRECATED — replaced by `flowkey-tui`

### Added (Phase 1-3 consolidated)

- Linux-native path resolution via `$XDG_DATA_HOME` / `~/.local/share`
- XDG autostart `.desktop` file support (replaces Windows Registry Run key)
- `notify-send` desktop notifications (replaces PowerShell toasts)
- Linux process management via `os.kill()`, `/proc/`, `ss -tlnp` (replaces `tasklist`/`taskkill`/`netstat`)
- `pyproject.toml` optional dependencies for X11 (`pynput`) and Wayland (`evdev`, `dasbus`)
- New console scripts: `flowkey-listener`, `flowkey-tray`, `flowkey-dashboard`, `flowkey-tui`
- Global hotkey listener (`listener.py`) with pynput (X11) and evdev (Wayland) backends
- Clipboard capture, mode prefix parsing, daemon dispatch

### Changed

- **Pure Linux codebase** — all Windows-specific code removed (AutoHotkey, PowerShell, WinAPI, Registry)
- `paths.py` — `_is_under_program_files()` → `_is_under_prefix()`, uses XDG base dir spec
- `subprocess_util.py` — no `CREATE_NO_WINDOW` flags
- `notify.py` — `notify-send` with stderr fallback (was `ffp_notify.py`)
- `flm_server.py` — `is_pid_alive()` uses `os.kill(pid, 0)`, `kill_pid()` uses `os.kill(pid, SIGTERM)`, `find_pids_on_port()` uses `ss -tlnp` (was `ffp_flm_server.py`)
- `daemon.py` — parent-PID watching via `/proc/` polling; autostart via XDG `.desktop` file (was `ffp_daemon.py`)
- `first_run.py` — NPU detection via `flm validate` instead of PowerShell
- `install.py` — Linux system setup (groups, autostart, model pull)
- Project renamed to `flowkey` in `pyproject.toml` (package name `fastflowprompt` kept for backward compat)
- Updated classifiers for Linux (POSIX, X11, Wayland)

### Removed

- All Windows-specific modules: AHK scripts, Inno Setup installer, PowerShell helpers
- WinAPI parent-watch (`ctypes.windll`, `kernel32`, `WaitForSingleObject`)
- Windows Registry autostart (`winreg`)
- AMD NPU PowerShell detection
- `.exe` references everywhere
- Update ZIP extraction validates paths before unpacking.

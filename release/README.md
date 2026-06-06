# Flowkey

A Windows desktop tool that adds local-LLM hotkeys (grammar fix, prompt rewrite, summarize, explain code, tone shift, chat popup, ask-in-chat, note capture) on top of [FastFlowLM](https://fastflowlm.com).

**Everything runs on the user's machine.** No cloud calls, no telemetry, no data leaves the box.

> **Hardware requirement:** the FLM backend uses an **AMD Ryzen AI NPU** for inference (e.g. Lenovo ThinkPad T14s Gen 5 / Ryzen AI 350). This tool is opt-in for people on AMD AI hardware.

Version history and per-release changes live in **[`CHANGELOG.md`](./CHANGELOG.md)**. This README always reflects the current code; it is not a release log.

---

## Hotkeys

| Hotkey | Action |
|---|---|
| `Ctrl+Shift+G` | Grammar fix — replaces selection in place |
| `Ctrl+Shift+G` with `prompt:` prefix | Rewrite rough text as a Claude-ready prompt (XML sections, testable constraints) |
| `Ctrl+Shift+G` with `summarize:` prefix | 3-bullet summary, replaces selection |
| `Ctrl+Shift+G` with `explain:` prefix | Plain-English explanation of code / regex / SQL |
| `Ctrl+Shift+G` with `tone:` prefix | Rewrite in active tone preset (formal / casual / friendly — cycle from tray) |
| `Ctrl+Shift+T` | Open multi-tab chat window |
| `Ctrl+Shift+A` | **Ask in Chat** — sends selection to chat as quoted context (works on read-only text); shows Summarize / Explain / Improve / Ask… picker |
| `Ctrl+Alt+N` | Capture note — LLM-categorizes selection or URL → Markdown + YAML in vault |

All four hotkeys are **editable** from the dashboard's Config tab; valid changes apply live with no restart.

**Hotkey format:** modifier symbols then **exactly one** key — `^` Ctrl, `+` Shift, `!` Alt, `#` Win. So `Ctrl+Shift+G` = `^+g`, `Ctrl+Alt+N` = `^!n`, `Ctrl+Shift+1` = `^+1`. Note `+` means *Shift*, not a separator — `^+a+1` is invalid (two keys) and the Config tab rejects it.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  AutoHotkey v2 front-end  (grammarFix.ahk)                  │
│    hotkeys · tray menu · dashboard · Settings GUI           │
└──────────────┬──────────────────────────────────────────────┘
               │  HTTP loopback (127.0.0.1:52650, header-gated)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  Python daemon  (ffp_daemon.py)                             │
│    single-instance · parent-PID watch                       │
│    dispatches to grammar_fix · notes · chat backend         │
└──────────────┬──────────────────────────────────────────────┘
               │  HTTP loopback (127.0.0.1:52625)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  FastFlowLM server  (flm serve)  — local model inference    │
└─────────────────────────────────────────────────────────────┘
```

- **Stack:** AutoHotkey v2 + Python 3.11+ (stdlib only; `trafilatura` is an optional extra for cleaner URL extraction).
- **IPC:** Loopback HTTP only. Daemon `127.0.0.1:52650`, chat single-instance `127.0.0.1:52640`, FLM `127.0.0.1:52625`.
- **Packaging:** Standard Python wheel (`pip install .`) with console-script entry points (`ffp-daemon`, `ffp-grammar-fix`, `ffp-chat`, `ffp-first-run`, `ffp-install`).
- **Process model:** Daemon runs as the user (no admin), exits automatically when the parent AHK process dies (WinAPI `WaitForSingleObject`).

---

## Security & Data Handling

- **Nothing leaves the machine.** All LLM calls are loopback HTTP to FLM.
- **No telemetry.** No analytics, no error reporting, no auto-uploads.
- **History storage off by default.** `history_store_text=false` — only metadata (timestamps, token counts) is logged.
- **Server logs off by default.** `server.log_to_file=false`.
- **Vault location** is `%USERPROFILE%\Documents\FastFlowPrompt Notes\` — outside the app folder so it works cleanly with OneDrive / Obsidian / git.
- **URL fetching** uses stdlib `urllib` against user-pasted URLs only — no background crawling.
- **Subprocess hygiene:** every Python `subprocess.run` / `Popen` passes `CREATE_NO_WINDOW` and uses argv lists (no `shell=True`).

---

## Prerequisites

- Windows 10/11 with an AMD Ryzen AI NPU
- Python 3.11+
- AutoHotkey v2+
- FastFlowLM (`flm` on PATH)
- Recommended model: `qwen3.5:4b`

Official downloads: [Python](https://www.python.org/downloads/windows/) · [AutoHotkey](https://www.autohotkey.com/) · [FastFlowLM](https://fastflowlm.com/) · [AMD drivers](https://www.amd.com/en/support)

---

## Install

### Option A — GitHub release installer (recommended for end users)

1. Download `Flowkey-Setup-1.5.0.exe` from the GitHub Releases page, or build it locally — see [`installer/README.md`](installer/README.md).
2. Double-click. Accept the SmartScreen prompt (`More info → Run anyway`) — the installer is self-signed; to silence the warning permanently, [import the `.cer`](installer/README.md#end-user-smartscreen-note).
3. Accept the admin prompt. The installer drops the app into `C:\Program Files\FastFlowPrompt\`, chain-installs FastFlowLM if missing, and offers to register a per-machine login autostart.
4. When the first-run wizard opens: verify NPU detection, accept the license, pick a model (and let the wizard pull it from HuggingFace), review the hotkeys, run the warmup test.

Done — hotkeys are live globally for every user on the machine.

### Option B — One-click install from source (no build, no signing)

The lightest path: no `.exe` to compile, no `iscc.exe`, no code-signing cert,
no SmartScreen prompt. Best for validating on a fresh machine quickly.

1. Clone or download the repository, then keep the `release\` folder somewhere **writable** (Downloads or Desktop — *not* Program Files).
2. Double-click **`INSTALL.cmd`** and accept the single FastFlowLM UAC prompt.

`INSTALL.cmd` runs `installer\install.ps1`, which detects/installs Python 3.11+
(via winget), creates a private venv at `scripts\.venv` (the app auto-detects it —
no env var needed), stages AutoHotkey v2, installs FastFlowLM, registers a
per-user login autostart, then launches the app. The first-run wizard opens
automatically (NPU check → license → model pull → hotkeys → warmup). Re-runnable.

Remove it later with:

```powershell
.\installer\install.ps1 -Uninstall
```

### Option C — Python install (developers)

From the repository root:

```powershell
pip install .\release
ffp-install --phase full
# after reboot:
ffp-install --phase postreboot
```

### Option D — Editable / development

```powershell
pip install -e .\release
```

### Option E — Build the installer yourself

From the repository root, see [`installer/README.md`](installer/README.md). One-line build:

```powershell
.\release\installer\build.ps1 -BundleAhk -BundleFlm -Sign
```

For the full GitHub publishing checklist, see [`../docs/GITHUB_DEPLOYMENT.md`](../docs/GITHUB_DEPLOYMENT.md).

---

## Launch & Use

1. Start `scripts\grammarFix.ahk` (first launch triggers the setup wizard).
2. Select text in any app and press a hotkey (see table above).
3. Right-click the tray icon for the menu.

### Tray menu

- **Mode** — radio submenu: `🟡 Balanced` / `🔴 Max`
- **History** — radio submenu: `👁 Visible` / `🙈 Redacted`
- **Tone** — radio submenu: `🎩 Formal` / `👕 Casual` / `🤝 Friendly`
- **Open Chat** (`Ctrl+Shift+T`)
- **Dashboard**
- **Server ▶** — Warmup, Stop, Restart, Switch model, Pull model, Performance mode, Log to file
- **Settings…**, **Doctor**, **Check for updates**, **Start with Windows**, **About**, **Quit**

---

## Dashboard

Right-click tray → **Dashboard**. Six tabs:

| Tab | Content |
|---|---|
| **Overview** | Live-status snapshot: daemon health, FLM URL, model, performance mode, history mode, tone preset, vault dir, app version, live hotkey bindings |
| **Telemetry** | Tiled sections: counters · time-of-day heatmap · token & latency aggregate · latency sparkline (last 50) |
| **History** | Last 50 entries of `grammar_fix_history.jsonl` |
| **Notes** | Vault dir, categories, fetch timeout, max chars, generation toggles |
| **Config** | **Hotkeys** (editable, live re-register) · endpoint · installed/installable models · performance · history · routing · tone |
| **Benchmark** | Run `flm bench` on an installed model; poll progress and view saved run history |

Footer: **Refresh** (Enter), **Open History File**, **Open Config**, **Close**.

---

## Chat Window

`Ctrl+Shift+T` opens a multi-tab modal chat.

- **+ New chat** / `Ctrl+T` — new tab
- **× Close tab** / `Ctrl+W` — close current tab
- `Ctrl+Tab` / `Ctrl+Shift+Tab` — cycle tabs
- **History…** — reopen any saved thread
- `Enter` send, `Shift+Enter` newline, `Esc` hide, `Ctrl+Q` quit

Threads auto-persist to `data/chat_threads.jsonl` (atomic rewrite; latest snapshot per thread). A sliding context window (`chat.context_window_turns=12`) keeps replies fast on long threads.

When triggered via `Ctrl+Shift+A`, chat opens a fresh tab with the selection as a quoted block, plus a picker bar above the input: **Summarize · Explain · Improve · Ask…**

---

## Notes Capture

`Ctrl+Alt+N` on selected text **or** a selected URL:

1. Writes an inbox stub to the vault immediately (Markdown + YAML frontmatter).
2. In the background: optionally fetches the URL (stdlib `urllib`, optional `trafilatura`), asks the LLM to categorize + title + summarize, then rewrites the note into the chosen category folder.
3. Low-confidence categorizations stay in `inbox/` (configurable).

Vault layout under `%USERPROFILE%\Documents\FastFlowPrompt Notes\`:

```
inbox/
work/technical/
work/managerial/
work/career/
research/
personal/
ideas/
```

Plain Markdown + YAML frontmatter — Obsidian / OneDrive / git compatible out of the box.

---

## Release Layout

```
release/
├── README.md                ← this file
├── CHANGELOG.md             ← per-version history
├── pyproject.toml           ← wheel + entry points
├── scripts/                 ← source only
│   ├── grammarFix.ahk
│   ├── grammar_fix.py
│   ├── ffp_daemon.py
│   ├── ffp_config.py
│   ├── ffp_flm_server.py
│   ├── ffp_llm_client.py
│   ├── ffp_telemetry.py
│   ├── ffp_updater.py
│   ├── chat_popup.py
│   ├── notes.py
│   ├── first_run.py
│   ├── install.py
│   ├── ffp_benchmark.py
│   ├── ffp_pull.py
│   ├── loopback_http.py
│   ├── paths.py             ← single source of truth for file locations
│   ├── subprocess_util.py
│   ├── lib/
│   │   ├── classify.ahk
│   │   ├── daemon_client.ahk
│   │   ├── hotkeys.ahk
│   │   ├── json.ahk
│   │   └── paths.ahk
│   ├── ui/
│   │   ├── dashboard.ahk
│   │   ├── dashboard_handlers.ahk
│   │   ├── notifications.ahk
│   │   └── tray.ahk
│   └── _version.py
├── config/                  ← user-editable JSON
│   ├── grammar_hotkey.config.example.json
│   └── grammar_hotkey.config.json     (created on first run)
├── data/                    ← runtime data (counters, history, threads, pid, markers)
├── logs/                    ← daemon.log, flm_server.log
├── tests/                   ← pytest suite (config, telemetry, paths, daemon, LLM routing)
└── setup/                   ← install scripts
    ├── install_release.cmd
    ├── install_release.ps1
    ├── install_release.sh
    └── bootstrap_release.sh
```

File locations are all resolved through `scripts/paths.py`. Move a folder or override `FFP_RELEASE_ROOT` and the rest of the code follows.

### Module Map

- `grammar_fix.py` stays the stable facade used by the daemon and CLI entry points.
- `ffp_config.py` owns default config shape, load/save, and deep merge behavior.
- `ffp_flm_server.py` owns FLM reachability, PID tracking, and `flm list` helpers.
- `ffp_llm_client.py` owns routing, chunking, prompt shaping, and dictionary protection.
- `ffp_telemetry.py` owns history writes plus dashboard/stat aggregation.
- `ffp_pull.py` owns async `flm pull` jobs (`pull_start` / `pull_status`).
- `ffp_benchmark.py` owns async `flm bench` runs (`bench_start` / `bench_status` / `bench_history`).
- `ffp_updater.py` owns update feed checks and package swap logic.
- `ffp_actions.py` centralizes action constants shared by daemon/client fallback paths.
- `ffp_notify.py` centralizes desktop notification helpers.
- `ffp_tools.py` contains the experimental note-search tool schema and dispatcher.
- `loopback_http.py` centralizes JSON GET/POST for local HTTP clients.
- `subprocess_util.py` centralizes hidden-window subprocess behavior on Windows.
- `grammarFix.ahk` remains the single entry script while shared UI/runtime logic lives under `scripts/lib/` and `scripts/ui/`.

---

## Uninstall

```powershell
pip uninstall fastflowprompt
```

Then delete (optional):

- `release/config/grammar_hotkey.config.json` — your edited config
- `release/data/` — counters, history, threads, markers
- `release/logs/` — log files
- `%USERPROFILE%\Documents\FastFlowPrompt Notes\` — your captured notes vault

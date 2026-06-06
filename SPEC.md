# SPEC.md — Flowkey v1.5.0 (dashboard tooling milestone)

## §G  goals

- G1: non-dev double-clicks `.exe` → app live → ⊥ pip, ⊥ AHK install, ⊥ FLM install
- G2: per-machine install, multi-user safe → ∀ Windows user own config/data/logs
- G3: hotkeys live on login → ⊥ manual start
- G4: uninstall clean → ⊥ orphan files, ⊥ orphan registry, user config opt-keep
- G5: self-signed → reproducible build → ⊥ external paid cert blocker
- G6: dev mode (FFP_RELEASE_ROOT) + pip mode preserved alongside production

## §C  constraints

- C1: target Windows 10/11 x64 only
- C2: AMD Ryzen AI NPU required at runtime → FLM enforces
- C3: Python 3.13 frozen via PyInstaller → ⊥ shipped Python install
- C4: AHK v2.x portable, bundled → ⊥ system AHK assumed
- C5: FLM chained via vendor official installer (Inno Setup 6.5.2, EV-signed FastFlowLM Inc.)
- C6: final installer ≤ 80 MB (FLM model ⊥ bundled, FLM downloads on first use)
- C7: installer signed w/ self-cert → SmartScreen warns first time → user dismisses OR imports `.cer`
- C8: stdlib-only Python deps (per pyproject.toml) → ⊥ wheel deps to bundle

## §I  interfaces

### §I.paths  paths.py (v1.4.0)
```
mode: dev | production | user-local            (auto)
env: FFP_RELEASE_ROOT ?                        (force dev)
APP_DIR     → read-only resources               (Program Files in prod)
USER_ROOT   → writable state                    (%LOCALAPPDATA% in prod)
CONFIG_DIR  → USER_ROOT/config
DATA_DIR    → USER_ROOT/data
LOGS_DIR    → USER_ROOT/logs
SETUP_DIR   → APP_DIR/setup
CONFIG_SEED_FILE → APP_DIR/setup/defaults/grammar_hotkey.config.json
fn: seed_config_if_missing() → bool             (first-run copy)
fn: migrate_legacy_layout() → list[str]
RELEASE_ROOT = APP_DIR                          (back-compat alias)
```

### §I.installer  Inno Setup script (installer.iss)
```
out: Flowkey-Setup-1.4.0.exe
DefaultDirName: {commonpf}\FastFlowPrompt       (Program Files, per-machine)
PrivilegesRequired: admin
Compression: lzma2/max
ArchitecturesAllowed: x64
ArchitecturesInstallIn64BitMode: x64
```

### §I.install-src  run-from-source installer (install.ps1 + INSTALL.cmd)
```
entry: INSTALL.cmd (dbl-click, no admin) → installer/install.ps1
why: ⊥ PyInstaller, ⊥ Inno (iscc), ⊥ sign-cert, ⊥ SmartScreen → fast validate on fresh box
mode: paths.INSTALL_MODE == "dev" (runs in unzipped tree)
steps: py3.11+ (winget --scope user) → venv scripts/.venv → AHK→ahk/ → FLM silent → HKCU Run → launch grammarFix.ahk
venv: scripts/.venv → AHK ResolvePythonwPath auto-detects pythonw → ⊥ GRAMMARFIX_PYTHONW env
deps: ⊥ pip install (stdlib-only, daemon/wizard/chat run by file path)
flm: ⊥ present → flm-setup.exe silent (1 UAC via -Verb RunAs) ; present → skip
launch-order: grammarFix.ahk owns it → EnsureDaemonRunning → MaybeRunFirstRunWizard (daemon up before warmup)
flags: -NoAutostart -NoLaunch -SkipFlm -Uninstall
uninstall: kill AutoHotkey64 (daemon self-exits via --parent-pid) → del HKCU Run val → del venv ; user-data kept
```

### §I.flm-chain  FLM nested install
```
src: vendor/flm-setup.exe                       (curl'd at build time)
sig: EV cert FastFlowLM Inc., SSL.com EV CA
type: Inno Setup 6.5.2 → 17.7 MB installer → 168 MB on disk
silent: /VERYSILENT /SUPPRESSMSGBOXES /NOCANCEL /NORESTART /SP- /NOICONS \
        /CLOSEAPPLICATIONS /FORCECLOSEAPPLICATIONS /LANG=english /LOG=...
skip-if-present: RegQueryStringValue HKLM32 \
                 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\flm version *' \
                 OR FileExists '{commonpf}\FastFlowLM\flm.exe'
uninstall-string: unins000.exe /SILENT (chained from our uninstaller)
models: not bundled → wizard runs `flm pull <model>` post-install
```

### §I.pyinstaller  PyInstaller spec
```
target: onedir (not onefile → faster startup, antivirus-friendly)
entry: scripts/ffp_daemon.py (main exe)
extras: grammar_fix, chat_popup, first_run, notes, install (console_scripts)
hidden-imports: ffp_config, ffp_flm_server, ffp_llm_client, ffp_telemetry,
                ffp_updater, loopback_http, paths, subprocess_util, _version
version-info: from _version.__version__
icon: setup/logo.ico
console: False (windowed, daemon ⊥ console flash)
```

### §I.ahk  AHK runtime
```
vendor/ahk/AutoHotkey64.exe                     (portable v2.x)
launched-by: HKLM\...\Run autostart entry → AHK64.exe grammarFix.ahk
working-dir: APP_DIR
```

### §I.wizard  first-run wizard (extends first_run.py)
```
pages:
  1. welcome + AMD NPU hardware check
  2. license accept
  3. FLM model picker → pull progress (HF download)
  4. hotkey preview + rebind
  5. warmup test action
  6. done + open dashboard
marker: USER_ROOT/data/.first_run_done
fallback: if user skips → dashboard shows "first run incomplete" banner
```

### §I.autostart  login hook
```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run
  Flowkey → "{app}\ahk\AutoHotkey64.exe" "{app}\scripts\grammarFix.ahk"
scope: per-machine (HKLM) → every user gets it
opt-out: dashboard toggle → flips reg entry
```

### §I.signing  self-sign chain
```
cert: New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Flowkey Dev"
store: Cert:\CurrentUser\My → export .pfx (password in CI secret)
sign: signtool sign /f cert.pfx /p $env:CERT_PW /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 \
      Flowkey-Setup-1.4.0.exe
user-trust: ship .cer alongside → README docs how to import to Trusted Publishers
```

### §I.ci  GitHub Actions
```
trigger: tag push v*
runner: windows-latest
steps:
  - python -m build --wheel (sanity)
  - pyinstaller pyinstaller.spec
  - curl flm-setup.exe → vendor/
  - iscc installer.iss → out/Flowkey-Setup-X.Y.Z.exe
  - signtool sign (cert from secrets.CODE_CERT_PFX_B64)
  - gh release upload
```

## §V  invariants

- V1: ∀ writable file path → under USER_ROOT (never APP_DIR)
- V2: ∀ read of seed/default → APP_DIR (never USER_ROOT)
- V3: production mode → APP_DIR is read-only → ⊥ write attempts to it
- V4: paths.INSTALL_MODE ∈ {"dev", "production", "user-local"} → ⊥ other strings
- V5: FFP_RELEASE_ROOT set → mode == "dev" → single-tree layout
- V6: SCRIPTS_DIR under Program Files → mode == "production" → split layout
- V7: ⊥ FFP_RELEASE_ROOT & ⊥ Program Files & ⊥ dev-tree-detected → mode == "user-local"
- V8: RELEASE_ROOT alias == APP_DIR → ∀ legacy callers still resolve
- V9: ensure_dirs() creates only CONFIG_DIR, DATA_DIR, LOGS_DIR (not SETUP_DIR — read-only)
- V10: seed_config_if_missing() idempotent → ⊥ overwrite existing CONFIG_FILE
- V11: legacy migrate ⊥ raise on read-only failure → log & continue
- V12: installer DefaultDirName == `{commonpf}\FastFlowPrompt` ! exact
- V13: PrivilegesRequired == admin → installer prompts UAC on launch
- V14: FLM chain Check fn → skip if FLM already present → ⊥ reinstall stomp
- V15: FLM chain uses `waituntilterminated` → our installer ⊥ races FLM
- V16: uninstaller chains FLM `unins000.exe /SILENT` only if WE installed it (track via {app}\.flm_installed_by_us marker)
- V17: HKLM Run entry deleted on uninstall → ⊥ orphan autostart
- V18: PyInstaller onedir (not onefile) → ⊥ first-run extract delay, ⊥ antivirus false positive
- V19: signtool step ! present in CI → unsigned build ⊥ released
- V20: installer file < 80 MB (G6)
- V21: dev mode + pip mode behavior preserved bit-for-bit pre-v1.4.0 (G6 enforces)
- V22: ∀ daemon log path → LOGS_DIR (per-user, writable) → ⊥ Program Files write attempt
- V23: ∀ AHK wrapper fn signature ⊇ corresponding `*_Impl` arity → ⊥ "Too many parameters" at call site → add `body := "{}"` default when `_Impl` accepts body
- V24: run-from-source venv ! @ `scripts/.venv` → AHK `ResolvePythonwPath_Impl` auto-detect → ⊥ env var; install.ps1 stages AHK @ `APP_DIR/ahk/AutoHotkey64.exe` & HKCU Run cmd ≡ `_autostart_command_line()` → dashboard toggle state consistent
- V25: install.ps1 ⊥ `New-Item -Force` on HKCU Run key (wipes sibling values) → `Set-ItemProperty` only; uninstall claims "removed" only if value ∃
- V26: ∀ `.ps1`/`.cmd` source → ASCII-only (⊥ em-dash, ⊥ box-draw) → PS 5.1 reads UTF-8-no-BOM as CP1252 → byte-mangle → parse failure
- V27: ∀ flm model-list query → `flm list --json` → filter client-side by per-model `installed` bool (authoritative) → ⊥ parse `--quiet`/decorated text ("Models:" header, "  - " bullets, emoji icons); force UTF-8 decode
- V28: ∀ AHK→daemon JSON string → EscapeJson escapes ∀ char < U+0020 (`\t`,`\r`,`\b`,`\f` named; rest `\uXXXX`) → ⊥ raw C0 byte in body (was: only `\`,`"`,`\n` → raw TAB in selection → invalid JSON → daemon 400)
- V29: daemon body parse = `json.loads(strict=False)` → tolerate raw C0 controls → ⊥ 400 on under-escaped client; backstop, ⊥ replace V28
- V30: Config hotkey save → validate ∀ binding via `Hotkey()` parse BEFORE persist → ⊥ persist unbindable key → HkStatus ≡ actual bind result (⊥ "✅ saved" while AHK rejects → silent revert to default)
- V31: reset-to-defaults hotkey vals ≡ startup defaults → capture_note ≡ `^!n` (⊥ `^+n`: Shift+N ghosting)
- V32: ∀ `A_Clipboard` read (ProcessSelection,CaptureNote,AskWithSelection,ClipboardWatcher) → try/catch → ⊥ uncaught "Can't open clipboard for reading" dialog on clipboard lock → ∅ text fallback | skip watcher tick
- V33: autostart 1 source ≡ HKCU Run key `Flowkey`; tray & dashboard both → daemon `set_autostart`/`get_autostart_state`; ⊥ Startup-folder `.lnk` as live mechanism → ⊥ double-launch @ boot; on launch: legacy `.lnk` ∃ → migrate intent→Run key → del `.lnk`
- V34: FLM version check: daemon `flm_update_check` cmp `flm version --json` vs GitHub `releases/latest` (tag `v` strip, `version_tuple`); cache_only ⇒ ⊥ network (instant dashboard open) | force ⇒ live; cache TTL 24h @ `data/flm_update_cache.json`; ⊥ auto-download → "Download update…" opens release page; net fail → has_update=⊥ + `error` (⊥ raise)
- V35: REMOVED v1.5.0 (per-model stats + Top-10 slowest dropped; see T35). `compute_dashboard_data` → {latencies_recent, hour_buckets} only (⊥ slowest); ⊥ daemon `model_stats`; Telemetry tab = Counters, Time-of-day, Token&latency stats, Latency sparkline
- V37: note_search tool: `notes.search_notes(query,limit)` rank vault `*.md` (title 5x > body) → {title,category,snippet,score}; daemon `note_search`; `ffp_tools.py` = OpenAI tool schema `TOOLS` + `run_tool_call` dispatch + `chat_with_tools` loop (⊥ `tool_choice` → FLM 500); B15: FLM 0.9.43 500s on ∀ real gemma tool call (in-band {"error",code:500} "type must be string, but is object"; gemma emits `<tool_code>…</tool_code>` text FLM ⊥ parses) → `chat_with_tools` graceful fallback (tool-free answer + `tool_error`); working path = `chat_with_notes_context` (client-side note_search → inject top-N as context → answer cites titles, ⊥ model tool-calling)
- V36: benchmark: daemon `bench_start`(args.model) → bg thread, ≤1 concurrent (2nd ⇒ ok=⊥); stop serve → `flm bench <model>` cwd `data/benchmarks/run_<slug>_<ts>/` (timeout 5400s) → restart serve (finally); CSV = any `*.csv` in workdir, parse tolerant (fuzzy header context|ttft|prefill|decode, raw row kept) → persist `data/benchmarks/<slug>_<ts>.json`; `bench_status`→{state: idle|running|done|error,message,error}; `bench_history`→runs[] (peak prefill/decode tps); Benchmark tab: installed-model dropdown + Run (confirm) + poll 4s while running + history table; CSV headers confirmed (real run): `context_length_k,ttft_avg_s,…,prefill_avg_toks_per_s,…,decoding_avg_toks_per_s,…`; file `bench_<model>_<date>_<hw>.csv`; fuzzy parser picks the `*_avg_*` col per metric; raw row preserved
- V38: first-run wizard gate: AHK `MaybeRunFirstRunWizard` launches `first_run.py --check` (⊥ guess marker path); `first_run.py` authoritative → skip iff `paths.MARKER_FIRST_RUN_DONE` (= `DATA_DIR/.first_run_done`) exists; marker written on Finish AND on window-close (WM_DELETE_WINDOW) → ⊥ nag every launch; re-openable via tray "Re-run wizard"
- V40: dashboard tables use AHK `Format()` right-justify `{:N}` (⊥ Python `{:>N}` → literal) & left `{:-N}`; ∀ monospace table cols (RenderHours, RenderBenchHistory) render values ≠ literal placeholders
- V41: daemon POST `/action/*` ! header `X-FFP-API` == `API_VERSION` else 403 (CSRF/cross-origin defense; browser ⊥ set custom header cross-origin w/o preflight daemon ⊥ grants); GET `/healthz` ⊥ gated; body > 8MB ⇒ 413; daemon bind 127.0.0.1 only; ⊥ shell=True ∀ subprocess; updater ! sha256 match
- V42: app name = "Flowkey" (display ∀ user-facing: titles, toasts, wizard, docs); internal ids KEEP "FastFlowPrompt"/"fastflowprompt" (data dir `%LOCALAPPDATA%\FastFlowPrompt`, vault `Documents\FastFlowPrompt Notes`, HKCU Run value `FastFlowPrompt`, pkg `fastflowprompt`, bundle dir, `ffp_*` prefix) → ⊥ orphan existing installs; FastFlowLM/`flm` (engine) ⊥ renamed; dashboard+tray icon `scripts/assets/flowkey.ico` (placeholder, FileExist-guarded)
- V39: model pull async: daemon `pull_start`(args.model) → bg thread `flm pull` (≤1 concurrent), parse last `\d+%` from streamed stdout → `pull_status`{state,model,percent,message,error}; dashboard `OnServerPullModel`→start+`PullPoll` 1s → ServerPullStatus "% " (⊥ block GUI); done → RefreshDashboard (new model in installed list)

## §T  tasks

```
id |status|task                                                          |cites
T10|.     |PyInstaller spec: freeze daemon + scripts                     |I.pyinstaller,V18
T11|.     |Bundle AHK v2 portable in vendor/ahk/                         |I.ahk,C4
T12|.     |Embed FLM installer via build-time curl                       |I.flm-chain,C5,C6
T13|.     |Inno Setup installer.iss (per-machine, admin, lzma2/max)      |I.installer,V12,V13
T14|.     |First-run wizard GUI (6 pages)                                |I.wizard
T15|.     |Self-signing pipeline (cert + signtool)                       |I.signing,V19
T16|.     |Uninstaller logic (Run key, FLM chain, user-config opt-keep)  |V16,V17,G4
T17|x     |Per-machine paths refactor (3-mode auto-detect)               |I.paths,V1-V11
T18|.     |GitHub Actions build pipeline                                 |I.ci,V19
T19|.     |Smoke test installer on clean VM                              |G1,G2,G3,G4
T20|.     |Update README + CHANGELOG for v1.4.0                          |-
T21|.     |Seed defaults bundle: setup/defaults/ ships in installer      |I.paths,V2,V10
T22|.     |AMD NPU hardware check in wizard page 1                       |C2,I.wizard
T23|.     |Dashboard toggle for autostart Run key                        |I.autostart
T24|x     |Run-from-source installer (install.ps1 + INSTALL.cmd, ⊥ exe)  |I.install-src,V24-V26,G6
T25|x     |note/Ask TAB→400 fix; hotkey save validate-before-persist; reset⇒^!n |B10-B12,V28-V31
T26|x     |guard ∀ `A_Clipboard` read (watcher,G,note,Ask) vs clipboard-lock throw |B13,V32
T27|x     |unify autostart→Run key (tray delegates to daemon set/get_autostart); migrate+del legacy `.lnk` @ startup; rm stale duplicate `.lnk` |B14,V33
T28|x     |Feature: FLM version check (daemon `flm_update_check` + Config-tab "FastFlowLM runtime" UI: status + Check + Download-opens-release) |V34
T29|x     |Feature: per-model timing (`compute_model_stats` + daemon `model_stats` + Telemetry-tab table & window selector) → REMOVED v1.5.0 (T35) |V35
T30|x     |Feature: benchmark tab (`ffp_benchmark` module + daemon `bench_start`/`bench_status`/`bench_history` + Benchmark tab w/ 4s poll) |V36
T31|x     |Prototype: gemma note_search (`notes.search_notes`+daemon `note_search`+`ffp_tools.py`); model tool-calling blocked by FLM 0.9.43 500 (B15) → working `chat_with_notes_context` retrieval-injection |V37,B15
T32|x     |Fix first-run wizard re-running every launch (AHK `--check` + ⊥ wrong marker path; mark done on window-close) |B16,V38
T33|x     |Async model pull w/ progress % (`ffp_pull` + daemon `pull_start`/`pull_status` + dashboard `PullPoll` 1s, ⊥ GUI freeze) |V39
T34|x     |Fix dashboard table render: AHK `Format()` `{:>N}`→`{:N}` (hours,benchmark) |B17,V40
T35|x     |Remove Top-10 slowest + per-model telemetry (UI+handlers+daemon `model_stats`+`compute_model_stats`+`slowest`); enlarge remaining Telemetry tiles |V35
T36|x     |Security: daemon POST ! `X-FFP-API` header (403) + 8MB body cap (413); CSRF/local-DoS hardening |V41
T37|x     |Rename app→Flowkey (display+docs only; internal ids kept); dashboard+tray icon `assets/flowkey.ico` |V42
T38|x     |Dashboard tiles: Config + Telemetry + Notes + Benchmark → `GroupBox` grid; `MinSize840x780`/open `920×860` |V42
```

## §B  bugs

```
id |date      |cause                                              |fix-cite
B1 |2026-05-26|AHK Format() ⊥ unescape `{{` on some builds → daemon 400 |V (see release notes 1.3.0)
B2 |2026-05-26|WinHttp UTF-16 → ANSI without charset hint → daemon 400  |V (charset=utf-8 header)
B3 |2026-05-26|Hotkey() callback ! 1-param sig → AHK error             |V (variadic lambda wrapper)
B4 |2026-05-26|Toast pipeline gated by Focus Assist → ⊥ visible        |V (TrayTip primary)
B5 |2026-05-26|prompt: mode truncated → max_tokens too low             |V (700/900/1200 caps)
B6 |2026-05-26|config_snapshot ⊥ subprocess fallback → dashboard `?`   |V (build_config_snapshot shared helper)
B7 |2026-05-28|RunAction wrapper arity == 1, OnToggleAutostart passed body → "Too many parameters" |V23 (wrapper arity ⊇ _Impl arity)
B8 |2026-05-29|install.ps1 em-dash in string → PS5.1 CP1252 read of UTF-8-no-BOM → mangled quote byte → ParseFile brace/paren cascade |V26 (ASCII-only ps1/cmd)
B9 |2026-05-29|dashboard installed-models empty → flm_list parsed `flm list --filter installed --quiet` decorated text ("Models:" hdr, "- name" bullets, ⏬ emoji mojibake) as bare names |V27 (parse `--json` installed flag, UTF-8)
B10|2026-05-29|note/Ask selection w/ TAB → EscapeJson left raw 0x09 in JSON str → daemon json.loads(strict) → HTTP 400 json_parse_failed → action silent no-op |V28,V29
B11|2026-05-29|Config hotkey "^+a+1" invalid (+ = Shift, ⊥ separator) → persisted + UI "✅ saved" but Hotkey() reject → silent revert to default |V30
B12|2026-05-29|OnResetHotkeys set capture_note `^+n` ≠ real default `^!n` → reset regressed to ghosting-prone Shift+N |V31
B13|2026-06-01|`A_Clipboard` read → throw "Can't open clipboard for reading" on clipboard lock (clip mgr\|RDP\|app mid-copy) → uncaught → dialog; watcher most exposed (∀ clip change); G\|note\|Ask post-copy reads also bare |V32
B14|2026-06-03|2 autostart toggles: tray→Startup `.lnk`, dashboard(T23)→HKCU Run key → both active → double-launch @ boot + tray "off" ⊥ rm Run key (autostart persists); stale old-install `.lnk` → "Script file not found" @ boot |V33
B15|2026-06-03|FLM 0.9.43 (upstream): ∀ real gemma tool call → in-band {"error",code:500} "type must be string, but is object" (reproduced w/ minimal schema); gemma emits `<tool_code>fn(args)</tool_code>` as text, FLM ⊥ parses→tool_calls; `tool_choice` key also 500s. ⊥ client-fixable → fallback + retrieval-injection path |V37
B16|2026-06-03|first-run wizard ran every launch: AHK checked `A_ScriptDir\.first_run_done` (scripts\, wrong — real marker `DATA_DIR\.first_run_done`) & launched wizard ⊥ `--check` → Python gate never engaged; + marker written only on Finish, ⊥ on window-close (X) |V38
B17|2026-06-03|AHK `Format()` `{:>N}` (Python-style right-align) unsupported in v2 → emitted LITERAL "{:>N}" in dashboard tables (Telemetry slowest+hours, per-model, benchmark) → all rows looked identical/garbled. Fix: `{:N}`=right (default), `{:-N}`=left (verified headless: `{:>6}`→literal, `{:6}`→right, `{:-6}`→left) |V40
```

## notes

- §V invariants are the SDD signal — new bugs append to §B, then check if a §V row would catch recurrence; if yes, add it.
- caveman encoding applies to this file only. Code, error strings, commit messages stay normal English.
- v1.4.0 milestone closes when T10–T24 all `x`. Two delivery paths: §I.installer (signed .exe) + §I.install-src (run-from-source, ⊥ build) — either satisfies G1.

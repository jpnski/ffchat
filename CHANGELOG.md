# Changelog

All notable changes to the **Flowkey Linux port** are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/).

For the step-by-step port log, see [`TODO.md`](TODO.md).

[v0.0.2]
- Fixed Wayland hotkey handling and selection capture for global actions
- Added configurable terminal launching for the chat hotkey with common fallbacks
- Improved note capture and chat startup behavior when FLM is still warming up

[v0.0.1]
- Functional flowkey daemon, listener, process, and tui. Tray untested.
    - TUI features functional ChatWidget and Dashboard Widget
    - Dashboard has complete ConfigPane, remaining are TODO
- Using pyinstaller to package a onefile distribution
- Release workflow using Ubuntu noble to package all py deps successfully

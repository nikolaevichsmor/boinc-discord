### Multi-Project Discord Rich Presence for BOINC

Real-time Discord Rich Presence (RPC) integration for **BOINC** distributed computing projects. Automatically cycles active BOINC projects on your Discord status, displaying live workunit progress, elapsed computation time, total completed tasks count, animated project artwork, and direct project links.

---

### Highlights

- **Cyclic Multi-Project Rotation**: Automatically alternates between active BOINC projects every 18 seconds while updating progress live every 4.5 seconds.
- **Per-Project Identity & Artwork**: Displays project-specific activity titles, custom animated GIFs, descriptions, and project links.
- **Continuous Workunit Tracking**: Independently tracks the freshest workunit for each project all the way to 100% completion before moving to the next task.
- **Standalone System Tray Control**: Lightweight Win32 system tray icon with live status tooltip, instant manual project switching (`Next Project Now`), project pinning, and pause/resume controls.
- **Zero External Dependencies**: Direct communication with Discord desktop client via Windows Named Pipes (`\\.\pipe\discord-ipc-0..9`). Pure Python standard library (`pypresence` not required).

---

### Quick Start (Windows)

1. Download and extract **`boinc-discord.zip`** from the Assets below.
2. Run **`start_discord.bat`** *(run as administrator if BOINC is installed as a service)*.
3. A BOINC icon appears in your Windows system tray, and your Discord profile automatically cycles through your active BOINC projects.

---

**Requirements:** Windows, Python 3.8+ (standard library only), Discord desktop client, running BOINC tasks.

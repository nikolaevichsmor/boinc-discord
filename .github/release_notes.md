### Discord Rich Presence for BOINC ODLK Tasks

Real-time Discord Rich Presence (RPC) integration for BOINC **ODLK** computations (searching for diagonal Latin squares of order 10). Displays live task progress, elapsed time, total completed tasks, and direct project links on your Discord profile.

---

### Highlights

- **Zero External Dependencies**: Direct communication with Discord desktop client via Windows Named Pipes (`\\.\pipe\discord-ipc-0..9`). No `pypresence` or third-party pip packages required.
- **Animated Live Matrix & BOINC Badge**: Displays a live animated 10×10 Latin square permutation matrix (`large_image`) with a rotating BOINC corner badge (`small_image`).
- **Continuous Workunit Tracking**: Automatically targets the workunit with the lowest progress and tracks it through to 100% completion before switching to the next task.
- **Full Telemetry**: Displays percentage progress, formatted total completed Latin squares task count, elapsed computation timer, and interactive link buttons.
- **Native System Tray Synergy**: Automatically detects and coordinates with [odlk1-voxel](https://github.com/nikolaevichsmor/odlk1-voxel) (the 3D visualizer) via local IPC (`SO_EXCLUSIVEADDRUSE` + Win32 named mutex) to share a single unified Windows system tray icon with synchronized pause/resume and exit controls.
- **Zero Overhead**: Standard read queries via `boinccmd` and BOINC job logs; no process memory injection or high CPU usage.

---

### Quick Start (Windows)

1. Download and extract **`odlk1-discord.zip`** from the Assets below.
2. Run **`start_discord.bat`** *(run as administrator if BOINC is installed as a service)*.
3. An icon appears in your Windows system tray, and your Discord status automatically updates with your active ODLK workunit progress.

---

**Requirements:** Windows, Python 3.8+ (standard library only), Discord desktop client, running ODLK tasks in BOINC.

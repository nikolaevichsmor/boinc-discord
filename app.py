"""
ODLK1 Discord Rich Presence main application with Windows system tray synergy.
Runs silently in background with no console windows by default.
"""
import argparse
import ctypes
import os
import sys
import threading
import time

# Handle pythonw stdout/stderr redirection
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass

from discord_rpc import OdlkPresenceService
from tray import TrayIcon


def parse_args():
    parser = argparse.ArgumentParser(description="ODLK1 Discord Rich Presence")
    parser.add_argument("--client-id", type=str, default=None, help="Discord Application (Client) ID")
    parser.add_argument("--boinc-data", type=str, default=None, help="Path to BOINC data directory")
    parser.add_argument("--boinccmd", type=str, default=None, help="Path to boinccmd executable")
    parser.add_argument("--interval", type=float, default=4.5, help="Update interval in seconds (default: 4.5)")
    parser.add_argument("--no-tray", action="store_true", help="Run without system tray icon")
    parser.add_argument("--console", action="store_true", help="Do not hide console window")
    return parser.parse_args()


def main():
    args = parse_args()

    # Hide console window if launched with standard python without --console
    if sys.platform == "win32" and not args.console:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "docs", "icon.ico")

    # Prevent running duplicate instances of Discord RPC service
    mutex = None
    if sys.platform == "win32":
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ctypes.set_last_error(0)
        mutex = k32.CreateMutexW(None, True, "Local\\ODLK1_Discord_Service_Singleton")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            return

    service = OdlkPresenceService(
        client_id=args.client_id,
        boinc_data=args.boinc_data,
        boinccmd=args.boinccmd,
        update_interval=args.interval
    )
    service.start()

    def on_toggle_discord(is_paused):
        service.set_paused(is_paused)

    def is_discord_active():
        return service.ipc.connected

    def on_exit():
        service.stop()

    tray = None
    if not args.no_tray:
        tray = TrayIcon(
            title="ODLK1 Discord RPC",
            icon_path=icon_path,
            module_name="discord",
            on_open=None,
            on_toggle_discord=on_toggle_discord,
            on_exit=on_exit,
            is_discord_active_fn=is_discord_active
        )
        tray.start()

    try:
        if tray:
            while tray.running:
                time.sleep(0.5)
        else:
            while service.running:
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        on_exit()
        if tray:
            tray.stop()
        if mutex and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.ReleaseMutex(mutex)
                ctypes.windll.kernel32.CloseHandle(mutex)
            except Exception:
                pass


if __name__ == "__main__":
    main()

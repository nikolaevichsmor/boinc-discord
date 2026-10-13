"""
Zero-dependency Discord Rich Presence (RPC) client for ODLK1.
Communicates directly with the local Discord client via Windows Named Pipes (\\\\.\\pipe\\discord-ipc-0..9).
Reads active BOINC task telemetry and completed task counts with zero overhead.
"""
import ctypes
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import uuid

DEFAULT_CLIENT_ID = "1559236488305311916"
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "discord_config.json")


def load_config():
    defaults = {
        "client_id": DEFAULT_CLIENT_ID,
        "update_interval": 4.5,
        "boinc_data": None,
        "boinccmd": None,
        "large_image": "odlk1_logo_1024",
        "large_text": "ODLK1 Latin Squares"
    }
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update({k: v for k, v in data.items() if v is not None})
        except Exception:
            pass
    return defaults


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


if sys.platform == "win32":
    import msvcrt
    _k32 = ctypes.windll.kernel32
    _k32.PeekNamedPipe.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)
    ]
    _k32.PeekNamedPipe.restype = ctypes.c_int


class DiscordIPC:
    """Low-level Discord IPC client over named pipe with non-blocking reads and auto-reconnect."""
    OP_HANDSHAKE = 0
    OP_FRAME = 1
    OP_CLOSE = 2
    OP_PING = 3
    OP_PONG = 4

    def __init__(self, client_id=None):
        self.client_id = client_id or load_config().get("client_id", DEFAULT_CLIENT_ID)
        self.pipe = None
        self.connected = False
        self._lock = threading.Lock()

    def _read_exact(self, num_bytes, timeout=1.0):
        if not self.pipe:
            raise OSError("Pipe not open")
        if sys.platform == "win32":
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(self.pipe.fileno()))
            start = time.time()
            avail = ctypes.c_uint32(0)
            while time.time() - start < timeout:
                res = _k32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
                if not res:
                    raise OSError("Pipe broken or disconnected (e.g. Discord account switch)")
                if avail.value >= num_bytes:
                    return self.pipe.read(num_bytes)
                time.sleep(0.02)
            raise TimeoutError("Timeout waiting for response from Discord pipe")
        else:
            return self.pipe.read(num_bytes)

    def connect(self):
        acquired = self._lock.acquire(timeout=0.5)
        if not acquired:
            return False
        try:
            if self.connected and self.pipe:
                return True
            self.connected = False
            if self.pipe:
                try:
                    self.pipe.close()
                except Exception:
                    pass
                self.pipe = None

            k32 = ctypes.windll.kernel32 if sys.platform == "win32" else None
            for i in range(10):
                pipe_path = rf"\\.\pipe\discord-ipc-{i}"
                if k32 and not k32.WaitNamedPipeW(pipe_path, 50):
                    continue
                try:
                    self.pipe = open(pipe_path, "r+b", buffering=0)
                    payload = json.dumps({"v": 1, "client_id": self.client_id}).encode("utf-8")
                    self.pipe.write(struct.pack("<II", self.OP_HANDSHAKE, len(payload)) + payload)

                    hdr = self._read_exact(8, timeout=3.0)
                    op, length = struct.unpack("<II", hdr)
                    resp_data = self._read_exact(length, timeout=3.0).decode("utf-8", errors="ignore")
                    resp = json.loads(resp_data)
                    if op == self.OP_FRAME and resp.get("cmd") == "DISPATCH" and resp.get("evt") == "READY":
                        self.connected = True
                        return True
                    else:
                        self._disconnect_locked()
                        continue
                except Exception:
                    if self.pipe:
                        try:
                            self.pipe.close()
                        except Exception:
                            pass
                        self.pipe = None
            return False
        finally:
            self._lock.release()

    def send_activity(self, activity):
        acquired = self._lock.acquire(timeout=0.5)
        if not acquired:
            return False
        try:
            if not self.connected or not self.pipe:
                return False
            payload = {
                "cmd": "SET_ACTIVITY",
                "args": {
                    "pid": os.getpid(),
                    "activity": activity
                },
                "nonce": str(uuid.uuid4())
            }
            try:
                data = json.dumps(payload).encode("utf-8")
                self.pipe.write(struct.pack("<II", self.OP_FRAME, len(data)) + data)
                hdr = self._read_exact(8, timeout=2.0)
                op, length = struct.unpack("<II", hdr)
                resp_data = self._read_exact(length, timeout=2.0)
                if op == self.OP_CLOSE:
                    self._disconnect_locked()
                    return False
                return True
            except Exception:
                self._disconnect_locked()
                return False
        finally:
            self._lock.release()

    def clear_activity(self):
        acquired = self._lock.acquire(timeout=0.5)
        if not acquired:
            return False
        try:
            if not self.connected or not self.pipe:
                return False
            payload = {
                "cmd": "SET_ACTIVITY",
                "args": {
                    "pid": os.getpid(),
                    "activity": None
                },
                "nonce": str(uuid.uuid4())
            }
            try:
                data = json.dumps(payload).encode("utf-8")
                self.pipe.write(struct.pack("<II", self.OP_FRAME, len(data)) + data)
                hdr = self._read_exact(8, timeout=0.8)
                _, length = struct.unpack("<II", hdr)
                self._read_exact(length, timeout=0.8)
                return True
            except Exception:
                self._disconnect_locked()
                return False
        finally:
            self._lock.release()

    def _disconnect_locked(self):
        self.connected = False
        if self.pipe:
            try:
                self.pipe.close()
            except Exception:
                pass
            self.pipe = None

    def disconnect(self):
        acquired = self._lock.acquire(timeout=0.5)
        if not acquired:
            return
        try:
            self._disconnect_locked()
        finally:
            self._lock.release()


class OdlkPresenceService:
    """
    Background worker that monitors BOINC ODLK progress and syncs to Discord.
    Respects Discord rate limits (default updates every 4.5 seconds).
    """

    def __init__(self, client_id=None, boinc_data=None, boinccmd=None, update_interval=4.5):
        cfg = load_config()
        self.client_id = client_id or cfg.get("client_id", DEFAULT_CLIENT_ID)
        self.ipc = DiscordIPC(client_id=self.client_id)
        self.running = False
        self.paused = False
        self.thread = None
        self._stop_event = threading.Event()
        self.last_update = 0.0
        self.update_interval = update_interval or cfg.get("update_interval", 4.5)
        self.current_task_name = None
        self.task_start_time = None
        self.data_dir = boinc_data or cfg.get("boinc_data") or self._find_boinc_data()
        self.boinccmd = boinccmd or cfg.get("boinccmd") or self._find_boinccmd()
        self.job_log_path = self._find_job_log()
        self.large_image = cfg.get("large_image", "odlk1_logo_1024")
        self.large_text = cfg.get("large_text", "ODLK1 Latin Squares")

    def _find_boinc_data(self):
        for candidate in [r"C:\Other\data.BOINC", r"C:\ProgramData\BOINC", r"C:\Other\BOINC"]:
            if os.path.isdir(candidate):
                return candidate
        return None

    def _find_boinccmd(self):
        for candidate in [r"C:\Other\BOINC\boinccmd.exe", r"C:\Program Files\BOINC\boinccmd.exe"]:
            if os.path.isfile(candidate):
                return candidate
        return "boinccmd"

    def _find_job_log(self):
        if self.data_dir:
            p = os.path.join(self.data_dir, "job_log_boinc.multi-pool.info_latinsquares.txt")
            if os.path.isfile(p):
                return p
        return None

    def get_completed_tasks_count(self):
        if self.job_log_path and os.path.isfile(self.job_log_path):
            try:
                with open(self.job_log_path, "rb") as f:
                    return sum(buf.count(b"\n") for buf in iter(lambda: f.read(1024 * 1024), b""))
            except Exception:
                pass
        return 0

    def get_active_task_info(self):
        """Returns (task_name, fraction_done, elapsed) or None."""
        if not self.data_dir or not os.path.isfile(self.boinccmd):
            return None
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        try:
            out = subprocess.run([self.boinccmd, "--get_tasks"], cwd=self.data_dir,
                                 capture_output=True, text=True, timeout=5, creationflags=flags).stdout
        except Exception:
            return None

        # Parse tasks
        tasks = []
        cur = None
        for line in out.splitlines():
            if re.match(r"^\d+\) -+", line):
                cur = {}
                tasks.append(cur)
            elif cur is not None and ":" in line:
                k, v = line.split(":", 1)
                cur[k.strip()] = v.strip()

        # Find active ODLK executing tasks
        active = [t for t in tasks if "latinsquares" in (t.get("project URL") or "")
                  and t.get("active_task_state") == "EXECUTING"]
        if not active:
            return None

        # Check if the currently tracked task is still active and executing
        tracked = None
        if self.current_task_name:
            tracked = next((t for t in active if (t.get("WU name") or t.get("name")) == self.current_task_name), None)

        # If the currently tracked task completed (or not yet chosen),
        # pick the task with the LOWEST fraction done (freshest task) to track to completion
        if not tracked:
            min_frac = 2.0
            for t in active:
                try:
                    frac = float(t.get("fraction done", 0.0))
                    if frac < min_frac:
                        min_frac = frac
                        tracked = t
                except ValueError:
                    pass
            if tracked:
                self.current_task_name = tracked.get("WU name") or tracked.get("name")
                try:
                    el = float(tracked.get("elapsed task time", 0.0))
                except ValueError:
                    el = 0.0
                self.task_start_time = int(time.time() - el) if el > 0 else int(time.time())

        if tracked:
            try:
                frac = float(tracked.get("fraction done", 0.0))
            except ValueError:
                frac = 0.0
            try:
                elapsed = float(tracked.get("elapsed task time", 0.0))
            except ValueError:
                elapsed = 0.0
            name = tracked.get("WU name") or tracked.get("name") or "ODLK1"
            return name, frac, elapsed

        self.current_task_name = None
        return None

    def start(self):
        if self.running:
            return
        self.running = True
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self._stop_event.set()
        if self.ipc:
            self.ipc.clear_activity()
            self.ipc.disconnect()

    def set_paused(self, paused: bool):
        self.paused = paused
        if paused:
            if self.ipc:
                self.ipc.clear_activity()
        else:
            self.last_update = 0.0

    def _run_loop(self):
        while not self._stop_event.is_set():
            if self.paused:
                if self.ipc.connected:
                    self.ipc.clear_activity()
                time.sleep(0.5)
                continue

            now = time.time()
            # Respect Discord rate limit: update at most once every interval
            if now - self.last_update < self.update_interval:
                time.sleep(0.5)
                continue

            if not self.ipc.connected:
                if not self.ipc.connect():
                    # Retry in 5 seconds if Discord is closed or switching accounts
                    time.sleep(5.0)
                    continue

            task_info = self.get_active_task_info()
            if not task_info:
                # No active task, clear status
                self.ipc.clear_activity()
                self.last_update = now
                time.sleep(2.0)
                continue

            wu_name, frac, elapsed = task_info
            if wu_name != self.current_task_name:
                self.current_task_name = wu_name
                self.task_start_time = int(now - elapsed) if elapsed > 0 else int(now)

            pct = frac * 100.0
            total_completed = self.get_completed_tasks_count()
            completed_str = f"{total_completed:,}".replace(",", " ")

            activity = {
                "details": "Searching 10x10 Latin Squares",
                "state": f"{pct:.1f}% ({completed_str} tasks completed)",
                "timestamps": {
                    "start": self.task_start_time or int(now)
                },
                "buttons": [
                    {
                        "label": "What is this?",
                        "url": "https://boinc.multi-pool.info/latinsquares/"
                    },
                    {
                        "label": "GitHub",
                        "url": "https://github.com/nikolaevichsmor/odlk1-discord"
                    }
                ]
            }

            if self.large_image:
                activity["assets"] = {
                    "large_image": self.large_image,
                    "large_text": self.large_text
                }

            success = self.ipc.send_activity(activity)
            self.last_update = time.time()
            if not success:
                # Pipe broken or disconnected (e.g. account switch), retry sooner
                time.sleep(2.0)
            else:
                time.sleep(self.update_interval)

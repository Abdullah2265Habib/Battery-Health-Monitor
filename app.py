"""
app.py — Battery Notifier Daemon
Reads thresholds from thresholds.json (written by the Streamlit dashboard)
and sends desktop notifications when battery crosses those limits.
"""

import json
import time
import platform
import subprocess
from pathlib import Path

THRESHOLDS_FILE = Path(__file__).parent / "thresholds.json"
DEFAULT_UPPER = 85
DEFAULT_LOWER = 20
POLL_INTERVAL = 30  # seconds between checks

# ── helpers ──────────────────────────────────────────────────────────────────

def load_thresholds() -> tuple[int, int]:
    """Return (upper, lower) thresholds from JSON, or defaults."""
    try:
        data = json.loads(THRESHOLDS_FILE.read_text())
        return int(data.get("upper", DEFAULT_UPPER)), int(data.get("lower", DEFAULT_LOWER))
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return DEFAULT_UPPER, DEFAULT_LOWER


def get_battery() -> tuple[float | None, bool | None]:
    """
    Returns (percent, is_plugged_in).
    Uses psutil when available; falls back to platform-specific commands.
    """
    try:
        import psutil
        batt = psutil.sensors_battery()
        if batt is None:
            return None, None
        return batt.percent, batt.power_plugged
    except ImportError:
        pass

    system = platform.system()

    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["pmset", "-g", "batt"], text=True, stderr=subprocess.DEVNULL
            )
            # e.g. "Now drawing from 'AC Power'\n\t... 78%; charging;"
            import re
            pct_match = re.search(r"(\d+)%", out)
            plugged = "AC Power" in out or "charging" in out.lower()
            if pct_match:
                return float(pct_match.group(1)), plugged
        except Exception:
            pass

    elif system == "Linux":
        try:
            import glob
            for base in glob.glob("/sys/class/power_supply/BAT*"):
                cap_file = Path(base) / "capacity"
                status_file = Path(base) / "status"
                if cap_file.exists():
                    pct = float(cap_file.read_text().strip())
                    plugged = False
                    if status_file.exists():
                        status = status_file.read_text().strip().lower()
                        plugged = status in ("charging", "full")
                    return pct, plugged
        except Exception:
            pass

    elif system == "Windows":
        try:
            out = subprocess.check_output(
                ["WMIC", "Path", "Win32_Battery", "Get", "EstimatedChargeRemaining"],
                text=True, stderr=subprocess.DEVNULL
            )
            lines = [l.strip() for l in out.splitlines() if l.strip().isdigit()]
            if lines:
                return float(lines[0]), None
        except Exception:
            pass

    return None, None


def send_notification(title: str, message: str) -> None:
    """Send a desktop notification cross-platform."""
    system = platform.system()

    if system == "Darwin":
        script = f'display notification "{message}" with title "{title}" sound name "Glass"'
        subprocess.run(["osascript", "-e", script], check=False)

    elif system == "Linux":
        # Try notify-send (libnotify), fall back to zenity
        if subprocess.call(["which", "notify-send"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            subprocess.run(["notify-send", title, message], check=False)
        else:
            print(f"[NOTIFY] {title}: {message}")

    elif system == "Windows":
        try:
            from win10toast import ToastNotifier
            ToastNotifier().show_toast(title, message, duration=5, threaded=True)
        except ImportError:
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
            except Exception:
                print(f"[NOTIFY] {title}: {message}")

    else:
        print(f"[NOTIFY] {title}: {message}")


# ── state machine ─────────────────────────────────────────────────────────────

class BatteryMonitor:
    """Tracks last-notified state to avoid spamming the same notification."""

    def __init__(self):
        self.last_state: str | None = None  # "high" | "low" | "ok"

    def check(self):
        upper, lower = load_thresholds()
        percent, plugged = get_battery()

        if percent is None:
            print("[battery-notifier] Could not read battery. Is psutil installed?")
            return

        state_icon = "🔌" if plugged else "🔋"
        print(
            f"[battery-notifier] {percent:.0f}% {'(charging)' if plugged else '(on battery)'}  "
            f"| thresholds: ↑{upper}%  ↓{lower}%"
        )

        if percent >= upper and plugged:
            new_state = "high"
            if new_state != self.last_state:
                send_notification(
                    "🔋 Unplug Your Charger",
                    f"Battery is at {percent:.0f}% — above the {upper}% threshold. "
                    "You can safely unplug now.",
                )
                self.last_state = new_state

        elif percent <= lower and not plugged:
            new_state = "low"
            if new_state != self.last_state:
                send_notification(
                    "⚠️ Plug In Your Charger",
                    f"Battery is at {percent:.0f}% — below the {lower}% threshold. "
                    "Please plug in soon.",
                )
                self.last_state = new_state

        else:
            self.last_state = "ok"


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  Battery Notifier — running")
    print(f"  Poll interval : {POLL_INTERVAL}s")
    print(f"  Thresholds file: {THRESHOLDS_FILE}")
    print("  Edit thresholds via: streamlit run dashboard.py")
    print("=" * 55)

    monitor = BatteryMonitor()
    while True:
        try:
            monitor.check()
        except KeyboardInterrupt:
            print("\n[battery-notifier] Stopped.")
            break
        except Exception as e:
            print(f"[battery-notifier] Error: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
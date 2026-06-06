"""
run_tasks.py — Find the 梦幻西游 game window and run all daily task flows.

Usage:
  python src/run_tasks.py [--shimen] [--mijing] [--baotu]

If no flags are supplied, all three tasks are run in order.
"""
import sys
import os
import argparse
import time

# Ensure src/ is on the path when run from project root
sys.path.insert(0, os.path.dirname(__file__))

from utils.logger import Logger, add_file_handler
from bot.vision import Vision
from bot.actions import Actions
from bot.tasks import TaskRunner


def _setup_logging() -> str:
    """Force UTF-8 stdout and attach a canonical UTF-8 log file.

    Returns the path of the UTF-8 log file. This makes log output readable and
    machine-independent regardless of the host console code page or how the
    wrapping shell captures output.
    """
    # Reconfigure stdout/stderr to UTF-8 where supported (Python 3.7+).
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    log_path = ""
    try:
        log_dir = os.path.join(os.path.dirname(__file__), "img", "debug_captures")
        os.makedirs(log_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"run_{ts}_utf8.log")
        add_file_handler(log_path)
    except Exception:
        pass
    return log_path


_UTF8_LOG_PATH = _setup_logging()

LOG = Logger(__name__)


def _get_physical_window_rect(hwnd) -> tuple:
    """
    Get the physical screen rect for hwnd using DwmGetWindowAttribute.
    DWM always returns physical pixel coords regardless of process DPI awareness.
    Falls back to GetWindowRect scaled by DPI if DWM call fails.
    """
    import ctypes
    from ctypes import wintypes
    try:
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        rc = wintypes.RECT()
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
            ctypes.byref(rc), ctypes.sizeof(rc)
        )
        if hr == 0:
            return (rc.left, rc.top, rc.right, rc.bottom)
    except Exception:
        pass
    # Fallback: scale GetWindowRect by DPI
    try:
        import win32gui
        rect = win32gui.GetWindowRect(hwnd)
        dpi = ctypes.windll.user32.GetDpiForWindow(hwnd)
        if dpi and dpi != 96:
            s = dpi / 96.0
            return (int(rect[0]*s), int(rect[1]*s), int(rect[2]*s), int(rect[3]*s))
        return rect
    except Exception:
        return win32gui.GetWindowRect(hwnd)


def find_game_window() -> dict | None:
    """Return window_info dict for the first visible 梦幻西游 window, or None.

    The stored 'rect' is always in physical screen pixels (via DWM) so that
    PIL.ImageGrab.grab captures at the correct resolution regardless of process
    DPI awareness.

    Matching strategy (in order):
      1. Window title contains '梦幻西游'
      2. Process exe name contains 'mhxy' (case-insensitive)
    Minimized windows (rect coords at -32000) are skipped.
    """
    try:
        import win32gui
        import win32process
        import psutil
    except ImportError as e:
        LOG.error(f"Required package not available: {e}. Run: pip install pywin32 psutil")
        return None

    results = []

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        if not title or not title.strip():
            return True
        rect = win32gui.GetWindowRect(hwnd)
        # skip minimized windows
        if rect[0] <= -31000 or rect[1] <= -31000:
            return True
        # skip tiny/zero-size windows
        if rect[2] - rect[0] < 50 or rect[3] - rect[1] < 50:
            return True

        # Match by window title
        if "梦幻西游" in title:
            phys_rect = _get_physical_window_rect(hwnd)
            results.append({"handle": hwnd, "title": title, "rect": phys_rect, "rect_is_physical": True, "_score": 2})
            return True

        # Match by process exe name
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            exe = proc.name().lower()
            if "mhxy" in exe:
                phys_rect = _get_physical_window_rect(hwnd)
                results.append({"handle": hwnd, "title": title, "rect": phys_rect, "rect_is_physical": True, "_score": 1})
        except Exception:
            pass
        return True

    win32gui.EnumWindows(_cb, None)

    if not results:
        LOG.warning("No 梦幻西游 window found. Listing all visible windows for reference:")
        def _cb2(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t and t.strip():
                    r = win32gui.GetWindowRect(hwnd)
                    if r[2] - r[0] > 50 and r[3] - r[1] > 50 and r[0] > -31000:
                        LOG.warning(f"  hwnd={hwnd}  title={t!r}  rect={r}")
            return True
        win32gui.EnumWindows(_cb2, None)
        return None

    # prefer highest score (title match over exe match)
    results.sort(key=lambda x: x["_score"], reverse=True)
    win = {k: v for k, v in results[0].items() if k != "_score"}
    LOG.info(f"Using game window: {win['title']!r}  rect={win['rect']}")
    return win


def build_runner(win: dict) -> TaskRunner:
    vision = Vision(window_info=win)
    actions = Actions()
    return TaskRunner(vision, actions)


def _ensure_admin():
    """Relaunch this process as administrator if not already elevated.
    
    This is needed because the game (MyGame_x64r.exe) runs elevated and we need
    matching privileges for PostMessage and mouse input to work.
    """
    try:
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            return  # already admin
        # Relaunch as admin
        import subprocess
        script = os.path.abspath(__file__)
        args = " ".join(sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {args}', None, 1
        )
        sys.exit(0)  # exit non-elevated instance
    except Exception:
        pass  # if we can't self-elevate, just continue


def _minimize_console():
    """Minimize the current Python console window so it doesn't cover the game."""
    try:
        import ctypes
        import win32gui
        import win32con
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            time.sleep(0.5)
    except Exception:
        pass


def main():
    _ensure_admin()
    _minimize_console()
    parser = argparse.ArgumentParser(description="梦幻西游 daily task runner")
    parser.add_argument("--shimen", action="store_true", help="Run 师门任务 only")
    parser.add_argument("--mijing", action="store_true", help="Run 秘境降妖 only")
    parser.add_argument("--baotu",  action="store_true", help="Run 宝图任务 only")
    args = parser.parse_args()

    run_all = not (args.shimen or args.mijing or args.baotu)

    win = find_game_window()
    if win is None:
        print("[ERROR] Game window not found. Make sure 梦幻西游 is running and visible.")
        sys.exit(1)

    runner = build_runner(win)

    if _UTF8_LOG_PATH:
        LOG.info(f"UTF-8 log file: {_UTF8_LOG_PATH}")

    # Track each task's result so the final summary always shows every task,
    # even when a task is skipped or exits early.
    results = {"师门任务": "skipped", "秘境降妖": "skipped", "宝图任务": "skipped"}

    if run_all or args.shimen:
        LOG.info("=== START 师门任务 ===")
        try:
            done = runner.run_shimen_tasks(count=20)
            results["师门任务"] = f"{done} iteration(s)"
        except Exception as e:
            LOG.error(f"师门任务 raised: {e}")
            results["师门任务"] = f"ERROR: {e}"
        LOG.info(f"=== END 师门任务: {results['师门任务']} ===")

    if run_all or args.mijing:
        LOG.info("=== START 秘境降妖 ===")
        try:
            ok = runner.run_mijing_tasks()
            results["秘境降妖"] = "OK" if ok else "FAILED"
        except Exception as e:
            LOG.error(f"秘境降妖 raised: {e}")
            results["秘境降妖"] = f"ERROR: {e}"
        LOG.info(f"=== END 秘境降妖: {results['秘境降妖']} ===")

    if run_all or args.baotu:
        LOG.info("=== START 宝图任务 ===")
        try:
            ok = runner.run_baotu_tasks()
            results["宝图任务"] = "OK" if ok else "FAILED"
        except Exception as e:
            LOG.error(f"宝图任务 raised: {e}")
            results["宝图任务"] = f"ERROR: {e}"
        LOG.info(f"=== END 宝图任务: {results['宝图任务']} ===")

    LOG.info(
        "=== SUMMARY: 师门任务=%s | 秘境降妖=%s | 宝图任务=%s ==="
        % (results["师门任务"], results["秘境降妖"], results["宝图任务"])
    )
    LOG.info("All tasks done.")


if __name__ == "__main__":
    main()

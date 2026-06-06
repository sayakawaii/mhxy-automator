import threading
import time
from typing import Optional
from utils.logger import Logger
from .vision import Vision
from .actions import Actions
from .navigation import Navigation
from .tasks import TaskRunner

LOG = Logger(__name__)

class BotCore:
    """
    Lightweight coordinator for components. Keeps methods small so unit tests can stub components.
    """
    def __init__(self, actions: Actions, navigation: Navigation, vision: Vision):
        self.actions = actions
        self.navigation = navigation
        self.vision = vision

    def run_one_cycle(self):
        """
        Run a single logical cycle. This should be extended for mission-specific logic.
        Returns False when there's nothing more to do.
        """
        # Example cycle: capture window, try to read some text and log it.
        img = self.vision.capture_window()
        if img is None:
            LOG.warning("No image captured in run_one_cycle")
            return True  # keep trying

        text = self.vision.recognize_text(img)
        LOG.debug(f"Recognized text (truncated): {text[:200]}")
        # Placeholder behaviour: no mission -> idle
        return True

# Public Bot class expected by the UI (app.py imports Bot)
class Bot:
    def __init__(self, window_info: Optional[dict] = None, *,
                 actions: Optional[Actions] = None,
                 navigation: Optional[Navigation] = None,
                 vision: Optional[Vision] = None):
        """
        window_info: dict with keys 'handle','title','rect' produced by app.list_windows()
        Optional components can be injected for tests.
        """
        self.window_info = window_info or {}
        self._stop_event = threading.Event()
        self._thread = None
        # Lazy create components if not provided
        self.actions = actions or Actions()
        self.navigation = navigation or Navigation(self.actions)
        self.vision = vision or Vision(window_info=self.window_info)
        self.core = BotCore(self.actions, self.navigation, self.vision)
        # Task runner for higher-level automated tasks (template-based)
        self.task_runner = TaskRunner(self.vision, self.actions)
        LOG.info(f"Bot initialized for window: {self.window_info.get('title')}")

    def start(self):
        """
        Blocking method intended to be run in a background thread by the UI.
        Will run until stop() is called.
        """
        LOG.info("Bot start requested")
        self._stop_event.clear()
        # Start task runner in background when bot starts
        try:
            self.start_tasks_in_thread()
        except Exception as e:
            LOG.warning(f"Failed to start tasks thread: {e}")
        try:
            while not self._stop_event.is_set():
                cont = self.core.run_one_cycle()
                # simple sleep to avoid busy loop; in real bot this is mission dependent
                time.sleep(0.5)
                if not cont:
                    LOG.info("Core indicated no further work; entering idle sleep")
                    time.sleep(1.0)
        except Exception as e:
            LOG.error(f"Exception in bot loop: {e}")
            raise
        finally:
            LOG.info("Bot loop exited")

    def start_in_thread(self):
        if self._thread and self._thread.is_alive():
            LOG.warning("Bot already running")
            return
        self._thread = threading.Thread(target=self.start, daemon=True)
        self._thread.start()
        LOG.info("Bot thread started")

    def stop(self):
        LOG.info("Bot stop requested")
        # request tasks stop as well
        try:
            self.stop_tasks()
        except Exception:
            pass
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            LOG.info("Bot thread joined (or timeout)")

    # --- Task runner integration ---
    def run_tasks(self) -> bool:
        """Run the daily task flows: 师门任务 → 秘境降妖 → 宝图任务. Returns True on success."""
        LOG.info("Task run requested")
        try:
            # 1. 师门任务 (right-side shortcut button, up to 10 runs)
            completed = self.task_runner.run_shimen_tasks(count=10)
            LOG.info(f"师门任务 completed: {completed}")

            # 2. 秘境降妖 (activity panel)
            mijing_ok = self.task_runner.run_mijing_tasks()
            LOG.info(f"秘境降妖 completed: {mijing_ok}")

            # 3. 宝图任务 (activity panel; requires Task_BaoTu.png template in img/)
            baotu_ok = self.task_runner.run_baotu_tasks()
            LOG.info(f"宝图任务 completed: {baotu_ok}")

            return True
        except Exception as e:
            LOG.error(f"Exception while running tasks: {e}")
            return False

    def start_tasks_in_thread(self):
        """Start `run_tasks` in a background thread (non-blocking)."""
        if hasattr(self, "_tasks_thread") and getattr(self, "_tasks_thread") is not None and self._tasks_thread.is_alive():
            LOG.warning("Tasks already running")
            return
        def _target():
            try:
                self.run_tasks()
            except Exception as e:
                LOG.error(f"Background tasks thread exception: {e}")

        self._tasks_thread = threading.Thread(target=_target, daemon=True)
        self._tasks_thread.start()
        LOG.info("Tasks thread started")

    def stop_tasks(self):
        """Request stop for tasks thread and join if running. Note: task runner methods should check events if long-running."""
        if hasattr(self, "_tasks_thread") and self._tasks_thread is not None:
            LOG.info("Waiting for tasks thread to finish (or timeout)")
            self._tasks_thread.join(timeout=5.0)
            LOG.info("Tasks thread join attempted")

    # convenience methods used by tests or higher-level code
    def is_running(self):
        return self._thread is not None and self._thread.is_alive()
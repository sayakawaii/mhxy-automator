# filepath: mhxy-automator/mhxy-automator/src/plugins/example_plugin.py

import threading
import time
from utils.logger import Logger

LOG = Logger(__name__)

class ExamplePlugin:
    """
    Minimal plugin that can be started/stopped. Designed to be loaded by the bot.
    """
    def __init__(self, interval: float = 1.0):
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def _run_loop(self):
        LOG.info("ExamplePlugin loop started")
        while not self._stop.is_set():
            # plugin logic placeholder
            LOG.debug("ExamplePlugin heartbeat")
            time.sleep(self.interval)
        LOG.info("ExamplePlugin loop exiting")

    def run(self):
        if self._thread and self._thread.is_alive():
            LOG.warning("ExamplePlugin already running")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        LOG.info("ExamplePlugin started")

    def stop(self):
        LOG.info("ExamplePlugin stop requested")
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            LOG.info("ExamplePlugin stopped")

# Example usage
if __name__ == "__main__":
    p = ExamplePlugin(0.5)
    p.run()
    time.sleep(2.0)
    p.stop()
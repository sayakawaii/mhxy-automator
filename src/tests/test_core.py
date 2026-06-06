import unittest
import time
from bot.core import Bot
from bot.actions import Actions
from bot.navigation import Navigation
from bot.vision import Vision

class DummyActions(Actions):
    def __init__(self):
        super().__init__()
        self.clicked = []

    def click_mouse(self, x, y, button: str = "left"):
        self.clicked.append((x, y, button))

class DummyVision(Vision):
    def __init__(self):
        super().__init__(window_info={"rect": (0,0,100,100)})
        self._counter = 0

    def capture_window(self, window_info=None):
        # return a simple blank image for OCR-free tests
        try:
            from PIL import Image
            img = Image.new("RGB", (100, 100), color=(0,0,0))
            return img
        except Exception:
            return None

    def recognize_text(self, image):
        # return different text each call so loop can be observed
        self._counter += 1
        return f"dummy_text_{self._counter}"

class DummyNavigation(Navigation):
    def __init__(self, actions=None):
        super().__init__(actions or DummyActions())

class BotLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.actions = DummyActions()
        self.vision = DummyVision()
        self.navigation = DummyNavigation(self.actions)
        self.bot = Bot(window_info={"title": "dummy", "rect": (0,0,100,100)},
                       actions=self.actions, navigation=self.navigation, vision=self.vision)

    def test_start_stop_thread(self):
        # start in background thread and stop shortly after
        self.bot.start_in_thread()
        time.sleep(0.2)
        self.assertTrue(self.bot.is_running(), "Bot should be running after start")
        self.bot.stop()
        time.sleep(0.1)
        self.assertFalse(self.bot.is_running(), "Bot should have stopped")

    def tearDown(self):
        try:
            self.bot.stop()
        except Exception:
            pass

if __name__ == '__main__':
    unittest.main()
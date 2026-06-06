import time
from typing import Tuple, List, Optional
from utils.logger import Logger

LOG = Logger(__name__)

# Try to import pyautogui (optional). If not available, actions will raise when used.
try:
    import pyautogui
except Exception:
    pyautogui = None

# For OCR fallback (optional)
try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None

class Actions:
    """
    Encapsulate input actions (click/drag) and simple OCR helpers.
    Meant to be injected into Navigation/Vision for easier testing.
    """
    def click_mouse(self, x: int, y: int, button: str = "left"):
        LOG.debug(f"click_mouse at ({x},{y}) button={button}")
        if pyautogui:
            pyautogui.click(x, y, button=button)
        else:
            raise RuntimeError("pyautogui not available for click_mouse")

    def drag_mouse(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.2):
        LOG.debug(f"drag_mouse {start_x},{start_y} -> {end_x},{end_y} duration={duration}")
        if pyautogui:
            pyautogui.moveTo(start_x, start_y)
            pyautogui.dragTo(end_x, end_y, duration=duration)
        else:
            raise RuntimeError("pyautogui not available for drag_mouse")

    def extract_text_from_image(self, image) -> str:
        """
        Run OCR on provided PIL Image. Requires pytesseract installed.
        """
        LOG.debug("extract_text_from_image called")
        if pytesseract and Image is not None:
            return pytesseract.image_to_string(image)
        LOG.warning("pytesseract not available; returning empty string")
        return ""

    def get_coordinates_from_text(self, image, target_text: str) -> List[Tuple[int, int]]:
        """
        Return list of approximate center coordinates where target_text appears in the image.
        Uses pytesseract.image_to_data if available.
        """
        LOG.debug(f"get_coordinates_from_text searching for: {target_text!r}")
        coords = []
        if pytesseract is None:
            LOG.warning("pytesseract not available; returning empty coords")
            return coords

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as e:
            LOG.error(f"OCR data extraction failed: {e}")
            return coords

        n_boxes = len(data.get('text', []))
        for i in range(n_boxes):
            txt = (data['text'][i] or "").strip()
            if not txt:
                continue
            if target_text.lower() in txt.lower():
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                cx, cy = x + w // 2, y + h // 2
                coords.append((cx, cy))
        return coords

    def perform_action(self, action_type: str, *args, **kwargs):
        if action_type == "click":
            return self.click_mouse(*args, **kwargs)
        elif action_type == "drag":
            return self.drag_mouse(*args, **kwargs)
        elif action_type == "extract_text":
            return self.extract_text_from_image(*args, **kwargs)
        elif action_type == "get_coordinates":
            return self.get_coordinates_from_text(*args, **kwargs)
        else:
            raise ValueError(f"Unknown action type: {action_type}")
from typing import Optional, Tuple, List
from PIL import Image, ImageGrab
import io
from utils.logger import Logger

LOG = Logger(__name__)

# Try to import pytesseract; if not available, OCR functions will be no-ops
try:
    import pytesseract
except Exception:
    pytesseract = None

class Vision:
    """
    Vision helpers: capture window region, simple segmentation and OCR helpers.
    window_info: optional dict with 'rect'=(left,top,right,bottom)
    """
    def __init__(self, window_info: Optional[dict] = None):
        self.window_info = window_info or {}

    def capture_window(self, window_info: Optional[dict] = None) -> Optional[Image.Image]:
        """
        Capture the window rectangle using PIL.ImageGrab.
        The rect in window_info is expected to be in physical screen pixels
        (set by find_game_window using DwmGetWindowAttribute).
        Falls back to DPI-scaling logical GetWindowRect if rect_is_physical not set.
        Returns a PIL Image or None.
        """
        info = window_info or self.window_info
        rect = info.get('rect') if info else None
        if not rect:
            LOG.warning("No rect provided to capture_window")
            return None
        try:
            left, top, right, bottom = rect
            # Only scale if rect was NOT already obtained in physical pixels
            if not info.get('rect_is_physical'):
                try:
                    import ctypes
                    hwnd = int(info.get('handle') or 0)
                    dpi = ctypes.windll.user32.GetDpiForWindow(hwnd) if hwnd else 0
                    if dpi and dpi != 96:
                        s = dpi / 96.0
                        left   = int(left   * s)
                        top    = int(top    * s)
                        right  = int(right  * s)
                        bottom = int(bottom * s)
                except Exception:
                    pass
            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            return img
        except Exception as e:
            LOG.error(f"Failed to capture window: {e}")
            return None

    def segment_image(self, image: Image.Image, boxes: List[Tuple[int, int, int, int]]):
        """
        Simple cropping helper: receive image and list of (l,t,r,b) boxes and return list of crops.
        """
        crops = []
        for (l, t, r, b) in boxes:
            try:
                crops.append(image.crop((l, t, r, b)))
            except Exception as e:
                LOG.error(f"Failed to crop region {(l,t,r,b)}: {e}")
        return crops

    def locate_text(self, image: Image.Image, text: str) -> List[Tuple[int, int, int, int]]:
        """
        Return list of bounding boxes [(l,t,w,h), ...] where text appears.
        Uses pytesseract.image_to_data when available.
        """
        boxes = []
        if pytesseract is None:
            LOG.warning("pytesseract not available; locate_text returns empty list")
            return boxes

        try:
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        except Exception as e:
            LOG.error(f"OCR locate_text failed: {e}")
            return boxes

        n = len(data.get('text', []))
        for i in range(n):
            txt = (data['text'][i] or "").strip()
            if not txt:
                continue
            if text.lower() in txt.lower():
                l, t, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                boxes.append((l, t, w, h))
        return boxes

    def recognize_text(self, image: Image.Image) -> str:
        """
        Return OCR text for the provided image.
        """
        if pytesseract is None:
            LOG.warning("pytesseract not available; recognize_text returns empty string")
            return ""
        try:
            return pytesseract.image_to_string(image)
        except Exception as e:
            LOG.error(f"OCR recognize_text failed: {e}")
            return ""
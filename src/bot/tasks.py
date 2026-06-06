import time
import os
from typing import Optional, Tuple, List

import cv2
import numpy as np
from PIL import Image

from utils.logger import Logger
from .vision import Vision
from .actions import Actions

LOG = Logger(__name__)


def _save_annotated(img: Image.Image, box: Tuple[int, int, int, int], path: str):
    """Save a copy of `img` with `box` drawn for debugging."""
    try:
        from PIL import ImageDraw
        out = img.copy()
        draw = ImageDraw.Draw(out)
        l, t, r, b = box
        draw.rectangle([(l, t), (r, b)], outline=(255, 0, 0), width=3)
        out.save(path)
    except Exception:
        try:
            img.save(path)
        except Exception:
            LOG.debug(f"Failed to save annotated image to {path}")


def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR ndarray."""
    arr = np.array(pil_img.convert("RGB"))
    # RGB -> BGR
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _save_grid_with_circle(pil_img: Image.Image, coord: Tuple[int, int], path: str, grid_step: int = 10, circle_radius: int = 6):
    """Draw vertical/horizontal red grid lines every `grid_step` pixels and a red circle at `coord` then save.

    `coord` is in the image coordinate space of `pil_img`.
    """
    try:
        from PIL import ImageDraw
        out = pil_img.convert("RGBA").copy()
        draw = ImageDraw.Draw(out)
        w, h = out.size
        # grid lines
        line_color = (255, 0, 0, 255)
        for x in range(0, w, grid_step):
            draw.line([(x, 0), (x, h)], fill=line_color)
        for y in range(0, h, grid_step):
            draw.line([(0, y), (w, y)], fill=line_color)

        # circle at coord
        cx, cy = int(coord[0]), int(coord[1])
        bbox = [cx - circle_radius, cy - circle_radius, cx + circle_radius, cy + circle_radius]
        draw.ellipse(bbox, outline=line_color, width=3)

        out.save(path)
    except Exception:
        try:
            pil_img.save(path)
        except Exception:
            LOG.debug(f"Failed to save grid image to {path}")


def match_template_with_score(screen_img: Image.Image, template_path: str, threshold: float = 0.8) -> Tuple[Optional[Tuple[int, int, int, int]], float]:
    """
    Find the template in screen_img. Returns (bounding box (l,t,r,b) or None, best_score).

    The best_score is returned even when below threshold so callers can log how
    close a match was (useful for diagnosing "button not found" issues).
    Automatically scales large templates to match the current window size.
    """
    if not os.path.exists(template_path):
        LOG.error(f"Template not found: {template_path}")
        return None, -1.0

    screen_cv = _pil_to_cv2(screen_img)
    template_pil = Image.open(template_path).convert("RGBA")
    template_cv = _pil_to_cv2(template_pil)

    # use grayscale matching for robustness
    screen_gray = cv2.cvtColor(screen_cv, cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template_cv, cv2.COLOR_BGR2GRAY)

    screen_h, screen_w = screen_gray.shape[:2]
    templ_h, templ_w = template_gray.shape[:2]

    # debug sizes
    try:
        LOG.debug(f"Screen size: {screen_gray.shape}, Template size: {template_gray.shape}")
    except Exception:
        pass

    # Always compute the natural scale from the current window vs reference width.
    # Templates were captured at REF_WINDOW_WIDTH; scale accordingly.
    REF_WINDOW_WIDTH = 1638
    natural_scale = screen_w / REF_WINDOW_WIDTH
    # For templates that are already tiny (≤4px after scale) skip
    scales_to_try = sorted(set([
        round(natural_scale, 2),
        round(natural_scale * 0.95, 2),
        round(natural_scale * 1.05, 2),
        1.0,  # always try 1:1 as fallback
    ]))

    best_val = -1.0
    best_loc = (0, 0)
    best_tw, best_th = templ_w, templ_h

    for scale in scales_to_try:
        tw = max(1, int(templ_w * scale))
        th = max(1, int(templ_h * scale))
        if tw > screen_w or th > screen_h or tw < 2 or th < 2:
            continue
        tg = cv2.resize(template_gray, (tw, th), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR)
        res = cv2.matchTemplate(screen_gray, tg, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        LOG.debug(f"Template {template_path} scale={scale:.2f} score={max_val:.3f} at {max_loc}")
        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_tw, best_th = tw, th

    LOG.debug(f"Template match {template_path} best_score={best_val:.3f}")
    if best_val < threshold:
        return None, best_val

    l, t = int(best_loc[0]), int(best_loc[1])
    return (l, t, l + best_tw, t + best_th), best_val


def match_template(screen_img: Image.Image, template_path: str, threshold: float = 0.8) -> Optional[Tuple[int, int, int, int]]:
    """
    Find the template in screen_img. Returns bounding box (l,t,r,b) of best match or None.
    Thin wrapper over `match_template_with_score` for callers that only need the box.
    """
    box, _ = match_template_with_score(screen_img, template_path, threshold=threshold)
    return box


class TaskRunner:
    """High-level task runner that uses Vision and Actions to complete tasks.

    Usage:
      vr = Vision(window_info)
      act = Actions()
      tr = TaskRunner(vr, act)
      tr.run_shimen_tasks(count=10)
    """

    def __init__(self, vision: Vision, actions: Actions, templates_dir: str = None):
        self.vision = vision
        self.actions = actions
        # Resolve templates directory robustly: prefer provided path, then project img/ next to repo root,
        # then src/img, then cwd/img. This avoids issues when running from `src/` vs project root.
        candidates = []
        if templates_dir:
            candidates.append(templates_dir)
        # project-root img: assume tasks.py is in src/bot -> go up 3 levels to repo root
        try:
            repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            candidates.append(os.path.join(repo_root, "img"))
        except Exception:
            pass
        # src/img (if img placed under src/)
        try:
            src_dir = os.path.dirname(os.path.dirname(__file__))
            candidates.append(os.path.join(src_dir, "img"))
        except Exception:
            pass
        # cwd/img fallback
        candidates.append(os.path.join(os.getcwd(), "img"))

        chosen = None
        for c in candidates:
            if c and os.path.isdir(c):
                chosen = c
                break
        if chosen is None:
            chosen = candidates[0] if candidates else os.path.join(os.getcwd(), "img")
            LOG.warning(f"Templates directory not found; using {chosen} (will likely fail to find templates)")
        else:
            LOG.info(f"Using templates directory: {chosen}")

        self.templates_dir = chosen
        self._ensure_cropped_templates()

    def _ensure_cropped_templates(self):
        """Create left-50%-cropped versions of templates that have dynamic count text on the right."""
        CROP_RATIO = 0.50
        templates_to_crop = ["Task_ShiMen.png", "Task_MiJing.png", "Task_BaoTu.png"]
        for name in templates_to_crop:
            src = os.path.join(self.templates_dir, name)
            dst = os.path.join(self.templates_dir, name.replace(".png", "_crop.png"))
            if os.path.exists(src) and not os.path.exists(dst):
                try:
                    img = Image.open(src)
                    w, h = img.size
                    cropped = img.crop((0, 0, int(w * CROP_RATIO), h))
                    cropped.save(dst)
                    LOG.info(f"Created cropped template: {dst}")
                except Exception as e:
                    LOG.warning(f"Failed to crop template {name}: {e}")

    def _capture(self) -> Optional[Image.Image]:
        # If a window handle is known, try to bring it to foreground before capture
        info = getattr(self.vision, "window_info", None) or {}
        hwnd = info.get("handle")
        try:
            import win32gui
            import win32con
            if hwnd:
                try:
                    # restore if minimized
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                except Exception:
                    pass
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
        except Exception:
            # pywin32 not available; continue
            pass

        img = self.vision.capture_window()
        if img is None:
            LOG.warning("capture returned None")
        else:
            # log rect used if available
            try:
                rect = info.get("rect")
                if rect:
                    LOG.debug(f"Captured rect: {rect}")
            except Exception:
                pass
        return img

    def _click_box_center(self, box: Tuple[int, int, int, int]):
        l, t, r, b = box
        x_img = (l + r) // 2
        y_img = (t + b) // 2

        info = getattr(self.vision, "window_info", None) or {}
        rect_is_physical = bool(info.get("rect_is_physical"))

        # Determine DPI scale (always needed for pyautogui logical coords and mouse_event normalization)
        scale = 1.0
        v_offset_x = 0
        v_offset_y = 0
        try:
            import ctypes
            user32 = ctypes.windll.user32
            try:
                hwnd_for_dpi = int(info.get("handle") or 0)
                if hwnd_for_dpi:
                    dpi = user32.GetDpiForWindow(hwnd_for_dpi)
                    scale = float(dpi) / 96.0 if dpi else 1.0
            except Exception:
                try:
                    hdc = ctypes.windll.user32.GetDC(0)
                    LOGPIXELSX = 88
                    dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
                    if dpi_x and dpi_x > 0:
                        scale = float(dpi_x) / 96.0
                except Exception:
                    pass
            try:
                SM_XVIRTUALSCREEN = 76; SM_YVIRTUALSCREEN = 77
                v_offset_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                v_offset_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
            except Exception:
                pass
        except Exception:
            pass

        # x_img/y_img are in PHYSICAL pixels (capture is at physical DPI scale via DWM rect).
        # Compute physical screen coordinates by adding the physical rect offset.
        left = top = None
        try:
            rect = info.get("rect")
            if rect and isinstance(rect, (list, tuple)) and len(rect) >= 2:
                left, top = rect[0], rect[1]
        except Exception:
            rect = None

        if rect_is_physical:
            # rect stored in physical pixels → x_img + left = physical screen coord directly
            trans_x = int(x_img + (left or 0))
            trans_y = int(y_img + (top  or 0))
            # logical coords for pyautogui
            x = int(trans_x / scale)
            y = int(trans_y / scale)
        else:
            # Legacy path: rect in logical coords → convert x_img to logical, add offset
            x = int(x_img / scale) + int(left or 0)
            y = int(y_img / scale) + int(top  or 0)
            trans_x = int(x * scale)
            trans_y = int(y * scale)

        LOG.info(f"Clicking image-center=({x_img},{y_img}) physical=({trans_x},{trans_y}) rect_phys={rect_is_physical}")

        # Bring game window to foreground BEFORE any click so input lands correctly
        try:
            _hwnd_fg = int(info.get("handle") or 0) if info else 0
            if _hwnd_fg:
                import win32gui as _w32gui_fg
                import win32con as _w32con_fg
                try:
                    _w32gui_fg.ShowWindow(_hwnd_fg, _w32con_fg.SW_RESTORE)
                except Exception:
                    pass
                try:
                    _w32gui_fg.SetForegroundWindow(_hwnd_fg)
                    time.sleep(0.25)
                except Exception:
                    pass
        except Exception as e:
            LOG.debug(f"SetForegroundWindow before click failed: {e}")

        # Try to move the mouse slightly before clicking to simulate real interaction
        # determine function to get/set mouse position for logging
        get_pos = None
        _pya = None
        try:
            import pyautogui as _pyautogui
            _pya = _pyautogui
            get_pos = lambda: _pya.position()
            LOG.debug("pyautogui available for mouse control")
        except Exception:
            try:
                import ctypes
                pt = ctypes.wintypes.POINT()
                def _get():
                    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
                    return (pt.x, pt.y)
                get_pos = _get
                LOG.debug("Using Win32 GetCursorPos for mouse position queries")
            except Exception:
                get_pos = None
                LOG.debug("No method available to query mouse position")

        pre_pos = None
        try:
            if get_pos:
                pre_pos = get_pos()
                LOG.info(f"Mouse pre-move position: {pre_pos}")
            # pyautogui uses physical screen coords on DPI-scaled displays (size() returns physical dims)
            if _pya is not None:
                try:
                    _pya.click(trans_x, trans_y)
                    LOG.debug(f"pyautogui.click sent at physical ({trans_x},{trans_y})")
                except Exception as e:
                    LOG.debug(f"pyautogui.click failed: {e}")
        except Exception:
            LOG.debug("Failed to query/move mouse pre-click")

        # --- save grid debug images: window-relative grid and full-desktop grid ---
        try:
            dbg_dir = os.path.join(self.templates_dir, "debug_captures")
            os.makedirs(dbg_dir, exist_ok=True)
            ts = int(time.time())
            # window-capture grid (image coords)
            try:
                win_img = self.vision.capture_window()
                if win_img is not None:
                    win_path = os.path.join(dbg_dir, f"dbg_grid_window_{ts}.png")
                    _save_grid_with_circle(win_img, (x_img, y_img), win_path)
                    LOG.info(f"Saved window-grid image to {win_path}")
            except Exception as e:
                LOG.debug(f"Failed to save window grid image: {e}")

            # desktop grid (screen coords)
            try:
                desktop = None
                try:
                    import pyautogui as _pya2
                    desktop = _pya2.screenshot()
                except Exception:
                    try:
                        from PIL import ImageGrab
                        desktop = ImageGrab.grab()
                    except Exception:
                        desktop = None
                if desktop is not None:
                    desk_path = os.path.join(dbg_dir, f"dbg_grid_desktop_{ts}.png")
                    # mark transformed screen coordinates on desktop image
                    _save_grid_with_circle(desktop, (trans_x, trans_y), desk_path)
                    LOG.info(f"Saved desktop-grid image to {desk_path}")
            except Exception as e:
                LOG.debug(f"Failed to save desktop grid image: {e}")
        except Exception:
            LOG.debug("Failed to write debug grid captures")

        post_move_pos = None
        try:
            if get_pos:
                post_move_pos = get_pos()
                LOG.info(f"Mouse post-move position: {post_move_pos}")
        except Exception:
            LOG.debug("Failed to query mouse post-move")

        # If move did not occur, try Win32 SetCursorPos as a fallback
        moved = (post_move_pos is not None and pre_pos is not None and post_move_pos != pre_pos)
        if not moved:
            try:
                import ctypes
                try:
                    # try setting physical cursor position first (use transformed coords)
                    res = ctypes.windll.user32.SetCursorPos(int(trans_x), int(trans_y))
                    LOG.info(f"Tried SetCursorPos fallback (physical coords), SetCursorPos returned: {res}")
                    # re-query
                    if get_pos:
                        post_move_pos = get_pos()
                        LOG.info(f"Mouse post-SetCursorPos position: {post_move_pos}")
                        moved = (pre_pos is not None and post_move_pos != pre_pos)
                    # if SetCursorPos didn't move the cursor, try SendInput/mouse_event absolute move+click
                    if not moved:
                        try:
                            user32 = ctypes.windll.user32
                            SM_CXVIRTUALSCREEN = 78
                            SM_CYVIRTUALSCREEN = 79
                            vx = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(0)
                            vy = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(1)
                            if vx <= 0:
                                vx = 1
                            if vy <= 0:
                                vy = 1
                            MOUSEEVENTF_MOVE = 0x0001
                            MOUSEEVENTF_ABSOLUTE = 0x8000
                            MOUSEEVENTF_LEFTDOWN = 0x0002
                            MOUSEEVENTF_LEFTUP = 0x0004
                            # Normalise physical coords into virtual-screen space (0..65535)
                            # Virtual screen starts at v_offset_x (SM_XVIRTUALSCREEN, may be negative)
                            px = max(0, min(vx, int(trans_x) - v_offset_x))
                            py = max(0, min(vy, int(trans_y) - v_offset_y))
                            nx = int(px * 65535 / vx)
                            ny = int(py * 65535 / vy)
                            # move absolute
                            ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0)
                            # click
                            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            LOG.info("Tried mouse_event SendInput fallback (absolute move + click)")
                            if get_pos:
                                post_move_pos = get_pos()
                                LOG.info(f"Mouse post-SendInput position: {post_move_pos}")
                                moved = (pre_pos is not None and post_move_pos != pre_pos)
                        except Exception as e:
                            LOG.debug(f"SendInput/mouse_event fallback failed: {e}")
                except Exception as e:
                    LOG.debug(f"SetCursorPos failed: {e}")
            except Exception:
                LOG.debug("ctypes not available for SetCursorPos fallback")

        # Actions should provide a click method in screen coords; adapt if needed
        # pyautogui (via Actions) uses physical coords on DPI-scaled displays
        clicked = False
        try:
            self.actions.click_mouse(trans_x, trans_y)
            clicked = True
            LOG.debug(f"Actions.click_mouse invoked at physical ({trans_x},{trans_y})")
        except Exception as e:
            LOG.error(f"Actions.click failed: {e}")

        # As some games use raw/physical input, also send a Win32 left-click via mouse_event at physical coords
        try:
            import ctypes
            try:
                user32 = ctypes.windll.user32
                SM_CXVIRTUALSCREEN = 78
                SM_CYVIRTUALSCREEN = 79
                vx = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(0)
                vy = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(1)
                if vx <= 0:
                    vx = 1
                if vy <= 0:
                    vy = 1
                MOUSEEVENTF_MOVE = 0x0001
                MOUSEEVENTF_ABSOLUTE = 0x8000
                MOUSEEVENTF_LEFTDOWN = 0x0002
                MOUSEEVENTF_LEFTUP = 0x0004
                # Normalise physical coords into virtual-screen space (0..65535)
                px = max(0, min(vx, int(trans_x) - v_offset_x))
                py = max(0, min(vy, int(trans_y) - v_offset_y))
                nx = int(px * 65535 / vx)
                ny = int(py * 65535 / vy)
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny, 0, 0)
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                LOG.debug("Sent Win32 left-click via mouse_event at physical coords")
            except Exception as e:
                LOG.debug(f"Win32 left-click via mouse_event failed: {e}")
        except Exception:
            pass

        # PostMessage: inject click directly into game's message queue (works regardless of focus)
        try:
            _hwnd_pm = int(info.get("handle") or 0) if info else 0
            if _hwnd_pm:
                import win32api as _w32api_pm
                import win32gui as _w32gui_pm
                import win32con as _w32con_pm
                _cx, _cy = _w32gui_pm.ScreenToClient(_hwnd_pm, (trans_x, trans_y))
                _lp = _w32api_pm.MAKELONG(_cx, _cy)
                _w32api_pm.PostMessage(_hwnd_pm, _w32con_pm.WM_LBUTTONDOWN, _w32con_pm.MK_LBUTTON, _lp)
                time.sleep(0.05)
                _w32api_pm.PostMessage(_hwnd_pm, _w32con_pm.WM_LBUTTONUP, 0, _lp)
                LOG.info(f"PostMessage WM_LBUTTON at client=({_cx},{_cy})")
        except Exception as e:
            LOG.debug(f"PostMessage click failed: {e}")

        # verify mouse position after click as additional signal
        try:
            if get_pos:
                after_click_pos = get_pos()
                LOG.info(f"Mouse after-click position: {after_click_pos}")
        except Exception:
            LOG.debug("Failed to query mouse after-click")

        LOG.info(f"Click attempted: moved={moved}, clicked={clicked}")
        # Save a final debug capture marking the mouse stop position (red circle)
        try:
            dbg_dir = os.path.join(self.templates_dir, "debug_captures")
            os.makedirs(dbg_dir, exist_ok=True)
            ts = int(time.time())
            desktop = None
            try:
                import pyautogui as _pya3
                desktop = _pya3.screenshot()
            except Exception:
                try:
                    from PIL import ImageGrab
                    desktop = ImageGrab.grab()
                except Exception:
                    desktop = None

            if desktop is not None:
                # determine circle coordinate in the image's coordinate space
                try:
                    if post_move_pos is not None:
                        cx, cy = post_move_pos
                    else:
                        cx, cy = (trans_x, trans_y)
                    # desktop image origin is the virtual screen origin; adjust by virtual offsets
                    img_coord = (int(cx - v_offset_x), int(cy - v_offset_y))
                except Exception:
                    img_coord = (int(trans_x - v_offset_x), int(trans_y - v_offset_y))

                stop_path = os.path.join(dbg_dir, f"dbg_mouse_stop_{ts}.png")
                _save_grid_with_circle(desktop, img_coord, stop_path)
                LOG.info(f"Saved mouse-stop debug image to {stop_path}")
        except Exception as e:
            LOG.debug(f"Failed to save mouse-stop debug image: {e}")

    def find_and_click(self, template_name: str, timeout: float = 5.0, threshold: float = 0.8) -> bool:
        """Try to find template and click it. Return True if clicked."""
        tpl = os.path.join(self.templates_dir, template_name)
        end = time.time() + timeout
        while time.time() < end:
            img = self._capture()
            if img is None:
                time.sleep(0.5)
                continue
            box = match_template(img, tpl, threshold=threshold)
            if box:
                # save annotated pre-click debug image
                try:
                    dbg_dir = os.path.join(self.templates_dir, "debug_captures")
                    os.makedirs(dbg_dir, exist_ok=True)
                    ts = int(time.time())
                    ann_path = os.path.join(dbg_dir, f"dbg_found_{template_name}_{ts}.png")
                    _save_annotated(img, box, ann_path)
                    LOG.debug(f"Saved annotated pre-click image to {ann_path}")
                except Exception as e:
                    LOG.debug(f"Failed to save annotated pre-click image: {e}")

                self._click_box_center(box)

                # wait briefly for UI to update, then save immediate post-click capture
                try:
                    time.sleep(0.45)
                    post = self._capture()
                    if post is not None:
                        post_path = os.path.join(self.templates_dir, "debug_captures", f"dbg_postclick_{template_name}_{int(time.time())}.png")
                        post.save(post_path)
                        LOG.debug(f"Saved post-click capture to {post_path}")
                except Exception as e:
                    LOG.debug(f"Failed to save post-click capture: {e}")

                return True
            else:
                # save debug capture for inspection (single file per template attempt)
                try:
                    dbg_dir = os.path.join(self.templates_dir, "debug_captures")
                    os.makedirs(dbg_dir, exist_ok=True)
                    ts = int(time.time())
                    dbg_path = os.path.join(dbg_dir, f"dbg_{template_name}_{ts}.png")
                    img.save(dbg_path)
                    LOG.debug(f"Saved debug capture to {dbg_path}")
                except Exception as e:
                    LOG.debug(f"Failed to save debug capture: {e}")
            time.sleep(0.3)
        LOG.info(f"Template {template_name} not found within {timeout}s")
        return False

    def open_activity(self) -> bool:
        """Open the 活动 activity panel, closing any blocking panels first."""
        info = getattr(self.vision, "window_info", None) or {}
        hwnd = info.get("handle")

        # Bring game to foreground before sending input
        if hwnd:
            try:
                import win32gui as _w32gui
                import win32con as _w32con
                _w32gui.ShowWindow(hwnd, _w32con.SW_RESTORE)
                _w32gui.SetForegroundWindow(hwnd)
                time.sleep(0.4)
            except Exception as e:
                LOG.debug(f"SetForegroundWindow in open_activity failed: {e}")

        # ClosePanel_X.png (shield/gold style) is the ACTIVITY LIST's own close button (scores
        # 0.97 on activity list). Using it at a low threshold causes false positives everywhere.
        # Instead we use:
        #   - ClosePanel_X2 (cloud + red X): the 指引 tutorial panel close button
        #   - ClosePanel_X3 (round red circle): the 攻略 guide panel close button
        _PRE_TEMPLATES = ("ClosePanel_X2.png", "ClosePanel_X3.png")
        # Same templates are safe post-open (both score <0.70 on activity list at threshold 0.70)
        _POST_TEMPLATES = ("ClosePanel_X2.png", "ClosePanel_X3.png")

        def _close_blocking_panels(templates: tuple, max_attempts: int, threshold: float) -> None:
            """Close any blocking panels using the given close-button templates."""
            for _attempt in range(max_attempts):
                img_check = self._capture()
                if img_check is None:
                    break
                panel_found = False
                for x_tpl_name in templates:
                    x_tpl = os.path.join(self.templates_dir, x_tpl_name)
                    if not os.path.exists(x_tpl):
                        continue
                    box = match_template(img_check, x_tpl, threshold=threshold)
                    if box:
                        LOG.info(f"[open_activity] Panel close button ({x_tpl_name}) found (attempt {_attempt+1}), clicking")
                        self._click_box_center(box)
                        time.sleep(1.2)
                        panel_found = True
                        break
                if not panel_found:
                    break
                if hwnd:
                    try:
                        import win32api as _w32api_esc, win32con as _w32con_esc
                        _w32api_esc.PostMessage(hwnd, _w32con_esc.WM_KEYDOWN, _w32con_esc.VK_ESCAPE, 0)
                        time.sleep(0.05)
                        _w32api_esc.PostMessage(hwnd, _w32con_esc.WM_KEYUP, _w32con_esc.VK_ESCAPE, 0)
                        time.sleep(0.4)
                    except Exception:
                        pass

        # Close any pre-existing blocking panels (use all templates at low threshold)
        _close_blocking_panels(_PRE_TEMPLATES, max_attempts=4, threshold=0.50)

        # Click the 活动 button to open the activity list panel
        if not self.find_and_click("Initial_Activity.png", timeout=8.0, threshold=0.58):
            return False

        # Wait for the activity list to load, then close any guide panels that
        # auto-appeared (e.g. 攻略 pop-ups). Use POST templates only at higher
        # threshold so the activity list's own X button (ClosePanel_X, score=0.97)
        # is never accidentally closed.
        time.sleep(1.5)
        _close_blocking_panels(_POST_TEMPLATES, max_attempts=3, threshold=0.70)
        return True

    def wait_for_template(self, template_name: str, timeout: float = 60.0, threshold: float = 0.78) -> bool:
        """Poll until template appears. Returns True if found within timeout.

        Returns False immediately if template file does not exist.
        """
        tpl = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(tpl):
            LOG.debug(f"wait_for_template: {template_name} not on disk, skipping")
            return False
        LOG.info(f"Waiting up to {timeout}s for template to appear: {template_name}")
        end = time.time() + timeout
        while time.time() < end:
            img = self._capture()
            if img is None:
                time.sleep(0.5)
                continue
            if match_template(img, tpl, threshold=threshold):
                LOG.info(f"Template {template_name} appeared")
                return True
            time.sleep(0.5)
        LOG.warning(f"Template {template_name} did not appear within {timeout}s")
        return False

    def wait_for_template_gone(self, template_name: str, timeout: float = 60.0, threshold: float = 0.75) -> bool:
        """Poll until template is NO LONGER visible. Returns True once gone (or if file missing).

        Used to detect completion by absence (e.g., 师门任务 button disappearing when all tasks done).
        """
        tpl = os.path.join(self.templates_dir, template_name)
        if not os.path.exists(tpl):
            return True
        LOG.info(f"Waiting up to {timeout}s for template to disappear: {template_name}")
        end = time.time() + timeout
        while time.time() < end:
            img = self._capture()
            if img is None:
                time.sleep(0.5)
                continue
            if not match_template(img, tpl, threshold=threshold):
                LOG.info(f"Template {template_name} is gone")
                return True
            time.sleep(0.5)
        LOG.warning(f"Template {template_name} still visible after {timeout}s")
        return False

    # ------------------------------------------------------------------
    # 师门任务
    # ------------------------------------------------------------------
    def run_shimen_tasks(self, count: int = 20) -> int:
        """Click 师门任务 button on the right side repeatedly until it disappears.

        Completion signal: the 师门任务 shortcut button on the right side of the screen
        disappears once all daily tasks are done.

        Flow per iteration:
          1. Look for Task_ShiMen.png — if gone, all done.
          2. Click it.
          3. Click Task_Join.png to start the task.
          4. Wait per-task (~60s fixed) then check button again.
        """
        # Per-task wait: typical 师门 task takes ~30-60 s; use 60s as safe upper bound.
        SHIMEN_TASK_WAIT = 60.0
        # Match threshold for the right-side shortcut button. Kept low because the
        # button carries dynamic count text; we match the cropped (left-half) template.
        SHIMEN_THRESHOLD = 0.55

        completed = 0
        for i in range(count):
            LOG.info(f"师门任务 iteration {i + 1}")

            # 1. Check if button is still present — absence means all tasks done
            img = self._capture()
            if img is None:
                LOG.warning("Capture failed, stopping 师门任务")
                break

            # On the first iteration, always save a reference capture so the test
            # agent has a frame to inspect when the button is reported "not found".
            if i == 0:
                try:
                    dbg_dir = os.path.join(self.templates_dir, "debug_captures")
                    os.makedirs(dbg_dir, exist_ok=True)
                    ref_path = os.path.join(dbg_dir, f"dbg_shimen_start_{int(time.time())}.png")
                    img.save(ref_path)
                    LOG.info(f"师门任务: saved start reference capture to {ref_path}")
                except Exception as e:
                    LOG.debug(f"师门任务: failed to save start reference capture: {e}")

            # Try both the cropped and full templates; log the best score for each
            # so we can tell whether the button is genuinely absent or just below
            # threshold (ISSUE-001 diagnosis).
            box = None
            for tpl_name in ("Task_ShiMen_crop.png", "Task_ShiMen.png"):
                tpl_path = os.path.join(self.templates_dir, tpl_name)
                if not os.path.exists(tpl_path):
                    continue
                cand_box, score = match_template_with_score(img, tpl_path, threshold=SHIMEN_THRESHOLD)
                LOG.info(f"师门任务: {tpl_name} best_score={score:.3f} (threshold={SHIMEN_THRESHOLD})")
                if cand_box:
                    box = cand_box
                    break
            if not box:
                LOG.info("师门任务 button not found (all templates below threshold) — assuming all daily tasks completed")
                break

            # 2. Click the 师门任务 button
            self._click_box_center(box)
            time.sleep(1.2)

            # 3. Click Join/Confirm button in the popup panel
            if not self.find_and_click("Task_Join.png", timeout=6.0, threshold=0.55):
                LOG.warning(f"Join button not found for 师门任务 {i + 1}; task may have auto-started")

            LOG.info(f"师门任务 {i + 1} started — waiting {SHIMEN_TASK_WAIT}s")
            time.sleep(SHIMEN_TASK_WAIT)
            completed += 1

        LOG.info(f"师门任务 finished — completed {completed} iteration(s)")
        return completed

    # ------------------------------------------------------------------
    # 秘境降妖
    # ------------------------------------------------------------------
    def run_mijing_tasks(self) -> bool:
        """Open activity panel → 秘境降妖 → join → wait for teleport → wait for battle.

        Completion signal: Task_Complete.png popup (if template available), otherwise
        falls back to a fixed 600 s wait.
        """
        # 1. Open activity panel
        if not self.open_activity():
            LOG.error("Failed to open activity panel for 秘境降妖")
            return False
        time.sleep(1.2)

        # 2. Find and click 秘境降妖 entry
        if not self.find_and_click("Task_MiJing_crop.png", timeout=8.0, threshold=0.55):
            if not self.find_and_click("Task_MiJing.png", timeout=4.0, threshold=0.55):
                LOG.warning("秘境降妖 icon not found in activity panel")
                return False
        time.sleep(0.8)

        # 3. Click Join/Start button
        if not self.find_and_click("Task_Join.png", timeout=6.0, threshold=0.55):
            LOG.warning("Join/Start button not found for 秘境降妖")
            return False

        # 4. Wait for teleport animation (~20 s)
        LOG.info("秘境降妖: joined — waiting ~20s for teleport")
        time.sleep(20.0)

        # 5. Wait for battle completion (Task_Complete.png popup, or fallback 600 s)
        MIJING_TIMEOUT = 600.0
        LOG.info(f"秘境降妖: waiting up to {MIJING_TIMEOUT}s for battle completion")
        if self.wait_for_template("Task_Complete.png", timeout=MIJING_TIMEOUT, threshold=0.78):
            LOG.info("秘境降妖 completed — clicking completion dialog")
            self.find_and_click("Task_Complete.png", timeout=5.0, threshold=0.78)
        else:
            LOG.info(f"秘境降妖: no completion template; assumed done after {MIJING_TIMEOUT}s wait")

        LOG.info("秘境降妖 task flow finished")
        return True

    # ------------------------------------------------------------------
    # 宝图任务
    # ------------------------------------------------------------------
    def run_baotu_tasks(self) -> bool:
        """Open activity panel → 宝图任务 → start → fixed wait for completion.

        Completion signal: no popup for 宝图任务, so we use a fixed 300 s wait.
        If Task_Complete.png exists in img/ it will be used instead.
        """
        BAOTU_TEMPLATE = "Task_BaoTu.png"
        BAOTU_FIXED_WAIT = 300.0  # seconds; adjust if typical 宝图 run takes longer

        # 1. Open activity panel
        if not self.open_activity():
            LOG.error("Failed to open activity panel for 宝图任务")
            return False
        time.sleep(1.2)

        # 2. Find and click 宝图任务 entry
        if not self.find_and_click(BAOTU_TEMPLATE.replace(".png", "_crop.png"), timeout=8.0, threshold=0.55):
            if not self.find_and_click(BAOTU_TEMPLATE, timeout=4.0, threshold=0.55):
                LOG.warning("宝图任务 icon not found in activity panel")
                return False
        time.sleep(0.8)

        # 3. Click Join/Start button
        if not self.find_and_click("Task_Join.png", timeout=6.0, threshold=0.55):
            LOG.warning("Join/Start button not found for 宝图任务")
            return False

        LOG.info("宝图任务 started")

        # 4. Wait for completion — prefer Task_Complete.png popup if it exists,
        #    otherwise do a fixed timed wait (no popup for 宝图任务).
        tpl_complete = os.path.join(self.templates_dir, "Task_Complete.png")
        if os.path.exists(tpl_complete):
            LOG.info(f"宝图任务: waiting up to {BAOTU_FIXED_WAIT}s for completion popup")
            if self.wait_for_template("Task_Complete.png", timeout=BAOTU_FIXED_WAIT, threshold=0.78):
                LOG.info("宝图任务 completed — clicking completion dialog")
                self.find_and_click("Task_Complete.png", timeout=5.0, threshold=0.78)
            else:
                LOG.info("宝图任务: completion popup not seen; assuming done")
        else:
            LOG.info(f"宝图任务: no completion template available; waiting fixed {BAOTU_FIXED_WAIT}s")
            time.sleep(BAOTU_FIXED_WAIT)
            LOG.info("宝图任务: fixed wait done, assuming completed")

        LOG.info("宝图任务 task flow finished")
        return True


__all__ = ["TaskRunner", "match_template", "match_template_with_score"]

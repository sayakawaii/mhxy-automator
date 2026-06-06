import tkinter as tk
from tkinter import messagebox, ttk
from bot.core import Bot
import threading
from utils.logger import Logger

# new imports
try:
    import win32gui
    import win32con
    from PIL import Image, ImageTk, ImageGrab
except Exception:
    win32gui = None
    Image = None
    ImageTk = None
    ImageGrab = None

def on_window_select(window_info):
    """
    window_info: dict produced by list_windows() (contains 'handle' and 'title')
    Start the bot in a background thread so the UI stays responsive.
    """
    if not window_info:
        messagebox.showerror("Error", "No window selected.")
        return

    bot = Bot(window_info)  # Bot should accept the window info (handle/title) — adapt if needed
    t = threading.Thread(target=bot.start, daemon=True)
    t.start()
    # messagebox.showinfo("Started", f"Bot started for: {window_info.get('title')}")

def _enum_windows():
    """Return list of tuples (hwnd, title) for visible top-level windows with non-empty titles."""
    results = []
    if not win32gui:
        return results

    def callback(hwnd, extra):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # filter out invisible/minimized/empty titles
            if title and title.strip():
                rect = win32gui.GetWindowRect(hwnd)
                # ignore windows with no area
                if rect[2] - rect[0] > 10 and rect[3] - rect[1] > 10:
                    results.append((hwnd, title, rect))
        return True

    win32gui.EnumWindows(callback, None)
    return results

def _capture_thumbnail(rect, max_size=(320, 200)):
    """Capture screen region (rect) and return a PIL Image resized to fit max_size."""
    if ImageGrab is None:
        return None
    left, top, right, bottom = rect
    try:
        img = ImageGrab.grab(bbox=(left, top, right, bottom))
    except Exception:
        return None
    img.thumbnail(max_size, Image.LANCZOS)
    return img

def list_windows():
    """
    Return a list of window info dicts:
      {'handle': hwnd, 'title': title, 'rect': (l,t,r,b), 'thumbnail': PhotoImage or None}
    """
    windows = []
    raw = _enum_windows()
    for hwnd, title, rect in raw:
        thumb_img = None
        if Image is not None and ImageTk is not None:
            pil = _capture_thumbnail(rect)
            if pil is not None:
                thumb_img = ImageTk.PhotoImage(pil)
        windows.append({"handle": hwnd, "title": title, "rect": rect, "thumbnail": thumb_img})
    return windows

def create_window_selection_interface():
    root = tk.Tk()
    root.title("梦幻西游 Automator")

    windows = list_windows()
    if not windows:
        messagebox.showerror("No windows", "Cannot find any visible windows. Is pywin32 and pillow installed?")
        root.destroy()
        return

    selected = {"info": None}
    thumbs_refs = []  # keep references to PhotoImage objects

    frm = ttk.Frame(root, padding=8)
    frm.pack(fill=tk.BOTH, expand=True)

    lbl = ttk.Label(frm, text="Click a window preview to select it:")
    lbl.pack(anchor=tk.W)

    canvas = tk.Canvas(frm)
    scrollbar = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)

    scroll_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set, height=400)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def on_preview_click(idx):
        info = windows[idx]
        selected["info"] = info
        # highlight selection visually (simple)
        for child in preview_items:
            child.config(relief=tk.RAISED)
        preview_items[idx].config(relief=tk.SUNKEN)

    preview_items = []
    for i, w in enumerate(windows):
        frame = ttk.Frame(scroll_frame, borderwidth=2, relief=tk.RAISED, padding=4)
        frame.pack(fill=tk.X, pady=4, padx=4)

        if w["thumbnail"] is not None:
            lbl_img = ttk.Label(frame, image=w["thumbnail"])
            lbl_img.image = w["thumbnail"]  # keep reference
            thumbs_refs.append(w["thumbnail"])
            lbl_img.pack(side=tk.LEFT)
            lbl_img.bind("<Button-1>", lambda e, idx=i: on_preview_click(idx))
        else:
            # placeholder if no thumbnail available
            lbl_img = ttk.Label(frame, text="[no preview]", width=40)
            lbl_img.pack(side=tk.LEFT)
            lbl_img.bind("<Button-1>", lambda e, idx=i: on_preview_click(idx))

        lbl_text = ttk.Label(frame, text=f"{w['title']}\nHandle: {w['handle']}\nRect: {w['rect']}", justify=tk.LEFT)
        lbl_text.pack(side=tk.LEFT, padx=8)
        lbl_text.bind("<Button-1>", lambda e, idx=i: on_preview_click(idx))

        preview_items.append(frame)

    btn_frame = ttk.Frame(root, padding=8)
    btn_frame.pack(fill=tk.X)

    def start_selected():
        info = selected.get("info")
        if not info:
            messagebox.showwarning("No selection", "Please click a window preview to select it first.")
            return
        on_window_select(info)

    ttk.Button(btn_frame, text="Start", command=start_selected).pack(side=tk.LEFT)
    ttk.Button(btn_frame, text="Refresh", command=lambda: (root.destroy(), create_window_selection_interface())).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_frame, text="Exit", command=root.quit).pack(side=tk.RIGHT)

    root.mainloop()

if __name__ == "__main__":
    create_window_selection_interface()
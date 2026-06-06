# scripts/diag_pywinauto_win32.py
from pywinauto import Desktop
wins = Desktop(backend="win32").windows()
print("Win32 top-level windows:", len(wins))
for w in wins:
    print(repr(w.window_text()))
# try find by regex (adjust pattern as needed)
try:
    w = Desktop(backend="win32").window(title_re=".*梦幻西游.*", visible_only=True)
    print("Found (win32):", w)
    w.print_control_identifiers()
except Exception as e:
    print("Not found with win32 backend:", e)
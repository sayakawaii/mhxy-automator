import sys, os, time, ctypes
sys.path.insert(0, r'e:\Documents\Project\Python\mhxy-automator\src')

# Check admin
if not ctypes.windll.shell32.IsUserAnAdmin():
    print('NOT ADMIN - may not work')

from run_tasks import find_game_window
from bot.vision import Vision
from bot.tasks import match_template

win = find_game_window()
print(f'Window rect: {win[\"rect\"]}')

vis = Vision(window_info=win)
hwnd = win['handle']
scale = 1.5  # 144 DPI / 96

import win32gui, win32con
win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
win32gui.SetForegroundWindow(hwnd)
time.sleep(1.0)  # wait for game to come to front

img = vis.capture_window()
print(f'Before click - capture size: {img.size}')

# Find X button
import os
tpl = r'e:\Documents\Project\Python\mhxy-automator\src\img\ClosePanel_X2.png'
box = match_template(img, tpl, threshold=0.40)
print(f'ClosePanel_X2 box: {box}')

if box:
    l,t,r,b = box
    x_img = (l+r)//2
    y_img = (t+b)//2
    rect = win['rect']
    trans_x = x_img + rect[0]
    trans_y = y_img + rect[1]
    lx = int(trans_x / scale)
    ly = int(trans_y / scale)
    print(f'Image center: ({x_img},{y_img}), Physical: ({trans_x},{trans_y}), Logical: ({lx},{ly})')
    
    # Method 1: pyautogui
    import pyautogui
    print(f'pyautogui clicking at logical ({lx},{ly})')
    pyautogui.click(lx, ly)
    time.sleep(2.0)
    
    img2 = vis.capture_window()
    img2.save(r'e:\Documents\Project\Python\mhxy-automator\src\img\debug_captures\diag_after_click.png')
    box2 = match_template(img2, tpl, threshold=0.40)
    print(f'After click - ClosePanel_X2: {box2}')
    if box2:
        print('PANEL STILL OPEN - click did not work!')
    else:
        print('PANEL CLOSED - click worked!')
else:
    print('X button not found')

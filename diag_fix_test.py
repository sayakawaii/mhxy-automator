import sys, os, time
sys.path.insert(0, r"e:\Documents\Project\Python\mhxy-automator\src")
log_path = r"e:\Documents\Project\Python\mhxy-automator\diag_fix_log.txt"

def log(msg):
    print(msg)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

try:
    from run_tasks import find_game_window
    from bot.vision import Vision
    from bot.tasks import match_template, TaskRunner
    from bot.actions import Actions

    win = find_game_window()
    if not win:
        log("NO GAME WINDOW FOUND")
        sys.exit(1)

    log(f"Window rect: {win['rect']}")
    vis = Vision(window_info=win)
    runner = TaskRunner(vision=vis, actions=Actions())

    img = vis.capture_window()
    log(f"Before click - capture size: {img.size}")

    tpl = r"e:\Documents\Project\Python\mhxy-automator\src\img\ClosePanel_X2.png"
    box = match_template(img, tpl, threshold=0.40)
    log(f"ClosePanel_X2 box: {box}")

    if box:
        rect = win["rect"]
        l,t,r,b = box
        x_img = (l+r)//2
        y_img = (t+b)//2
        trans_x = x_img + rect[0]
        trans_y = y_img + rect[1]
        log(f"Will click physical ({trans_x},{trans_y})")
        
        runner._click_box_center(box)
        
        time.sleep(2.0)
        img2 = vis.capture_window()
        img2.save(r"e:\Documents\Project\Python\mhxy-automator\src\img\debug_captures\diag_after_fix.png")
        box2 = match_template(img2, tpl, threshold=0.40)
        log(f"After click - ClosePanel_X2: {box2}")
        if box2:
            log("PANEL STILL OPEN")
        else:
            log("PANEL CLOSED - CLICK WORKED!")
    else:
        log("X button not found")
except Exception as ex:
    with open(log_path, "a", encoding="utf-8") as f:
        import traceback
        f.write(f"ERROR: {ex}\n{traceback.format_exc()}\n")

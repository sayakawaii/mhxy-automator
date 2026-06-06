import subprocess, sys, os, time

LOG_PATH = r"e:\Documents\Project\Python\mhxy-automator\run_test_log.txt"

result = subprocess.run(
    [r"e:\Documents\Project\Python\mhxy-automator\venv\Scripts\python.exe",
     r"e:\Documents\Project\Python\mhxy-automator\src\run_tasks.py", "--baotu"],
    cwd=r"e:\Documents\Project\Python\mhxy-automator",
    capture_output=True, text=True, timeout=90
)
with open(LOG_PATH, "w", encoding="utf-8") as f:
    f.write(f"exit={result.returncode}\n=STDOUT=\n{result.stdout}\n=STDERR=\n{result.stderr}")
print(f"Wrote to {LOG_PATH}, exit={result.returncode}")

from datetime import datetime
import time
import threading

class Scheduler:
    def __init__(self):
        self.tasks = []

    def add_task(self, task, delay):
        execution_time = datetime.now().timestamp() + delay
        self.tasks.append((execution_time, task))
        self.tasks.sort(key=lambda x: x[0])

    def run(self):
        while True:
            current_time = datetime.now().timestamp()
            while self.tasks and self.tasks[0][0] <= current_time:
                _, task = self.tasks.pop(0)
                threading.Thread(target=task).start()
            time.sleep(1)

scheduler = Scheduler()
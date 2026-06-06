from pynput.mouse import Controller as MouseController, Button as MouseButton
from pynput.keyboard import Controller as KeyboardController, Key
import time

class InputControl:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()

    def click(self, x, y):
        self.mouse.position = (x, y)
        self.mouse.click(MouseButton.left)

    def double_click(self, x, y):
        self.mouse.position = (x, y)
        self.mouse.click(MouseButton.left)
        time.sleep(0.1)
        self.mouse.click(MouseButton.left)

    def right_click(self, x, y):
        self.mouse.position = (x, y)
        self.mouse.click(MouseButton.right)

    def type(self, text):
        self.keyboard.type(text)

    def press_key(self, key):
        self.keyboard.press(key)
        self.keyboard.release(key)

    def press_and_hold_key(self, key, duration):
        self.keyboard.press(key)
        time.sleep(duration)
        self.keyboard.release(key)

    def move_mouse(self, x_offset, y_offset):
        current_position = self.mouse.position
        self.mouse.position = (current_position[0] + x_offset, current_position[1] + y_offset)
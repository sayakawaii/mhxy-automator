from typing import Optional, Tuple, List
from .actions import Actions
from utils.logger import Logger
import time

LOG = Logger(__name__)

class Navigation:
    """
    High-level navigation methods built on Actions.
    Navigation receives an Actions instance (for clicks/drags).
    """
    def __init__(self, actions: Optional[Actions] = None):
        self.actions = actions or Actions()

    def move_to(self, x: int, y: int):
        """
        Move by clicking at coordinates to simulate a tap/move.
        Games may require different gestures; adapt here.
        """
        LOG.info(f"move_to {x},{y}")
        self.actions.click_mouse(x, y)

    def interact_with_object(self, image, object_name: str) -> bool:
        """
        Try to find object_name on the provided image and click its center.
        Returns True if interaction was attempted.
        """
        LOG.info(f"interact_with_object: searching for {object_name}")
        coords = self.actions.get_coordinates_from_text(image, object_name)
        if not coords:
            LOG.debug("No coordinates found for object")
            return False
        # click the first found
        cx, cy = coords[0]
        self.actions.click_mouse(cx, cy)
        time.sleep(0.2)
        return True

    def navigate_to(self, destination: Tuple[int, int]):
        """
        Destination is an (x,y) tuple in screen coordinates.
        """
        LOG.info(f"navigate_to {destination}")
        self.move_to(destination[0], destination[1])

    def avoid_obstacles(self):
        """
        Placeholder for obstacle avoidance; real implementation needs vision feedback.
        """
        LOG.debug("avoid_obstacles called (no-op)")

    def follow_path(self, path: List[Tuple[int, int]]):
        """
        Follow a list of coordinates sequentially.
        """
        LOG.info(f"follow_path with {len(path)} points")
        for x, y in path:
            self.move_to(x, y)
            time.sleep(0.3)
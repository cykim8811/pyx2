
from typing import Any

class PyXContext:
    def __init__(self):
        self.user: Any = None
        self.request: Any = None
        self.app: Any = None


current = PyXContext()

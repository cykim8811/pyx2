
from pyx2 import createElement, current

class Display:
    def __init__(self):
        self.value = 0
    
    def __render__(self):
        return createElement("h1", {}, f"Count: {200 + self.value}"),
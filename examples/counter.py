

from pyx2 import createElement, current

import display

import watcher

class Counter:
    def __init__(self):
        self.count = 0
        self.display = display.Display()
        watcher.watcher.target.append((display, self.display))

    def increment(self):
        self.count += 1
        self.display.value = self.count
        current.app.rerender(self)
        current.app.rerender(self.display)

    def decrement(self):
        self.count -= 1
        self.display.value = self.count
        current.app.rerender(self)
        current.app.rerender(self.display)

    def __render__(self):
        return createElement("div", {},
            self.display,
            createElement("button", {"onClick": self.increment}, "+"),
            createElement("button", {"onClick": self.decrement}, "-"),
        )

root = Counter()

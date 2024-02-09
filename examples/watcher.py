
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from typing import Any

class Watcher(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self.target = []
        self.runner: Any = None

    def on_modified(self, event: FileSystemEvent) -> None:
        modified_path = os.path.abspath(event.src_path)
        for watcher in self.target:
            if watcher[0].__file__ == modified_path:
                self.runner.rerender_target.append(watcher)
            

observer = Observer()
watcher = Watcher()
observer.schedule(watcher, path='.')
observer.start()

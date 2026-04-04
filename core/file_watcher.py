"""File watcher for hot-reloading wildcard files.

Uses watchdog if available, falls back to polling (5-second interval).
Thread-safe. No ComfyUI dependencies.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

from .types import WildcardIndex
from .wildcard_index import build_index, reload_file

logger = logging.getLogger("PromptAlchemy")

POLL_INTERVAL = 5.0  # seconds
WILDCARD_EXTENSIONS = {".txt", ".yaml", ".yml"}


class WildcardWatcher:
    """Watches wildcard directories and keeps a WildcardIndex up to date."""

    def __init__(self, directories: list[str], index: WildcardIndex) -> None:
        self.directories = [str(Path(d).resolve()) for d in directories if Path(d).is_dir()]
        self.index = index
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._observer = None  # watchdog observer, if available

    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            return

        self._running = True

        if self._try_start_watchdog():
            logger.info("Wildcard hot-reload: using watchdog file watcher")
        else:
            logger.info("Wildcard hot-reload: using polling (every %.0fs)", POLL_INTERVAL)
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="PA-WildcardPoller"
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None
        self._thread = None

    def _try_start_watchdog(self) -> bool:
        """Try to start watchdog-based file watching. Returns True on success."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent

            watcher = self

            class _Handler(FileSystemEventHandler):
                def on_any_event(self, event: FileSystemEvent) -> None:
                    if event.is_directory:
                        return
                    src = Path(event.src_path)
                    if src.suffix.lower() not in WILDCARD_EXTENSIONS:
                        return
                    watcher._on_file_changed(src)

            observer = Observer()
            for d in self.directories:
                observer.schedule(_Handler(), d, recursive=True)
            observer.daemon = True
            observer.start()
            self._observer = observer
            return True
        except ImportError:
            return False
        except Exception as e:
            logger.warning("Failed to start watchdog: %s, falling back to polling", e)
            return False

    def _poll_loop(self) -> None:
        """Polling fallback: scan for modified files every POLL_INTERVAL seconds."""
        # Build initial snapshot of modification times
        snapshots: dict[str, dict[str, float]] = {}
        for d in self.directories:
            snapshots[d] = self._scan_mtimes(d)

        while self._running:
            time.sleep(POLL_INTERVAL)
            if not self._running:
                break

            for d in self.directories:
                new_snap = self._scan_mtimes(d)
                old_snap = snapshots.get(d, {})

                # Check for new or modified files
                for filepath, mtime in new_snap.items():
                    if filepath not in old_snap or old_snap[filepath] != mtime:
                        self._on_file_changed(Path(filepath))

                # Check for deleted files
                for filepath in old_snap:
                    if filepath not in new_snap:
                        self._on_file_changed(Path(filepath))

                snapshots[d] = new_snap

    def _scan_mtimes(self, directory: str) -> dict[str, float]:
        """Scan a directory tree and return {filepath: mtime} for wildcard files."""
        result: dict[str, float] = {}
        try:
            for root, _dirs, files in os.walk(directory):
                for f in files:
                    if Path(f).suffix.lower() in WILDCARD_EXTENSIONS:
                        full = os.path.join(root, f)
                        try:
                            result[full] = os.path.getmtime(full)
                        except OSError:
                            pass
        except OSError:
            pass
        return result

    def _on_file_changed(self, filepath: Path) -> None:
        """Handle a file change event."""
        # Find which base directory this file belongs to
        resolved = filepath.resolve()
        for d in self.directories:
            base = Path(d)
            try:
                resolved.relative_to(base)
            except ValueError:
                continue

            with self._lock:
                reload_file(self.index, resolved, base)
            return

        logger.debug("Changed file not in any watched directory: %s", filepath)


def create_watched_index(directories: list[str]) -> tuple[WildcardIndex, WildcardWatcher]:
    """Build a WildcardIndex and start watching the directories for changes.

    Returns (index, watcher). Caller should call watcher.stop() on cleanup.
    """
    valid_dirs = [d for d in directories if Path(d).is_dir()]
    index = build_index(valid_dirs)
    watcher = WildcardWatcher(valid_dirs, index)
    watcher.start()
    return index, watcher

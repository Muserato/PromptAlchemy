"""Tests for the file watcher and hot-reload functionality."""

import time
import pytest
from pathlib import Path

from core.file_watcher import WildcardWatcher, create_watched_index
from core.wildcard_index import build_index
from core.types import WildcardIndex


class TestWatcherIndexUpdate:
    def test_initial_build(self, tmp_path):
        (tmp_path / "colors.txt").write_text("red\nblue\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            assert "colors" in index
            assert len(index.get("colors").entries) == 2
        finally:
            watcher.stop()

    def test_file_add_detected_by_reload(self, tmp_path):
        """Test that manually calling reload_file updates the index."""
        (tmp_path / "colors.txt").write_text("red\nblue\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            assert "animals" not in index

            # Simulate adding a file and manually triggering reload
            (tmp_path / "animals.txt").write_text("cat\ndog\n")
            from core.wildcard_index import reload_file
            reload_file(index, tmp_path / "animals.txt", tmp_path)

            assert "animals" in index
            assert len(index.get("animals").entries) == 2
        finally:
            watcher.stop()

    def test_file_modify_detected_by_reload(self, tmp_path):
        """Test that reloading a modified file updates entries."""
        f = tmp_path / "items.txt"
        f.write_text("apple\nbanana\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            assert len(index.get("items").entries) == 2

            # Modify the file and reload
            f.write_text("apple\nbanana\ncherry\n")
            from core.wildcard_index import reload_file
            reload_file(index, f, tmp_path)

            assert len(index.get("items").entries) == 3
        finally:
            watcher.stop()

    def test_file_delete_detected_by_reload(self, tmp_path):
        """Test that reloading a deleted file removes it from the index."""
        f = tmp_path / "items.txt"
        f.write_text("apple\nbanana\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            assert "items" in index

            f.unlink()
            from core.wildcard_index import reload_file
            reload_file(index, f, tmp_path)

            assert "items" not in index
        finally:
            watcher.stop()

    def test_subdirectory_files(self, tmp_path):
        sub = tmp_path / "category"
        sub.mkdir()
        (sub / "things.txt").write_text("x\ny\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            assert "category/things" in index
        finally:
            watcher.stop()


class TestWatcherPolling:
    def test_scan_mtimes(self, tmp_path):
        (tmp_path / "a.txt").write_text("hello")
        (tmp_path / "b.yaml").write_text("entries:\n  - x\n")
        (tmp_path / "c.py").write_text("not a wildcard")

        watcher = WildcardWatcher([str(tmp_path)], WildcardIndex())
        mtimes = watcher._scan_mtimes(str(tmp_path))

        # Should find .txt and .yaml but not .py
        paths = [Path(p).name for p in mtimes]
        assert "a.txt" in paths
        assert "b.yaml" in paths
        assert "c.py" not in paths

    def test_empty_directory(self, tmp_path):
        watcher = WildcardWatcher([str(tmp_path)], WildcardIndex())
        mtimes = watcher._scan_mtimes(str(tmp_path))
        assert len(mtimes) == 0


class TestWatcherLifecycle:
    def test_start_stop(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello\n")
        index, watcher = create_watched_index([str(tmp_path)])
        assert watcher._running
        watcher.stop()
        assert not watcher._running

    def test_double_start(self, tmp_path):
        (tmp_path / "test.txt").write_text("hello\n")
        index, watcher = create_watched_index([str(tmp_path)])
        try:
            watcher.start()  # Should be a no-op
            assert watcher._running
        finally:
            watcher.stop()

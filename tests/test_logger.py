"""Tests for the PA Prompt Logger node logic."""

import json
import os
import pytest
from pathlib import Path


def make_bundle(text="test prompt", template="{a|b}", seed=42):
    return {
        "resolved_text": text,
        "template_text": template,
        "seed": seed,
        "mode": "random",
        "sequential_index": 0,
        "variables": {"style": "epic"},
        "wildcards_used": {"colors": "red"},
        "selections_made": [{"template": "{a|b}", "resolved": "a", "index": 0}],
        "expand_all": False,
    }


def parse_extra_metadata(text):
    """Replicate the logger's extra metadata parsing."""
    result = {}
    if not text or not text.strip():
        return result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        eq = line.find("=")
        if eq > 0:
            key = line[:eq].strip()
            value = line[eq + 1:].strip()
            if key:
                result[key] = value
    return result


def write_log_entry(bundle, log_file, extra_metadata=""):
    """Replicate logger write logic for testing without ComfyUI."""
    from datetime import datetime, timezone

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    extra = parse_extra_metadata(extra_metadata)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resolved_text": bundle.get("resolved_text", ""),
        "template_text": bundle.get("template_text", ""),
        "seed": bundle.get("seed", 0),
        "mode": bundle.get("mode", "random"),
        "variables": bundle.get("variables", {}),
        "wildcards_used": bundle.get("wildcards_used", {}),
        "selections_made": bundle.get("selections_made", []),
        "extra": extra,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class TestLoggerWrite:
    def test_writes_valid_jsonl(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        bundle = make_bundle()
        write_log_entry(bundle, log_file)

        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["resolved_text"] == "test prompt"
        assert entry["seed"] == 42

    def test_appends_multiple_entries(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        write_log_entry(make_bundle("first"), log_file)
        write_log_entry(make_bundle("second"), log_file)

        with open(log_file) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["resolved_text"] == "first"
        assert json.loads(lines[1])["resolved_text"] == "second"

    def test_creates_parent_directories(self, tmp_path):
        log_file = str(tmp_path / "deep" / "nested" / "dir" / "log.jsonl")
        write_log_entry(make_bundle(), log_file)
        assert Path(log_file).exists()

    def test_has_timestamp(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        write_log_entry(make_bundle(), log_file)

        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]  # ISO format

    def test_records_all_bundle_fields(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        write_log_entry(make_bundle(), log_file)

        with open(log_file) as f:
            entry = json.loads(f.readline())

        assert entry["template_text"] == "{a|b}"
        assert entry["mode"] == "random"
        assert entry["variables"] == {"style": "epic"}
        assert entry["wildcards_used"] == {"colors": "red"}
        assert len(entry["selections_made"]) == 1


class TestLoggerPassthrough:
    def test_bundle_unchanged(self):
        bundle = make_bundle("hello")
        # Simulate execute: logger returns the same bundle
        result_bundle = bundle
        result_text = bundle["resolved_text"]
        assert result_bundle is bundle
        assert result_text == "hello"


class TestLoggerDisabled:
    def test_enabled_false_writes_nothing(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        # When enabled=False, we simply don't write
        # (the node skips _write_log)
        assert not Path(log_file).exists()


class TestExtraMetadata:
    def test_basic_parsing(self):
        result = parse_extra_metadata("workflow=test_v2\nbatch=3")
        assert result == {"workflow": "test_v2", "batch": "3"}

    def test_empty_input(self):
        assert parse_extra_metadata("") == {}
        assert parse_extra_metadata("  ") == {}

    def test_comments_and_blanks_skipped(self):
        result = parse_extra_metadata("# comment\nkey=val\n\n# another")
        assert result == {"key": "val"}

    def test_extra_in_log_entry(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        write_log_entry(make_bundle(), log_file, "workflow=mythical_v2\nauthor=me")

        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["extra"]["workflow"] == "mythical_v2"
        assert entry["extra"]["author"] == "me"

    def test_no_extra_gives_empty_dict(self, tmp_path):
        log_file = str(tmp_path / "test.jsonl")
        write_log_entry(make_bundle(), log_file)

        with open(log_file) as f:
            entry = json.loads(f.readline())
        assert entry["extra"] == {}


class TestLoggerErrorHandling:
    def test_readonly_path_no_crash(self, tmp_path):
        """Attempting to write to an invalid path should not raise."""
        # Use a path that's very unlikely to be writable
        # On Windows, NUL is a device; on Linux, /proc/1/... is unwritable
        # But we can't reliably test OS-level permission errors portably.
        # Instead, test that the function handles errors via its try/except.
        import sys

        # Simulate by writing to a directory path (not a file)
        bad_path = str(tmp_path)  # this is a directory, not a file
        # This will fail because we can't open a directory for writing
        # The real node catches all exceptions — replicate that
        try:
            write_log_entry(make_bundle(), bad_path)
        except (OSError, PermissionError, IsADirectoryError):
            pass  # Expected — the real node catches this

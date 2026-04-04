"""Tests for pre-release fixes: empty entries, text cleanup, and batch size."""

import pytest
from core.resolver import resolve, resolve_bundle, cleanup_resolved_text
from core.wildcard_index import build_index
from core.types import WildcardIndex, WildcardFile, WildcardEntry


# ---------------------------------------------------------------------------
# Fix 1: Empty YAML entries
# ---------------------------------------------------------------------------

class TestEmptyYamlEntries:
    def test_yaml_bare_dash_is_empty_string(self, tmp_path):
        """A bare '- ' in YAML (None) should produce an empty string entry."""
        (tmp_path / "items.yaml").write_text("""
items:
  things:
    - red
    -
    - blue
""")
        idx = build_index([str(tmp_path)])
        entries = idx.get("items/things").entries
        assert len(entries) == 3
        assert entries[0].value == "red"
        assert entries[1].value == ""
        assert entries[2].value == "blue"

    def test_yaml_quoted_empty_string(self, tmp_path):
        """'- ""' in YAML should produce an empty string entry."""
        (tmp_path / "items.yaml").write_text("""
items:
  things:
    - red
    - ""
    - blue
""")
        idx = build_index([str(tmp_path)])
        entries = idx.get("items/things").entries
        assert entries[1].value == ""
        assert entries[1].weight == 1.0

    def test_empty_entry_not_none_string(self, tmp_path):
        """Empty entry must never produce the string 'None' or 'none'."""
        (tmp_path / "items.yaml").write_text("""
items:
  things:
    -
    - ""
""")
        idx = build_index([str(tmp_path)])
        for entry in idx.get("items/things").entries:
            assert entry.value != "None"
            assert entry.value != "none"
            assert entry.value == ""

    def test_flat_format_bare_dash(self, tmp_path):
        """Bare dash in flat entries format should also be empty string."""
        (tmp_path / "items.yaml").write_text("""
entries:
  - red
  -
  - blue
""")
        idx = build_index([str(tmp_path)])
        entries = idx.get("items").entries
        assert entries[1].value == ""

    def test_empty_entry_in_resolved_output(self, tmp_path):
        """When an empty entry is picked, it should be empty, not 'none'."""
        (tmp_path / "items.yaml").write_text("""
items:
  x:
    -
""")
        idx = build_index([str(tmp_path)])
        result = resolve("__items/x__", seed=42, wildcard_index=idx)
        assert result != "None"
        assert result != "none"


# ---------------------------------------------------------------------------
# Fix 2: Text cleanup
# ---------------------------------------------------------------------------

class TestCleanupResolvedText:
    def test_cleanup_double_comma(self):
        assert cleanup_resolved_text("a warrior, , dramatic lighting") == "a warrior, dramatic lighting"

    def test_cleanup_triple_comma(self):
        assert cleanup_resolved_text("a, , , b") == "a, b"

    def test_cleanup_leading_comma(self):
        assert cleanup_resolved_text(", dramatic lighting") == "dramatic lighting"

    def test_cleanup_trailing_comma(self):
        assert cleanup_resolved_text("a warrior,") == "a warrior"

    def test_cleanup_trailing_comma_with_space(self):
        assert cleanup_resolved_text("a warrior, ") == "a warrior"

    def test_cleanup_multiple_spaces(self):
        assert cleanup_resolved_text("a warrior  in  lighting") == "a warrior in lighting"

    def test_cleanup_preserves_normal_text(self):
        assert cleanup_resolved_text("a warrior, dramatic lighting, 8k") == "a warrior, dramatic lighting, 8k"

    def test_cleanup_empty_string(self):
        assert cleanup_resolved_text("") == ""

    def test_cleanup_only_commas(self):
        assert cleanup_resolved_text(", , ,") == ""

    def test_integrated_empty_wildcard_cleanup(self, tmp_path):
        """Template with empty wildcard should not leave double commas."""
        (tmp_path / "items.yaml").write_text("""
items:
  x:
    -
""")
        idx = build_index([str(tmp_path)])
        result = resolve("a warrior, __items/x__, dramatic lighting", seed=42, wildcard_index=idx)
        assert ",," not in result
        assert ", ," not in result
        assert result in ["a warrior, dramatic lighting", "a warrior,dramatic lighting"]


# ---------------------------------------------------------------------------
# Fix 3: Batch size
# ---------------------------------------------------------------------------

class TestBatchSize:
    """Test batch behavior via resolve_bundle (core engine).
    The node's OUTPUT_IS_LIST mechanism is a ComfyUI integration detail."""

    def test_single_resolution(self):
        """batch_size=1 equivalent: single resolve still works."""
        bundle = resolve_bundle("{red|blue|green}", seed=42)
        assert bundle.resolved_text in ["red", "blue", "green"]

    def test_multiple_seeds_different_output(self):
        """Different seeds should produce different results (for batch)."""
        results = set()
        for i in range(10):
            r = resolve("{red|blue|green}", seed=42 + i)
            results.add(r)
        assert len(results) > 1

    def test_sequential_advances_per_item(self):
        """Sequential mode should produce different results per index."""
        r0 = resolve("{a|b|c}", mode="sequential", sequential_index=0)
        r1 = resolve("{a|b|c}", mode="sequential", sequential_index=1)
        r2 = resolve("{a|b|c}", mode="sequential", sequential_index=2)
        assert r0 == "a"
        assert r1 == "b"
        assert r2 == "c"

    def test_batch_produces_list_via_node(self):
        """Simulate what the node does: resolve N times with incrementing seeds."""
        template = "{red|blue|green}"
        seed = 42
        batch_size = 5
        texts = []
        for i in range(batch_size):
            r = resolve(template, seed=seed + i)
            texts.append(r)
        assert len(texts) == 5
        assert all(t in ["red", "blue", "green"] for t in texts)
        # With 5 different seeds, should get at least 2 different results
        assert len(set(texts)) >= 2

    def test_batch_sequential_advances_counter(self):
        """In sequential mode, batch should advance through options."""
        template = "{a|b|c|d|e}"
        texts = []
        for i in range(5):
            r = resolve(template, mode="sequential", sequential_index=i)
            texts.append(r)
        assert texts == ["a", "b", "c", "d", "e"]

"""Tests for wildcard file loading and indexing."""

import pytest
from pathlib import Path

from core.wildcard_index import build_index, load_txt_file, load_yaml_file
from core.types import WildcardIndex


# ---------------------------------------------------------------------------
# .txt loading (unchanged)
# ---------------------------------------------------------------------------

class TestTxtLoading:
    def test_load_txt(self, tmp_path):
        f = tmp_path / "colors.txt"
        f.write_text("# comment\nred\nblue\n\ngreen\n")
        wf = load_txt_file(f)
        assert wf.name == "colors"
        assert len(wf.entries) == 3
        assert wf.entries[0].value == "red"
        assert wf.entries[1].value == "blue"
        assert wf.entries[2].value == "green"
        assert all(e.weight == 1.0 for e in wf.entries)


# ---------------------------------------------------------------------------
# Flat YAML (original format — must still work)
# ---------------------------------------------------------------------------

class TestYamlFlat:
    def test_load_yaml(self, tmp_path):
        f = tmp_path / "test.yaml"
        f.write_text("""
name: Test Entries
tags: [test, example]
entries:
  - alpha
  - bravo
  - value: charlie
    weight: 2.0
  - value: delta
    weight: 0.5
""")
        wf = load_yaml_file(f)
        assert wf is not None
        assert wf.name == "Test Entries"
        assert "test" in wf.tags
        assert len(wf.entries) == 4
        assert wf.entries[0].value == "alpha"
        assert wf.entries[0].weight == 1.0
        assert wf.entries[2].value == "charlie"
        assert wf.entries[2].weight == 2.0
        assert wf.entries[3].weight == 0.5

    def test_flat_format_in_index(self, tmp_path):
        (tmp_path / "items.yaml").write_text("""
name: Items
entries:
  - sword
  - shield
""")
        idx = build_index([str(tmp_path)])
        assert "items" in idx
        wf = idx.get("items")
        assert len(wf.entries) == 2

    def test_flat_with_inline_weights(self, tmp_path):
        (tmp_path / "items.yaml").write_text("""
entries:
  - 1.5::rare item
  - common item
  - 0.3::ultra rare
""")
        idx = build_index([str(tmp_path)])
        wf = idx.get("items")
        assert wf.entries[0].value == "rare item"
        assert wf.entries[0].weight == 1.5
        assert wf.entries[1].value == "common item"
        assert wf.entries[1].weight == 1.0
        assert wf.entries[2].value == "ultra rare"
        assert wf.entries[2].weight == 0.3


# ---------------------------------------------------------------------------
# Nested YAML categories
# ---------------------------------------------------------------------------

class TestYamlNested:
    def test_nested_yaml_categories(self, tmp_path):
        (tmp_path / "colors.yaml").write_text("""
colors:
  warm:
    - deep crimson
    - burnt amber
  cool:
    - sapphire blue
    - ice blue
""")
        idx = build_index([str(tmp_path)])
        assert "colors/warm" in idx
        assert "colors/cool" in idx
        assert len(idx.get("colors/warm").entries) == 2
        assert len(idx.get("colors/cool").entries) == 2

    def test_nested_yaml_flattened_parent(self, tmp_path):
        (tmp_path / "colors.yaml").write_text("""
colors:
  warm:
    - deep crimson
    - burnt amber
  cool:
    - sapphire blue
""")
        idx = build_index([str(tmp_path)])
        # Parent key should have all entries flattened
        assert "colors" in idx
        parent = idx.get("colors")
        assert len(parent.entries) == 3
        values = {e.value for e in parent.entries}
        assert "deep crimson" in values
        assert "sapphire blue" in values

    def test_nested_yaml_glob(self, tmp_path):
        (tmp_path / "colors.yaml").write_text("""
colors:
  warm:
    - red
  cool:
    - blue
  jewel:
    - emerald
""")
        idx = build_index([str(tmp_path)])
        keys = idx.glob("colors/*")
        assert len(keys) == 3
        assert "colors/warm" in keys
        assert "colors/cool" in keys
        assert "colors/jewel" in keys
        # Parent "colors" should NOT be in glob results
        assert "colors" not in keys

    def test_deep_nesting(self, tmp_path):
        (tmp_path / "artists.yaml").write_text("""
artists:
  finnish:
    - name1
    - name2
  dutch:
    - name3
""")
        idx = build_index([str(tmp_path)])
        assert "artists/finnish" in idx
        assert "artists/dutch" in idx
        assert "artists" in idx
        assert idx.get("artists/finnish").entries[0].value == "name1"

    def test_subfolder_nested_yaml(self, tmp_path):
        """Nested YAML in a subdirectory: characters/mythological.yaml"""
        chars = tmp_path / "characters"
        chars.mkdir()
        (chars / "mythological.yaml").write_text("""
mythological:
  greek:
    - Zeus
    - Apollo
  norse:
    - Thor
    - Odin
""")
        idx = build_index([str(tmp_path)])
        assert "characters/mythological/greek" in idx
        assert "characters/mythological/norse" in idx
        assert "characters/mythological" in idx
        greek = idx.get("characters/mythological/greek")
        assert greek.entries[0].value == "Zeus"
        # Parent should have all 4 entries
        parent = idx.get("characters/mythological")
        assert len(parent.entries) == 4


# ---------------------------------------------------------------------------
# Inline weight syntax
# ---------------------------------------------------------------------------

class TestInlineWeights:
    def test_inline_weight_syntax(self, tmp_path):
        (tmp_path / "items.yaml").write_text("""
items:
  gear:
    - 1.5::copper gold
    - sword
    - 0.3::diamond
""")
        idx = build_index([str(tmp_path)])
        entries = idx.get("items/gear").entries
        assert entries[0].value == "copper gold"
        assert entries[0].weight == 1.5
        assert entries[1].value == "sword"
        assert entries[1].weight == 1.0
        assert entries[2].value == "diamond"
        assert entries[2].weight == 0.3

    def test_inline_weight_default(self, tmp_path):
        (tmp_path / "x.yaml").write_text("""
x:
  a:
    - deep crimson
""")
        idx = build_index([str(tmp_path)])
        assert idx.get("x/a").entries[0].weight == 1.0

    def test_empty_string_entry(self, tmp_path):
        (tmp_path / "x.yaml").write_text("""
x:
  a:
    - red
    - ""
    - blue
""")
        idx = build_index([str(tmp_path)])
        entries = idx.get("x/a").entries
        assert len(entries) == 3
        assert entries[1].value == ""
        assert entries[1].weight == 1.0

    def test_object_weight_still_works(self, tmp_path):
        (tmp_path / "items.yaml").write_text("""
entries:
  - value: Hephaestus
    weight: 0.5
  - value: Zeus
    weight: 1.5
""")
        idx = build_index([str(tmp_path)])
        wf = idx.get("items")
        assert wf.entries[0].value == "Hephaestus"
        assert wf.entries[0].weight == 0.5
        assert wf.entries[1].value == "Zeus"
        assert wf.entries[1].weight == 1.5

    def test_mixed_weight_formats(self, tmp_path):
        (tmp_path / "mix.yaml").write_text("""
entries:
  - plain text
  - 2.0::weighted inline
  - value: weighted object
    weight: 0.5
""")
        idx = build_index([str(tmp_path)])
        wf = idx.get("mix")
        assert wf.entries[0].value == "plain text"
        assert wf.entries[0].weight == 1.0
        assert wf.entries[1].value == "weighted inline"
        assert wf.entries[1].weight == 2.0
        assert wf.entries[2].value == "weighted object"
        assert wf.entries[2].weight == 0.5

    def test_value_containing_double_colon(self, tmp_path):
        """Only split on the FIRST :: — value can contain :: itself."""
        (tmp_path / "x.yaml").write_text("""
x:
  a:
    - 1.5::text::with::colons
""")
        idx = build_index([str(tmp_path)])
        e = idx.get("x/a").entries[0]
        assert e.value == "text::with::colons"
        assert e.weight == 1.5


# ---------------------------------------------------------------------------
# Glob with nested YAML
# ---------------------------------------------------------------------------

class TestGlobNested:
    def test_glob_direct_children_only(self, tmp_path):
        (tmp_path / "colors.yaml").write_text("""
colors:
  warm:
    - red
  cool:
    - blue
""")
        idx = build_index([str(tmp_path)])
        keys = idx.glob("colors/*")
        # Should get warm and cool, NOT the parent "colors"
        assert sorted(keys) == ["colors/cool", "colors/warm"]

    def test_glob_deep_star(self, tmp_path):
        """/** should match all descendants at any depth."""
        chars = tmp_path / "characters"
        chars.mkdir()
        (chars / "mythological.yaml").write_text("""
mythological:
  greek:
    - Zeus
  norse:
    - Thor
""")
        idx = build_index([str(tmp_path)])
        keys = idx.glob("characters/**")
        # Should find greek and norse (and mythological itself)
        assert "characters/mythological/greek" in keys
        assert "characters/mythological/norse" in keys


# ---------------------------------------------------------------------------
# Mid-path glob: path/**/suffix
# ---------------------------------------------------------------------------

class TestMidPathGlob:
    @pytest.fixture
    def deep_index(self, tmp_path):
        """Create a deeply nested YAML for mid-path glob tests."""
        (tmp_path / "colors.yaml").write_text("""
colors:
  reds:
    pastels:
      - blush pink
      - salmon
    vivid:
      - crimson
      - scarlet
  greens:
    pastels:
      - mint
      - sage
    vivid:
      - emerald
      - forest green
  blues:
    pastels:
      - powder blue
      - periwinkle
""")
        return build_index([str(tmp_path)])

    def test_mid_path_glob_matches_keys(self, deep_index):
        """colors/**/pastels should match all pastels subcategories."""
        keys = deep_index.glob("colors/**/pastels")
        assert "colors/reds/pastels" in keys
        assert "colors/greens/pastels" in keys
        assert "colors/blues/pastels" in keys
        assert len(keys) == 3

    def test_mid_path_glob_vivid(self, deep_index):
        """colors/**/vivid should match both vivid subcategories."""
        keys = deep_index.glob("colors/**/vivid")
        assert "colors/reds/vivid" in keys
        assert "colors/greens/vivid" in keys
        assert len(keys) == 2

    def test_mid_path_glob_no_match(self, deep_index):
        """colors/**/nonexistent should return empty list."""
        keys = deep_index.glob("colors/**/nonexistent")
        assert keys == []

    def test_mid_path_glob_single_level(self, tmp_path):
        """Mid-path glob should work even when suffix is one level deep."""
        (tmp_path / "items.yaml").write_text("""
items:
  pastels:
    - soft pink
""")
        idx = build_index([str(tmp_path)])
        keys = idx.glob("items/**/pastels")
        assert "items/pastels" in keys

    def test_mid_path_glob_pools_entries_in_resolver(self, deep_index):
        """Resolver should pool entries from all mid-path glob matches."""
        from core.resolver import resolve
        all_pastels = {"blush pink", "salmon", "mint", "sage", "powder blue", "periwinkle"}
        results = set()
        for seed in range(200):
            r = resolve("__colors/**/pastels__", seed=seed, wildcard_index=deep_index)
            results.add(r)
        # Should have drawn from all three pastels subcategories
        assert results.issubset(all_pastels)
        assert len(results) >= 3  # statistically should hit most of them

    def test_mid_path_glob_with_weights(self, tmp_path):
        """Weighted entries from multiple mid-path matches should all be respected."""
        (tmp_path / "things.yaml").write_text("""
things:
  a:
    special:
      - 9.0::common_a
      - 0.01::rare_a
  b:
    special:
      - 9.0::common_b
      - 0.01::rare_b
""")
        idx = build_index([str(tmp_path)])
        from core.resolver import resolve
        results = [resolve("__things/**/special__", seed=i, wildcard_index=idx) for i in range(500)]
        # Common entries should dominate
        assert results.count("common_a") + results.count("common_b") > 400

    def test_mid_path_glob_passthrough_on_no_match(self):
        """Unmatched mid-path glob should return raw wildcard text."""
        from core.resolver import resolve
        from core.types import WildcardIndex
        idx = WildcardIndex()
        result = resolve("__foo/**/bar__", seed=42, wildcard_index=idx)
        assert result == "__foo/**/bar__"


# ---------------------------------------------------------------------------
# Build index — .txt files unaffected
# ---------------------------------------------------------------------------

class TestBuildIndex:
    def test_build_from_directory(self, tmp_path):
        (tmp_path / "items.txt").write_text("red\nblue\n")
        animals = tmp_path / "animals"
        animals.mkdir()
        (animals / "mammals.txt").write_text("cat\ndog\n")

        idx = build_index([str(tmp_path)])
        assert "items" in idx
        assert "animals/mammals" in idx

    def test_nonexistent_directory(self):
        idx = build_index(["/nonexistent/path/12345"])
        assert len(idx) == 0

    def test_glob_txt_files(self, tmp_path):
        animals = tmp_path / "animals"
        animals.mkdir()
        (animals / "mammals.txt").write_text("cat\ndog\n")
        (animals / "birds.txt").write_text("eagle\nsparrow\n")

        idx = build_index([str(tmp_path)])
        keys = idx.glob("animals/*")
        assert len(keys) == 2
        assert "animals/mammals" in keys
        assert "animals/birds" in keys

    def test_mixed_txt_and_nested_yaml(self, tmp_path):
        """Both .txt and nested .yaml in same directory tree."""
        (tmp_path / "moods.txt").write_text("happy\nsad\n")
        (tmp_path / "colors.yaml").write_text("""
colors:
  warm:
    - red
  cool:
    - blue
""")
        idx = build_index([str(tmp_path)])
        assert "moods" in idx
        assert "colors/warm" in idx
        assert "colors/cool" in idx
        assert "colors" in idx

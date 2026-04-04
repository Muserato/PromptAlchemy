"""Tests for the PromptAlchemy resolver."""

import pytest
from core.resolver import resolve, resolve_bundle
from core.types import WildcardEntry, WildcardFile, WildcardIndex


class TestBasicSelection:
    def test_random_pick(self):
        result = resolve("{red|blue|green}", seed=42)
        assert result in ["red", "blue", "green"]

    def test_deterministic_seed(self):
        r1 = resolve("{red|blue|green}", seed=42)
        r2 = resolve("{red|blue|green}", seed=42)
        assert r1 == r2

    def test_different_seeds(self):
        results = set()
        for seed in range(100):
            results.add(resolve("{red|blue|green}", seed=seed))
        # With 100 seeds, should see all 3 options
        assert len(results) == 3

    def test_text_with_selection(self):
        result = resolve("a {red|blue} sky", seed=42)
        assert result in ["a red sky", "a blue sky"]


class TestMultiSelect:
    def test_pick_two(self):
        result = resolve("{2$$red|blue|green}", seed=42)
        parts = result.split(", ")
        assert len(parts) == 2
        for p in parts:
            assert p in ["red", "blue", "green"]

    def test_pick_range(self):
        result = resolve("{2-4$$red|blue|green|yellow|purple}", seed=42)
        parts = result.split(", ")
        assert 2 <= len(parts) <= 4

    def test_custom_separator(self):
        result = resolve("{2$$ and $$red|blue|green}", seed=42)
        assert " and " in result


class TestWeightedSelection:
    def test_weighted_bias(self):
        results = [resolve("{0.9::common|0.1::rare}", seed=i) for i in range(1000)]
        common_count = results.count("common")
        rare_count = results.count("rare")
        assert common_count > rare_count * 3


class TestNesting:
    def test_nested_selection(self):
        result = resolve("a {red|blue} {cat|dog}", seed=42)
        assert result.startswith("a ")
        words = result.split()
        assert len(words) == 3
        assert words[1] in ["red", "blue"]
        assert words[2] in ["cat", "dog"]

    def test_deep_nesting(self):
        result = resolve("{a {red|blue} thing|just {simple|plain}}", seed=42)
        assert isinstance(result, str)
        assert len(result) > 0


class TestWildcards:
    @pytest.fixture
    def wildcard_index(self):
        idx = WildcardIndex()
        idx.add("colors", WildcardFile(
            name="colors",
            entries=[
                WildcardEntry("red"),
                WildcardEntry("blue"),
                WildcardEntry("green"),
            ],
        ))
        idx.add("animals/mammals", WildcardFile(
            name="mammals",
            entries=[
                WildcardEntry("cat"),
                WildcardEntry("dog"),
            ],
        ))
        idx.add("animals/birds", WildcardFile(
            name="birds",
            entries=[
                WildcardEntry("eagle"),
                WildcardEntry("sparrow"),
            ],
        ))
        return idx

    def test_simple_wildcard(self, wildcard_index):
        result = resolve("__colors__", seed=42, wildcard_index=wildcard_index)
        assert result in ["red", "blue", "green"]

    def test_path_wildcard(self, wildcard_index):
        result = resolve("__animals/mammals__", seed=42, wildcard_index=wildcard_index)
        assert result in ["cat", "dog"]

    def test_glob_wildcard(self, wildcard_index):
        result = resolve("__animals/*__", seed=42, wildcard_index=wildcard_index)
        assert result in ["cat", "dog", "eagle", "sparrow"]

    def test_missing_wildcard_passthrough(self):
        result = resolve("__nonexistent__", seed=42)
        assert result == "__nonexistent__"

    def test_weighted_yaml_entries(self):
        idx = WildcardIndex()
        idx.add("weighted", WildcardFile(
            name="weighted",
            entries=[
                WildcardEntry("common", weight=9.0),
                WildcardEntry("rare", weight=1.0),
            ],
        ))
        results = [resolve("__weighted__", seed=i, wildcard_index=idx) for i in range(1000)]
        assert results.count("common") > results.count("rare") * 3


class TestVariables:
    def test_variable_ref(self):
        result = resolve("{$color} sky", variables={"color": "blue"}, seed=42)
        assert result == "blue sky"

    def test_missing_variable_passthrough(self):
        result = resolve("{$unknown} sky", seed=42)
        assert result == "{$unknown} sky"

    def test_variable_set(self):
        result = resolve("{$color=red}the sky is {$color}", seed=42)
        assert result == "the sky is red"

    def test_variable_with_template_value(self):
        result = resolve("{$color} sky", variables={"color": "{red|blue}"}, seed=42)
        assert result in ["red sky", "blue sky"]


class TestConditionals:
    def test_conditional_true(self):
        result = resolve(
            "{if $style==epic: dramatic lighting | calm glow}",
            variables={"style": "epic"}, seed=42,
        )
        assert result == "dramatic lighting"

    def test_conditional_false(self):
        result = resolve(
            "{if $style==epic: dramatic lighting | calm glow}",
            variables={"style": "soft"}, seed=42,
        )
        assert result == "calm glow"

    def test_conditional_neq(self):
        result = resolve(
            "{if $style!=photo: illustration, artwork}",
            variables={"style": "painting"}, seed=42,
        )
        assert result == "illustration, artwork"

    def test_conditional_neq_false(self):
        result = resolve(
            "{if $style!=photo: illustration | photograph}",
            variables={"style": "photo"}, seed=42,
        )
        assert result == "photograph"


class TestNumericRanges:
    def test_int_range(self):
        result = resolve("{steps:20-35}", seed=42)
        val = int(result)
        assert 20 <= val <= 35

    def test_float_range(self):
        result = resolve("{cfg:5.0-9.0}", seed=42)
        val = float(result)
        assert 5.0 <= val <= 9.0

    def test_float_range_with_step(self):
        result = resolve("{cfg:5.0-9.0:0.5}", seed=42)
        val = float(result)
        assert 5.0 <= val <= 9.0
        # Should be a multiple of 0.5
        assert abs(val * 2 - round(val * 2)) < 0.01

    def test_deterministic_range(self):
        r1 = resolve("{steps:20-35}", seed=42)
        r2 = resolve("{steps:20-35}", seed=42)
        assert r1 == r2


class TestSequentialMode:
    def test_sequential_selection(self):
        assert resolve("{a|b|c}", mode="sequential", sequential_index=0) == "a"
        assert resolve("{a|b|c}", mode="sequential", sequential_index=1) == "b"
        assert resolve("{a|b|c}", mode="sequential", sequential_index=2) == "c"

    def test_sequential_wraps(self):
        assert resolve("{a|b|c}", mode="sequential", sequential_index=3) == "a"
        assert resolve("{a|b|c}", mode="sequential", sequential_index=4) == "b"

    def test_sequential_wildcard(self):
        idx = WildcardIndex()
        idx.add("items", WildcardFile(
            name="items",
            entries=[WildcardEntry("x"), WildcardEntry("y"), WildcardEntry("z")],
        ))
        assert resolve("__items__", mode="sequential", sequential_index=0, wildcard_index=idx) == "x"
        assert resolve("__items__", mode="sequential", sequential_index=1, wildcard_index=idx) == "y"
        assert resolve("__items__", mode="sequential", sequential_index=2, wildcard_index=idx) == "z"
        assert resolve("__items__", mode="sequential", sequential_index=3, wildcard_index=idx) == "x"


class TestLoRASafety:
    def test_lora_passthrough(self):
        result = resolve("<lora:cool__model__v2:1.0>", seed=42)
        assert result == "<lora:cool__model__v2:1.0>"

    def test_lora_with_selection(self):
        result = resolve("{red|blue} <lora:test__model:1.0>", seed=42)
        assert "<lora:test__model:1.0>" in result
        # First part should be resolved
        assert result.split(" <lora")[0] in ["red", "blue"]


class TestComments:
    def test_line_comment_stripped(self):
        result = resolve("hello // this is a comment\nworld", seed=42)
        assert "comment" not in result
        assert "hello" in result
        assert "world" in result

    def test_block_comment_stripped(self):
        result = resolve("hello /* block */ world", seed=42)
        assert "block" not in result
        assert "hello" in result
        assert "world" in result


class TestEscapes:
    def test_escape_braces(self):
        result = resolve("\\{not a selection\\}", seed=42)
        assert result == "{not a selection}"

    def test_escape_underscores(self):
        result = resolve("\\_\\_not a wildcard\\_\\_", seed=42)
        assert "__not a wildcard__" in result


class TestPromptBundle:
    def test_bundle_structure(self):
        bundle = resolve_bundle("{red|blue}", seed=42)
        assert bundle.template_text == "{red|blue}"
        assert bundle.resolved_text in ["red", "blue"]
        assert bundle.seed == 42
        assert bundle.mode == "random"
        assert len(bundle.selections_made) == 1

    def test_bundle_variables_recorded(self):
        bundle = resolve_bundle("{$color} sky", seed=42, variables={"color": "blue"})
        assert bundle.variables["color"] == "blue"
        assert bundle.resolved_text == "blue sky"

    def test_bundle_to_dict(self):
        bundle = resolve_bundle("{red|blue}", seed=42)
        d = bundle.to_dict()
        assert "resolved_text" in d
        assert "template_text" in d
        assert "seed" in d
        assert "selections_made" in d


class TestExpandMarker:
    def test_bare_expand_produces_empty(self):
        result = resolve("{@expand}", seed=42)
        assert result == ""

    def test_expand_with_text_has_sentinels(self):
        from core.types import EXPAND_START, EXPAND_END
        result = resolve("{@expand: a warrior}", seed=42)
        assert EXPAND_START in result
        assert EXPAND_END in result
        assert "a warrior" in result

    def test_bare_expand_sets_flag(self):
        from core.resolver import resolve_bundle
        bundle = resolve_bundle("{@expand}", seed=42)
        assert bundle.expand_all is True

    def test_expand_with_text_no_flag(self):
        from core.resolver import resolve_bundle
        bundle = resolve_bundle("{@expand: something}", seed=42)
        assert bundle.expand_all is False


class TestRelativeWildcards:
    """Test context-aware relative wildcard key resolution."""

    def _build_index(self):
        """Build an index simulating a nested YAML file structure."""
        idx = WildcardIndex()
        # Simulate themes/fantasy.yaml with nested structure
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("dragon"), WildcardEntry("griffin")],
        ))
        idx.add("themes/fantasy/colors", WildcardFile(
            name="colors",
            entries=[WildcardEntry("mystic blue"), WildcardEntry("emerald")],
        ))
        idx.add("themes/fantasy/world/biomes", WildcardFile(
            name="biomes",
            entries=[WildcardEntry("enchanted forest"), WildcardEntry("crystal caves")],
        ))
        # A root-level "colors" that should NOT shadow the relative one
        # when the relative one exists
        idx.add("colors", WildcardFile(
            name="colors",
            entries=[WildcardEntry("red"), WildcardEntry("blue")],
        ))
        return idx

    def test_absolute_still_works(self):
        """Absolute paths resolve exactly as before."""
        idx = self._build_index()
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result in ["dragon", "griffin"]

    def test_absolute_takes_priority(self):
        """When a name matches an absolute key, use it (no relative fallback)."""
        idx = self._build_index()
        # "colors" exists at root, so absolute match wins
        result = resolve("__colors__", seed=42, wildcard_index=idx)
        assert result in ["red", "blue"]

    def test_relative_sibling_no_slash(self):
        """Entry in one key referencing a sibling by short name (no slash)."""
        idx = WildcardIndex()
        # No root "palette" exists — only themes/fantasy/palette
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __palette__ dragon")],
        ))
        idx.add("themes/fantasy/palette", WildcardFile(
            name="palette",
            entries=[WildcardEntry("golden")],
        ))
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result == "a golden dragon"

    def test_relative_sibling_with_slash(self):
        """Entry referencing a sibling sub-path (with slash) resolves relatively."""
        idx = WildcardIndex()
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __world/biomes__ dragon")],
        ))
        idx.add("themes/fantasy/world/biomes", WildcardFile(
            name="biomes",
            entries=[WildcardEntry("forest")],
        ))
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result == "a forest dragon"

    def test_relative_walks_up(self):
        """Relative resolution walks up the context path."""
        idx = WildcardIndex()
        idx.add("themes/fantasy/world/deep/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __palette__ beast")],
        ))
        # palette is two levels up from creatures
        idx.add("themes/fantasy/palette", WildcardFile(
            name="palette",
            entries=[WildcardEntry("silver")],
        ))
        result = resolve(
            "__themes/fantasy/world/deep/creatures__", seed=42, wildcard_index=idx
        )
        assert result == "a silver beast"

    def test_relative_falls_back_to_global(self):
        """If no relative match, global is used as last resort."""
        idx = WildcardIndex()
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __moods__ dragon")],
        ))
        idx.add("moods", WildcardFile(
            name="moods",
            entries=[WildcardEntry("fierce")],
        ))
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result == "a fierce dragon"

    def test_no_context_global_only(self):
        """Top-level template with no context resolves globally (backward compat)."""
        idx = self._build_index()
        result = resolve("__colors__", seed=42, wildcard_index=idx)
        assert result in ["red", "blue"]

    def test_context_propagates_through_nesting(self):
        """Context propagates through multiple levels of recursive resolution."""
        idx = WildcardIndex()
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __adjectives__ dragon")],
        ))
        idx.add("themes/fantasy/adjectives", WildcardFile(
            name="adjectives",
            entries=[WildcardEntry("__palette__ and fierce")],
        ))
        idx.add("themes/fantasy/palette", WildcardFile(
            name="palette",
            entries=[WildcardEntry("golden")],
        ))
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result == "a golden and fierce dragon"

    def test_missing_relative_passthrough(self):
        """Unresolved wildcard (neither absolute nor relative) passes through."""
        idx = WildcardIndex()
        idx.add("themes/fantasy/creatures", WildcardFile(
            name="creatures",
            entries=[WildcardEntry("a __nonexistent__ dragon")],
        ))
        result = resolve("__themes/fantasy/creatures__", seed=42, wildcard_index=idx)
        assert result == "a __nonexistent__ dragon"

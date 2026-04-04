"""Tests for the PA Prompt Combiner logic."""

import pytest
from core.types import PromptBundle, SelectionRecord


def make_bundle_dict(text: str, template: str = "", seed: int = 0,
                     variables: dict | None = None,
                     wildcards: dict | None = None,
                     selections: list | None = None) -> dict:
    """Create a bundle dict matching the format nodes produce."""
    return {
        "resolved_text": text,
        "template_text": template or text,
        "seed": seed,
        "mode": "random",
        "sequential_index": 0,
        "variables": variables or {},
        "wildcards_used": wildcards or {},
        "selections_made": selections or [],
    }


def combine_bundles(bundle_1: dict, separator: str,
                    bundle_2: dict | None = None,
                    bundle_3: dict | None = None) -> tuple[dict, str]:
    """Replicate PAPromptCombiner.execute logic for testing without ComfyUI."""
    bundles_raw = [bundle_1]
    if bundle_2 is not None:
        bundles_raw.append(bundle_2)
    if bundle_3 is not None:
        bundles_raw.append(bundle_3)

    texts = [b["resolved_text"] for b in bundles_raw if b.get("resolved_text")]
    combined_text = separator.join(texts)

    templates = [b["template_text"] for b in bundles_raw if b.get("template_text")]
    combined_template = separator.join(templates)

    merged_vars = {}
    merged_wildcards = {}
    merged_selections = []
    seeds = []

    for b in bundles_raw:
        merged_vars.update(b.get("variables", {}))
        merged_wildcards.update(b.get("wildcards_used", {}))
        merged_selections.extend(b.get("selections_made", []))
        seeds.append(b.get("seed", 0))

    result = {
        "resolved_text": combined_text,
        "template_text": combined_template,
        "seed": seeds[0] if seeds else 0,
        "mode": bundles_raw[0].get("mode", "random"),
        "sequential_index": bundles_raw[0].get("sequential_index", 0),
        "variables": merged_vars,
        "wildcards_used": merged_wildcards,
        "selections_made": merged_selections,
    }
    return result, combined_text


class TestCombinerBasic:
    def test_single_bundle(self):
        b1 = make_bundle_dict("hello world")
        result, text = combine_bundles(b1, ", ")
        assert text == "hello world"

    def test_two_bundles(self):
        b1 = make_bundle_dict("a warrior")
        b2 = make_bundle_dict("epic lighting")
        result, text = combine_bundles(b1, ", ", b2)
        assert text == "a warrior, epic lighting"

    def test_three_bundles(self):
        b1 = make_bundle_dict("subject")
        b2 = make_bundle_dict("style")
        b3 = make_bundle_dict("lighting")
        result, text = combine_bundles(b1, ", ", b2, b3)
        assert text == "subject, style, lighting"

    def test_custom_separator(self):
        b1 = make_bundle_dict("hello")
        b2 = make_bundle_dict("world")
        result, text = combine_bundles(b1, " AND ", b2)
        assert text == "hello AND world"

    def test_empty_separator(self):
        b1 = make_bundle_dict("hello")
        b2 = make_bundle_dict("world")
        result, text = combine_bundles(b1, "", b2)
        assert text == "helloworld"


class TestCombinerMetadata:
    def test_variables_merged(self):
        b1 = make_bundle_dict("a", variables={"style": "epic"})
        b2 = make_bundle_dict("b", variables={"mood": "dark"})
        result, _ = combine_bundles(b1, ", ", b2)
        assert result["variables"] == {"style": "epic", "mood": "dark"}

    def test_variables_override(self):
        b1 = make_bundle_dict("a", variables={"x": "1"})
        b2 = make_bundle_dict("b", variables={"x": "2"})
        result, _ = combine_bundles(b1, ", ", b2)
        # Later bundle overrides
        assert result["variables"]["x"] == "2"

    def test_wildcards_merged(self):
        b1 = make_bundle_dict("a", wildcards={"colors": "red"})
        b2 = make_bundle_dict("b", wildcards={"animals": "cat"})
        result, _ = combine_bundles(b1, ", ", b2)
        assert result["wildcards_used"] == {"colors": "red", "animals": "cat"}

    def test_selections_merged(self):
        s1 = [{"template": "{a|b}", "resolved": "a", "index": 0}]
        s2 = [{"template": "{x|y}", "resolved": "y", "index": 1}]
        b1 = make_bundle_dict("a", selections=s1)
        b2 = make_bundle_dict("b", selections=s2)
        result, _ = combine_bundles(b1, ", ", b2)
        assert len(result["selections_made"]) == 2

    def test_seed_from_first(self):
        b1 = make_bundle_dict("a", seed=42)
        b2 = make_bundle_dict("b", seed=99)
        result, _ = combine_bundles(b1, ", ", b2)
        assert result["seed"] == 42

    def test_template_text_combined(self):
        b1 = make_bundle_dict("resolved1", template="{a|b}")
        b2 = make_bundle_dict("resolved2", template="__colors__")
        result, _ = combine_bundles(b1, ", ", b2)
        assert result["template_text"] == "{a|b}, __colors__"


class TestCombinerEdgeCases:
    def test_empty_resolved_text(self):
        b1 = make_bundle_dict("")
        b2 = make_bundle_dict("hello")
        result, text = combine_bundles(b1, ", ", b2)
        assert text == "hello"

    def test_none_optional_bundles(self):
        b1 = make_bundle_dict("only one")
        result, text = combine_bundles(b1, ", ", None, None)
        assert text == "only one"

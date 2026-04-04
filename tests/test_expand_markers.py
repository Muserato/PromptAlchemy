"""Tests for {@expand} marker parsing, resolution, and sentinel handling."""

import pytest
from core.parser import parse_template, ExpandMarkerNode, TextNode, SelectionNode
from core.resolver import resolve, resolve_bundle
from core.types import EXPAND_START, EXPAND_END


class TestExpandParserTokenization:
    def test_expand_with_text(self):
        nodes = parse_template("{@expand: a warrior}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], ExpandMarkerNode)
        assert len(nodes[0].text_nodes) > 0
        # Inner text should be a TextNode
        assert isinstance(nodes[0].text_nodes[0], TextNode)
        assert nodes[0].text_nodes[0].text == "a warrior"

    def test_bare_expand(self):
        nodes = parse_template("{@expand}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], ExpandMarkerNode)
        assert nodes[0].text_nodes == []

    def test_expand_with_surrounding_text(self):
        nodes = parse_template("before {@expand: middle} after")
        assert len(nodes) == 3
        assert isinstance(nodes[0], TextNode)
        assert isinstance(nodes[1], ExpandMarkerNode)
        assert isinstance(nodes[2], TextNode)

    def test_multiple_expand_markers(self):
        nodes = parse_template("{@expand: first} and {@expand: second}")
        expand_nodes = [n for n in nodes if isinstance(n, ExpandMarkerNode)]
        assert len(expand_nodes) == 2


class TestExpandResolverSentinels:
    def test_expand_with_text_produces_sentinels(self):
        result = resolve("{@expand: a warrior}", seed=42)
        assert EXPAND_START in result
        assert EXPAND_END in result
        assert "a warrior" in result
        # Should be: EXPAND_START + "a warrior" + EXPAND_END
        expected = f"{EXPAND_START}a warrior{EXPAND_END}"
        assert result == expected

    def test_bare_expand_no_sentinels(self):
        result = resolve("{@expand}", seed=42)
        assert EXPAND_START not in result
        assert result == ""

    def test_bare_expand_sets_flag(self):
        bundle = resolve_bundle("{@expand}", seed=42)
        assert bundle.expand_all is True

    def test_expand_with_text_no_flag(self):
        bundle = resolve_bundle("{@expand: something}", seed=42)
        assert bundle.expand_all is False

    def test_sentinels_in_context(self):
        result = resolve("a warrior, {@expand: dramatic battle scene}, epic", seed=42)
        assert result.startswith("a warrior, ")
        assert result.endswith(", epic")
        assert EXPAND_START in result
        assert "dramatic battle scene" in result

    def test_multiple_sentinels(self):
        result = resolve("{@expand: first} and {@expand: second}", seed=42)
        # Should have two pairs of sentinels
        assert result.count(EXPAND_START) == 2
        assert result.count(EXPAND_END) == 2

    def test_expand_all_with_text_around(self):
        bundle = resolve_bundle("hello {@expand} world", seed=42)
        assert bundle.expand_all is True
        assert bundle.resolved_text == "hello world"


class TestExpandNestedInSelection:
    def test_expand_inside_selection(self):
        result = resolve("{epic|{@expand: calm scene}}", seed=42)
        # Depending on seed, might get "epic" or sentinel-wrapped "calm scene"
        assert isinstance(result, str)
        assert len(result) > 0

    def test_expand_with_variables(self):
        result = resolve(
            "{@expand: a {$style} scene}",
            variables={"style": "cinematic"}, seed=42,
        )
        assert "cinematic" in result
        assert EXPAND_START in result

    def test_expand_with_wildcard(self):
        from core.types import WildcardIndex, WildcardFile, WildcardEntry
        idx = WildcardIndex()
        idx.add("moods", WildcardFile(
            name="moods",
            entries=[WildcardEntry("dramatic"), WildcardEntry("serene")],
        ))
        result = resolve(
            "{@expand: a __moods__ landscape}",
            seed=42, wildcard_index=idx,
        )
        assert EXPAND_START in result
        assert EXPAND_END in result
        # Inner text should have resolved the wildcard
        inner = result.replace(EXPAND_START, "").replace(EXPAND_END, "")
        assert inner in ["a dramatic landscape", "a serene landscape"]


class TestSentinelStripping:
    def test_strip_for_clean_output(self):
        """Verify sentinels can be stripped to get clean text."""
        result = resolve("{@expand: warrior}", seed=42)
        clean = result.replace(EXPAND_START, "").replace(EXPAND_END, "")
        assert clean == "warrior"

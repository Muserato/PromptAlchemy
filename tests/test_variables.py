"""Tests for the PA Variables node logic."""

import pytest
import sys
import os

# Import the parsing logic directly to test without ComfyUI
# We test the same logic the node uses
from core.resolver import resolve


def parse_variables(text: str, upstream: dict | None = None) -> dict[str, str]:
    """Replicate PAVariables.execute logic for testing without ComfyUI imports."""
    result: dict[str, str] = {}
    if upstream is not None:
        result.update(upstream)

    if text.strip():
        for line_num, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            eq_pos = line.find("=")
            if eq_pos <= 0:
                continue
            key = line[:eq_pos].strip()
            value = line[eq_pos + 1:].strip()
            if key:
                result[key] = value

    return result


class TestVariablesParsing:
    def test_basic_parsing(self):
        text = "style=cinematic\ncharacter=warrior"
        result = parse_variables(text)
        assert result == {"style": "cinematic", "character": "warrior"}

    def test_empty_input(self):
        result = parse_variables("")
        assert result == {}

    def test_whitespace_only(self):
        result = parse_variables("   \n  \n  ")
        assert result == {}

    def test_comments_ignored(self):
        text = "# This is a comment\nstyle=epic\n# Another comment\nmood=dark"
        result = parse_variables(text)
        assert result == {"style": "epic", "mood": "dark"}

    def test_value_with_equals(self):
        text = "formula=a=b+c"
        result = parse_variables(text)
        assert result == {"formula": "a=b+c"}

    def test_whitespace_trimmed(self):
        text = "  style  =  cinematic  \n  mood  =  epic  "
        result = parse_variables(text)
        assert result == {"style": "cinematic", "mood": "epic"}

    def test_invalid_line_skipped(self):
        text = "style=epic\nthis has no equals\nmood=dark"
        result = parse_variables(text)
        assert result == {"style": "epic", "mood": "dark"}

    def test_blank_lines_skipped(self):
        text = "style=epic\n\n\nmood=dark\n\n"
        result = parse_variables(text)
        assert result == {"style": "epic", "mood": "dark"}


class TestVariablesMerging:
    def test_upstream_vars(self):
        upstream = {"style": "photo", "quality": "high"}
        text = "style=cinematic\nmood=epic"
        result = parse_variables(text, upstream)
        # Downstream overrides upstream
        assert result["style"] == "cinematic"
        assert result["quality"] == "high"
        assert result["mood"] == "epic"

    def test_upstream_only(self):
        upstream = {"a": "1", "b": "2"}
        result = parse_variables("", upstream)
        assert result == {"a": "1", "b": "2"}

    def test_no_upstream(self):
        result = parse_variables("x=1")
        assert result == {"x": "1"}


class TestVariablesInResolver:
    def test_variables_used_in_template(self):
        vars_dict = parse_variables("color=blue\nanimal=cat")
        result = resolve("{$color} {$animal}", variables=vars_dict, seed=42)
        assert result == "blue cat"

    def test_variable_in_conditional(self):
        vars_dict = parse_variables("style=epic")
        result = resolve(
            "{if $style==epic: dramatic | calm}",
            variables=vars_dict, seed=42,
        )
        assert result == "dramatic"

    def test_chained_variables(self):
        upstream = parse_variables("base=photo")
        downstream = parse_variables("style=cinematic\nbase=painting", upstream)
        result = resolve("{$base} in {$style}", variables=downstream, seed=42)
        assert result == "painting in cinematic"

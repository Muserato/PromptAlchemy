"""Tests for the PromptAlchemy parser."""

import pytest
from core.parser import (
    ConditionalNode,
    ExpandMarkerNode,
    NumericRangeNode,
    SelectionNode,
    TextNode,
    VariableRefNode,
    VariableSetNode,
    WildcardNode,
    parse_template,
)


class TestBasicText:
    def test_plain_text(self):
        nodes = parse_template("hello world")
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)
        assert nodes[0].text == "hello world"

    def test_empty(self):
        nodes = parse_template("")
        assert nodes == []


class TestSelections:
    def test_simple_selection(self):
        nodes = parse_template("{red|blue|green}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], SelectionNode)
        assert len(nodes[0].options) == 3

    def test_selection_with_text(self):
        nodes = parse_template("a {red|blue} sky")
        assert len(nodes) == 3
        assert isinstance(nodes[0], TextNode)
        assert isinstance(nodes[1], SelectionNode)
        assert isinstance(nodes[2], TextNode)

    def test_nested_selection(self):
        nodes = parse_template("{a {red|blue} thing|simple}")
        assert len(nodes) == 1
        sel = nodes[0]
        assert isinstance(sel, SelectionNode)
        assert len(sel.options) == 2
        # First option has nested nodes
        first_opt_nodes = sel.options[0].nodes
        assert any(isinstance(n, SelectionNode) for n in first_opt_nodes)

    def test_multiselect(self):
        nodes = parse_template("{2$$red|blue|green}")
        assert len(nodes) == 1
        sel = nodes[0]
        assert isinstance(sel, SelectionNode)
        assert sel.pick_min == 2
        assert sel.pick_max == 2

    def test_multiselect_range(self):
        nodes = parse_template("{2-4$$red|blue|green|yellow|purple}")
        sel = nodes[0]
        assert sel.pick_min == 2
        assert sel.pick_max == 4

    def test_multiselect_custom_separator(self):
        nodes = parse_template("{2$$ and $$red|blue|green}")
        sel = nodes[0]
        assert sel.pick_min == 2
        assert sel.separator == " and "

    def test_weighted_options(self):
        nodes = parse_template("{0.7::dramatic|0.3::soft}")
        sel = nodes[0]
        assert isinstance(sel, SelectionNode)
        assert sel.options[0].weight == 0.7
        assert sel.options[1].weight == 0.3


class TestWildcards:
    def test_simple_wildcard(self):
        nodes = parse_template("__colors__")
        assert len(nodes) == 1
        assert isinstance(nodes[0], WildcardNode)
        assert nodes[0].name == "colors"

    def test_path_wildcard(self):
        nodes = parse_template("__animals/mammals__")
        assert len(nodes) == 1
        assert isinstance(nodes[0], WildcardNode)
        assert nodes[0].name == "animals/mammals"

    def test_glob_wildcard(self):
        nodes = parse_template("__animals/*__")
        assert len(nodes) == 1
        assert isinstance(nodes[0], WildcardNode)
        assert nodes[0].name == "animals/*"

    def test_wildcard_in_text(self):
        nodes = parse_template("a __colors__ cat")
        assert len(nodes) == 3
        assert isinstance(nodes[1], WildcardNode)


class TestVariables:
    def test_variable_ref(self):
        nodes = parse_template("{$style}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], VariableRefNode)
        assert nodes[0].name == "style"

    def test_variable_set(self):
        nodes = parse_template("{$style=cinematic}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], VariableSetNode)
        assert nodes[0].name == "style"


class TestNumericRanges:
    def test_int_range(self):
        nodes = parse_template("{steps:20-35}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], NumericRangeNode)
        assert nodes[0].label == "steps"
        assert nodes[0].min_val == 20
        assert nodes[0].max_val == 35
        assert nodes[0].is_int is True

    def test_float_range(self):
        nodes = parse_template("{weight:0.8-1.3}")
        assert len(nodes) == 1
        node = nodes[0]
        assert isinstance(node, NumericRangeNode)
        assert node.min_val == 0.8
        assert node.max_val == 1.3
        assert node.is_int is False

    def test_float_range_with_step(self):
        nodes = parse_template("{cfg:5.0-9.0:0.5}")
        node = nodes[0]
        assert isinstance(node, NumericRangeNode)
        assert node.step == 0.5


class TestConditionals:
    def test_conditional_eq(self):
        nodes = parse_template("{if $style==cinematic: epic lighting | soft glow}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], ConditionalNode)
        assert nodes[0].var_name == "style"
        assert nodes[0].operator == "=="
        assert nodes[0].compare_value == "cinematic"

    def test_conditional_neq(self):
        nodes = parse_template("{if $style!=photo: illustration}")
        assert len(nodes) == 1
        cond = nodes[0]
        assert cond.operator == "!="


class TestExpandMarker:
    def test_expand_marker_empty(self):
        nodes = parse_template("{@expand}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], ExpandMarkerNode)
        assert nodes[0].text_nodes == []

    def test_expand_marker_with_text(self):
        nodes = parse_template("{@expand: a warrior}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], ExpandMarkerNode)
        assert len(nodes[0].text_nodes) > 0


class TestLoRASafety:
    def test_lora_passthrough(self):
        nodes = parse_template("<lora:cool__model__v2:1.0>")
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)
        assert nodes[0].text == "<lora:cool__model__v2:1.0>"

    def test_hypernet_passthrough(self):
        nodes = parse_template("<hypernet:my__net__v1:0.8>")
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)

    def test_lora_with_wildcards(self):
        nodes = parse_template("__colors__ <lora:my__model:1.0> __styles__")
        wildcards = [n for n in nodes if isinstance(n, WildcardNode)]
        assert len(wildcards) == 2
        lora_texts = [n for n in nodes if isinstance(n, TextNode) and "lora" in n.text]
        assert len(lora_texts) == 1


class TestEscapes:
    def test_escape_brace(self):
        nodes = parse_template("\\{not a selection\\}")
        assert len(nodes) == 1
        assert isinstance(nodes[0], TextNode)
        assert nodes[0].text == "{not a selection}"

    def test_escape_underscore(self):
        nodes = parse_template("\\_\\_not a wildcard\\_\\_")
        text = "".join(n.text for n in nodes if isinstance(n, TextNode))
        assert "__not a wildcard__" in text


class TestComments:
    def test_line_comment(self):
        nodes = parse_template("hello // comment\nworld")
        text = "".join(n.text for n in nodes if isinstance(n, TextNode))
        assert "comment" not in text
        assert "hello" in text
        assert "world" in text

    def test_block_comment(self):
        nodes = parse_template("hello /* block */ world")
        text = "".join(n.text for n in nodes if isinstance(n, TextNode))
        assert "block" not in text
        assert "hello" in text
        assert "world" in text

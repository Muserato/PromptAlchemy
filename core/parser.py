"""Recursive descent parser for PromptAlchemy template syntax.

Produces an AST (list of Node objects) from a template string.
No ComfyUI dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Union


# ---------------------------------------------------------------------------
# AST Node types
# ---------------------------------------------------------------------------

@dataclass
class TextNode:
    """Literal text."""
    text: str


@dataclass
class SelectionOption:
    """One option inside a {a|b|c} selection."""
    weight: float | None = None  # None means equal weight
    nodes: list[Node] = field(default_factory=list)


@dataclass
class SelectionNode:
    """A {a|b|c} selection group, possibly with multi-select and weights."""
    options: list[SelectionOption] = field(default_factory=list)
    pick_min: int = 1
    pick_max: int = 1
    separator: str = ", "
    raw: str = ""  # original template text for logging


@dataclass
class WildcardNode:
    """A __name__ wildcard reference."""
    name: str  # e.g. "animals/mammals" or "colors"
    raw: str = ""


@dataclass
class VariableRefNode:
    """A {$varname} variable reference."""
    name: str


@dataclass
class VariableSetNode:
    """A {$varname=value} inline variable assignment."""
    name: str
    value_nodes: list[Node] = field(default_factory=list)


@dataclass
class NumericRangeNode:
    """A {label:min-max} or {label:min-max:step} numeric range."""
    label: str
    min_val: float
    max_val: float
    step: float | None = None
    is_int: bool = False


@dataclass
class ConditionalNode:
    """A {if $var==val: true_branch | false_branch} conditional."""
    var_name: str
    operator: str  # "==" or "!="
    compare_value: str
    true_nodes: list[Node] = field(default_factory=list)
    false_nodes: list[Node] = field(default_factory=list)


@dataclass
class ExpandMarkerNode:
    """An {@expand} or {@expand: text} LLM expansion marker."""
    text_nodes: list[Node] = field(default_factory=list)  # empty = expand all


Node = Union[
    TextNode, SelectionNode, WildcardNode, VariableRefNode,
    VariableSetNode, NumericRangeNode, ConditionalNode, ExpandMarkerNode,
]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    """Non-fatal parse error — logged but doesn't crash."""
    pass


class Parser:
    """Recursive descent parser for PromptAlchemy templates."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0
        self.length = len(text)

    def parse(self) -> list[Node]:
        """Parse the full template and return an AST."""
        text = self._strip_comments(self.text)
        self.text = text
        self.length = len(text)
        self.pos = 0
        return self._parse_nodes(stop_chars="")

    def _strip_comments(self, text: str) -> str:
        """Remove // line comments and /* block comments */."""
        # Block comments: require at least one char between /* and */
        # so that /**/ (glob pattern) is not treated as an empty comment.
        result = re.sub(r'/\*.+?\*/', '', text, flags=re.DOTALL)
        # Line comments: // to end of line
        result = re.sub(r'//[^\n]*', '', result)
        return result

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx < self.length:
            return self.text[idx]
        return ""

    def _at_end(self) -> bool:
        return self.pos >= self.length

    def _advance(self, n: int = 1) -> str:
        result = self.text[self.pos:self.pos + n]
        self.pos += n
        return result

    def _parse_nodes(self, stop_chars: str = "") -> list[Node]:
        """Parse nodes until we hit a stop character or end of input."""
        nodes: list[Node] = []

        while not self._at_end():
            ch = self._peek()

            if ch in stop_chars:
                break

            if ch == '\\':
                nodes.append(self._parse_escape())
            elif ch == '{':
                nodes.append(self._parse_brace_group())
            elif ch == '_' and self._peek(1) == '_':
                node = self._try_parse_wildcard()
                if node is not None:
                    nodes.append(node)
                else:
                    nodes.append(TextNode(self._advance()))
            elif ch == '<' and self._is_lora_start():
                nodes.append(self._parse_lora_passthrough())
            else:
                nodes.append(self._parse_text(stop_chars))

        return self._merge_text_nodes(nodes)

    def _parse_text(self, stop_chars: str) -> TextNode:
        """Consume plain text until we hit a special character."""
        start = self.pos
        while not self._at_end():
            ch = self._peek()
            if ch in stop_chars or ch in '{\\':
                break
            if ch == '_' and self._peek(1) == '_':
                break
            if ch == '<' and self._is_lora_start():
                break
            self.pos += 1
        return TextNode(self.text[start:self.pos])

    def _parse_escape(self) -> TextNode:
        """Handle \\{, \\}, \\_ escape sequences."""
        self._advance()  # skip backslash
        if self._at_end():
            return TextNode("\\")
        ch = self._peek()
        if ch in '{}_':
            return TextNode(self._advance())
        return TextNode("\\" + self._advance())

    def _is_lora_start(self) -> bool:
        """Check if current position starts a <lora:...> or <hypernet:...> tag."""
        remaining = self.text[self.pos:]
        return remaining.startswith("<lora:") or remaining.startswith("<hypernet:")

    def _parse_lora_passthrough(self) -> TextNode:
        """Consume everything inside <lora:...> or <hypernet:...> as literal text."""
        start = self.pos
        while not self._at_end():
            if self._peek() == '>':
                self.pos += 1
                break
            self.pos += 1
        return TextNode(self.text[start:self.pos])

    def _try_parse_wildcard(self) -> WildcardNode | None:
        """Try to parse __name__ wildcard. Returns None if not a valid wildcard."""
        save_pos = self.pos
        self._advance(2)  # skip opening __

        name_start = self.pos
        while not self._at_end():
            if self._peek() == '_' and self._peek(1) == '_':
                name = self.text[name_start:self.pos]
                self._advance(2)  # skip closing __
                if name:
                    raw = f"__{name}__"
                    return WildcardNode(name=name, raw=raw)
                else:
                    # Empty ____  — not a wildcard
                    self.pos = save_pos
                    return None
            if self._peek() in '{}\n':
                # Not a valid wildcard
                self.pos = save_pos
                return None
            self.pos += 1

        # Reached end without closing __
        self.pos = save_pos
        return None

    def _parse_brace_group(self) -> Node:
        """Parse a {…} group — could be selection, variable, range, conditional, or expand."""
        save_pos = self.pos
        self._advance()  # skip {

        if self._at_end():
            return TextNode("{")

        # Check for variable: {$...}
        if self._peek() == '$':
            node = self._try_parse_variable()
            if node is not None:
                return node
            self.pos = save_pos + 1

        # Check for conditional: {if $var...}
        if self.text[self.pos:].startswith("if "):
            node = self._try_parse_conditional()
            if node is not None:
                return node
            self.pos = save_pos + 1

        # Check for expand marker: {@expand...}
        if self._peek() == '@':
            node = self._try_parse_expand()
            if node is not None:
                return node
            self.pos = save_pos + 1

        # Check for numeric range: {label:min-max} or {label:min-max:step}
        node = self._try_parse_numeric_range()
        if node is not None:
            return node
        self.pos = save_pos + 1

        # Default: selection {a|b|c} possibly with multi-select or weights
        return self._parse_selection(save_pos)

    def _try_parse_variable(self) -> VariableRefNode | VariableSetNode | None:
        """Try to parse {$name} or {$name=value}."""
        self._advance()  # skip $
        name_start = self.pos
        while not self._at_end() and self._peek() not in '=}':
            if self._peek() == '|':
                # This is likely a selection option starting with $, not a variable
                return None
            self.pos += 1

        if self._at_end():
            return None

        name = self.text[name_start:self.pos].strip()
        if not name:
            return None

        if self._peek() == '=':
            self._advance()  # skip =
            value_nodes = self._parse_nodes(stop_chars="}")
            if not self._at_end() and self._peek() == '}':
                self._advance()
            return VariableSetNode(name=name, value_nodes=value_nodes)

        if self._peek() == '}':
            self._advance()
            return VariableRefNode(name=name)

        return None

    def _try_parse_conditional(self) -> ConditionalNode | None:
        """Try to parse {if $var==val: true_branch | false_branch}."""
        save = self.pos
        self._advance(3)  # skip "if "

        # Skip whitespace
        while not self._at_end() and self._peek() == ' ':
            self._advance()

        if self._at_end() or self._peek() != '$':
            self.pos = save
            return None
        self._advance()  # skip $

        # Parse variable name
        name_start = self.pos
        while not self._at_end() and self._peek() not in '=!}':
            self.pos += 1
        var_name = self.text[name_start:self.pos].strip()

        # Parse operator
        if self.text[self.pos:self.pos + 2] == '==':
            operator = '=='
            self._advance(2)
        elif self.text[self.pos:self.pos + 2] == '!=':
            operator = '!='
            self._advance(2)
        else:
            self.pos = save
            return None

        # Parse compare value (until colon)
        val_start = self.pos
        while not self._at_end() and self._peek() != ':':
            self.pos += 1
        if self._at_end():
            self.pos = save
            return None
        compare_value = self.text[val_start:self.pos].strip()
        self._advance()  # skip :

        # Parse true branch (until | or })
        true_nodes = self._parse_nodes(stop_chars="|}")

        false_nodes: list[Node] = []
        if not self._at_end() and self._peek() == '|':
            self._advance()  # skip |
            false_nodes = self._parse_nodes(stop_chars="}")

        if not self._at_end() and self._peek() == '}':
            self._advance()

        # Strip leading/trailing whitespace from branches
        true_nodes = self._strip_whitespace_nodes(true_nodes)
        false_nodes = self._strip_whitespace_nodes(false_nodes)

        return ConditionalNode(
            var_name=var_name,
            operator=operator,
            compare_value=compare_value,
            true_nodes=true_nodes,
            false_nodes=false_nodes,
        )

    def _try_parse_expand(self) -> ExpandMarkerNode | None:
        """Try to parse {@expand} or {@expand: text}."""
        self._advance()  # skip @
        if not self.text[self.pos:].startswith("expand"):
            return None
        self._advance(6)  # skip "expand"

        if self._at_end():
            return None

        if self._peek() == '}':
            self._advance()
            return ExpandMarkerNode()

        if self._peek() == ':':
            self._advance()  # skip :
            # skip optional whitespace
            if not self._at_end() and self._peek() == ' ':
                self._advance()
            text_nodes = self._parse_nodes(stop_chars="}")
            if not self._at_end() and self._peek() == '}':
                self._advance()
            return ExpandMarkerNode(text_nodes=text_nodes)

        return None

    def _try_parse_numeric_range(self) -> NumericRangeNode | None:
        """Try to parse {label:min-max} or {label:min-max:step}."""
        save = self.pos

        # Scan ahead to find the closing brace and check the pattern
        scan = self.pos
        depth = 0
        while scan < self.length:
            if self.text[scan] == '{':
                depth += 1
            elif self.text[scan] == '}':
                if depth == 0:
                    break
                depth -= 1
            scan += 1

        if scan >= self.length:
            return None

        content = self.text[self.pos:scan]

        # Pattern: label:min-max or label:min-max:step
        # The min-max part requires a number, dash, number pattern
        match = re.match(
            r'^([a-zA-Z_]\w*):(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)(?::(-?\d+(?:\.\d+)?))?$',
            content
        )
        if not match:
            return None

        label = match.group(1)
        min_str = match.group(2)
        max_str = match.group(3)
        step_str = match.group(4)

        is_int = '.' not in min_str and '.' not in max_str
        min_val = float(min_str)
        max_val = float(max_str)
        step = float(step_str) if step_str else None

        self.pos = scan + 1  # skip past closing }
        return NumericRangeNode(
            label=label, min_val=min_val, max_val=max_val,
            step=step, is_int=is_int,
        )

    def _parse_selection(self, open_brace_pos: int) -> SelectionNode:
        """Parse a {a|b|c} selection, possibly with multi-select prefix and weights."""
        # Check for multi-select prefix: {N$$...} or {N-M$$...} or {N$$ sep $$...}
        pick_min = 1
        pick_max = 1
        separator = ", "

        multi_match = self._try_parse_multiselect_prefix()
        if multi_match:
            pick_min, pick_max, separator = multi_match

        # Parse options separated by |
        options: list[SelectionOption] = []
        current_option = self._parse_selection_option()
        options.append(current_option)

        while not self._at_end() and self._peek() == '|':
            self._advance()  # skip |
            current_option = self._parse_selection_option()
            options.append(current_option)

        if not self._at_end() and self._peek() == '}':
            self._advance()

        raw = self.text[open_brace_pos:self.pos]

        return SelectionNode(
            options=options,
            pick_min=pick_min,
            pick_max=pick_max,
            separator=separator,
            raw=raw,
        )

    def _try_parse_multiselect_prefix(self) -> tuple[int, int, str] | None:
        """Try to parse N$$ or N-M$$ or N$$ sep $$ prefix. Returns (min, max, sep) or None."""
        save = self.pos

        # Look ahead for $$ to determine if this is a multi-select
        scan = self.pos
        while scan < self.length and self.text[scan] not in '|}':
            if self.text[scan:scan + 2] == '$$':
                break
            scan += 1

        if scan >= self.length or self.text[scan:scan + 2] != '$$':
            return None

        prefix = self.text[self.pos:scan]

        # Try N or N-M
        count_match = re.match(r'^(\d+)(?:-(\d+))?$', prefix)
        if not count_match:
            return None

        pick_min = int(count_match.group(1))
        pick_max = int(count_match.group(2)) if count_match.group(2) else pick_min

        self.pos = scan + 2  # skip past $$
        separator = ", "

        # Check for custom separator: another $$ ahead
        scan2 = self.pos
        while scan2 < self.length and self.text[scan2] not in '|}':
            if self.text[scan2:scan2 + 2] == '$$':
                separator = self.text[self.pos:scan2]
                self.pos = scan2 + 2
                break
            scan2 += 1

        return (pick_min, pick_max, separator)

    def _parse_selection_option(self) -> SelectionOption:
        """Parse a single option, possibly with weight prefix (0.7::text)."""
        save = self.pos
        weight = None

        # Look ahead for weight prefix: float::
        weight_match = self._try_parse_weight_prefix()
        if weight_match is not None:
            weight = weight_match

        nodes = self._parse_nodes(stop_chars="|}")
        return SelectionOption(weight=weight, nodes=nodes)

    def _try_parse_weight_prefix(self) -> float | None:
        """Try to parse a weight:: prefix. Returns weight or None."""
        save = self.pos

        # Scan for :: pattern preceded by a number
        scan = self.pos
        while scan < self.length and self.text[scan] not in '|}':
            if self.text[scan:scan + 2] == '::':
                prefix = self.text[self.pos:scan]
                try:
                    weight = float(prefix)
                    self.pos = scan + 2
                    return weight
                except ValueError:
                    return None
            scan += 1

        return None

    def _strip_whitespace_nodes(self, nodes: list[Node]) -> list[Node]:
        """Strip leading and trailing whitespace from a list of nodes."""
        if not nodes:
            return nodes
        if isinstance(nodes[0], TextNode):
            nodes[0] = TextNode(nodes[0].text.lstrip())
        if isinstance(nodes[-1], TextNode):
            nodes[-1] = TextNode(nodes[-1].text.rstrip())
        return [n for n in nodes if not (isinstance(n, TextNode) and n.text == "")]

    def _merge_text_nodes(self, nodes: list[Node]) -> list[Node]:
        """Merge adjacent TextNode instances."""
        if not nodes:
            return nodes
        merged: list[Node] = []
        for node in nodes:
            if isinstance(node, TextNode) and merged and isinstance(merged[-1], TextNode):
                merged[-1] = TextNode(merged[-1].text + node.text)
            else:
                merged.append(node)
        return merged


def parse_template(text: str) -> list[Node]:
    """Parse a template string into an AST."""
    return Parser(text).parse()

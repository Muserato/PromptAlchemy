"""Template resolution engine for PromptAlchemy.

Walks the AST from parser.py and resolves all syntax elements.
No ComfyUI dependencies.
"""

from __future__ import annotations

import logging
import random
from dataclasses import field

from .parser import (
    ConditionalNode,
    ExpandMarkerNode,
    Node,
    NumericRangeNode,
    SelectionNode,
    TextNode,
    VariableRefNode,
    VariableSetNode,
    WildcardNode,
    parse_template,
)
from .types import (
    PA_VARIABLES, PromptBundle, SelectionRecord, WildcardIndex,
    EXPAND_START, EXPAND_END,
)

logger = logging.getLogger("PromptAlchemy")


class Resolver:
    """Resolves a parsed template AST into final text."""

    def __init__(
        self,
        seed: int = 0,
        mode: str = "random",
        sequential_index: int = 0,
        variables: dict[str, str] | None = None,
        wildcard_index: WildcardIndex | None = None,
    ) -> None:
        self.seed = seed
        self.mode = mode
        self.sequential_index = sequential_index
        self.variables = dict(variables) if variables else {}
        self.wildcard_index = wildcard_index or WildcardIndex()
        self.wildcards_used: dict[str, str] = {}
        self.selections_made: list[SelectionRecord] = []
        self.expand_all: bool = False
        self._rng = random.Random(seed)
        self._seq_counter = 0  # incremented for each sequential choice
        self._context_stack: list[str] = []

    def resolve_nodes(self, nodes: list[Node]) -> str:
        """Resolve a list of AST nodes into a string."""
        parts: list[str] = []
        for node in nodes:
            parts.append(self._resolve_node(node))
        return "".join(parts)

    def _resolve_node(self, node: Node) -> str:
        if isinstance(node, TextNode):
            return node.text
        elif isinstance(node, SelectionNode):
            return self._resolve_selection(node)
        elif isinstance(node, WildcardNode):
            return self._resolve_wildcard(node)
        elif isinstance(node, VariableRefNode):
            return self._resolve_variable_ref(node)
        elif isinstance(node, VariableSetNode):
            return self._resolve_variable_set(node)
        elif isinstance(node, NumericRangeNode):
            return self._resolve_numeric_range(node)
        elif isinstance(node, ConditionalNode):
            return self._resolve_conditional(node)
        elif isinstance(node, ExpandMarkerNode):
            return self._resolve_expand_marker(node)
        else:
            return ""

    def _resolve_selection(self, node: SelectionNode) -> str:
        options = node.options
        if not options:
            return ""

        pick_count = self._pick_count(node.pick_min, node.pick_max)
        pick_count = min(pick_count, len(options))

        if self.mode == "sequential":
            indices = []
            for _ in range(pick_count):
                idx = (self.sequential_index + self._seq_counter) % len(options)
                indices.append(idx)
                self._seq_counter += 1
        else:
            # Weighted random selection
            weights = []
            for opt in options:
                weights.append(opt.weight if opt.weight is not None else 1.0)

            if pick_count == 1:
                indices = [self._weighted_choice(weights)]
            else:
                indices = self._weighted_sample(weights, pick_count)

        results: list[str] = []
        for idx in indices:
            opt = options[idx]
            resolved = self.resolve_nodes(opt.nodes)
            results.append(resolved)
            self.selections_made.append(SelectionRecord(
                template=node.raw,
                resolved=resolved,
                index=idx,
            ))

        return node.separator.join(results)

    def _pick_count(self, pick_min: int, pick_max: int) -> int:
        if pick_min == pick_max:
            return pick_min
        if self.mode == "sequential":
            return pick_min
        return self._rng.randint(pick_min, pick_max)

    def _weighted_choice(self, weights: list[float]) -> int:
        """Pick one index based on weights."""
        total = sum(weights)
        if total <= 0:
            return self._rng.randint(0, len(weights) - 1)
        r = self._rng.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return i
        return len(weights) - 1

    def _weighted_sample(self, weights: list[float], k: int) -> list[int]:
        """Pick k unique indices based on weights (without replacement)."""
        available = list(range(len(weights)))
        avail_weights = list(weights)
        chosen: list[int] = []
        for _ in range(k):
            if not available:
                break
            total = sum(avail_weights)
            if total <= 0:
                idx_in_avail = self._rng.randint(0, len(available) - 1)
            else:
                r = self._rng.random() * total
                cumulative = 0.0
                idx_in_avail = len(available) - 1
                for i, w in enumerate(avail_weights):
                    cumulative += w
                    if r <= cumulative:
                        idx_in_avail = i
                        break
            chosen.append(available[idx_in_avail])
            available.pop(idx_in_avail)
            avail_weights.pop(idx_in_avail)
        return chosen

    def _resolve_key_with_context(self, name: str) -> str | None:
        """Resolve a wildcard name, trying absolute first then relative to context.

        1. Try name as-is (absolute) — preserves all existing behavior.
        2. If not found and context exists, walk up the context path trying
           prefix/name at each level.

        Glob patterns (containing '*') are always absolute.
        Returns the resolved key, or None if not found.
        """
        if "*" in name:
            return name if self.wildcard_index.get(name) is not None else None

        # Absolute lookup first
        if self.wildcard_index.get(name) is not None:
            return name

        # Relative: walk up context path
        if self._context_stack:
            context = self._context_stack[-1]
            parts = context.split("/")
            for i in range(len(parts), 0, -1):
                candidate = "/".join(parts[:i]) + "/" + name
                if self.wildcard_index.get(candidate) is not None:
                    return candidate

        return None

    def _resolve_wildcard(self, node: WildcardNode) -> str:
        name = node.name

        # Resolve any variables in the wildcard path
        # e.g. __animals/{$type}__ where $type is a variable
        if "{$" in name:
            # Quick inline resolution of variable references in the name
            import re
            def _replace_var(m: re.Match) -> str:
                var_name = m.group(1)
                return self.variables.get(var_name, m.group(0))
            name = re.sub(r'\{\$(\w+)\}', _replace_var, name)

        # Handle mid-path glob: __path/**/suffix__ — pool entries from all matches
        if "/**/" in name:
            keys = self.wildcard_index.glob(name)
            if not keys:
                logger.warning("No wildcard files match glob: %s", node.raw)
                return node.raw
            # Pool all entries from matching keys, tracking source key
            pooled: list[tuple[str, object]] = []
            for k in keys:
                match_wf = self.wildcard_index.get(k)
                if match_wf and match_wf.entries:
                    for e in match_wf.entries:
                        pooled.append((k, e))
            if not pooled:
                logger.warning("No entries in wildcard glob matches: %s", node.raw)
                return node.raw
            # Pick from pooled entries
            if self.mode == "sequential":
                idx = (self.sequential_index + self._seq_counter) % len(pooled)
                self._seq_counter += 1
                source_key, entry = pooled[idx]
            else:
                weights = [e.weight for _, e in pooled]
                idx = self._weighted_choice(weights)
                source_key, entry = pooled[idx]
            self.wildcards_used[name] = entry.value
            if any(ch in entry.value for ch in ['{', '__']):
                self._context_stack.append(source_key)
                try:
                    sub_ast = parse_template(entry.value)
                    return self.resolve_nodes(sub_ast)
                finally:
                    self._context_stack.pop()
            return entry.value

        # Handle end glob: __path/*__ or __path/**__
        if name.endswith("/**") or name.endswith("/*"):
            keys = self.wildcard_index.glob(name)
            if not keys:
                logger.warning("No wildcard files match glob: %s", node.raw)
                return node.raw
            if self.mode == "sequential":
                key = keys[(self.sequential_index + self._seq_counter) % len(keys)]
                self._seq_counter += 1
            else:
                key = self._rng.choice(keys)
            name = key

        resolved_key = self._resolve_key_with_context(name)
        wf = self.wildcard_index.get(resolved_key) if resolved_key else None
        if wf is None or not wf.entries:
            logger.warning("Wildcard not found: %s", node.raw)
            return node.raw

        # Pick an entry
        if self.mode == "sequential":
            idx = (self.sequential_index + self._seq_counter) % len(wf.entries)
            self._seq_counter += 1
            entry = wf.entries[idx]
        else:
            weights = [e.weight for e in wf.entries]
            idx = self._weighted_choice(weights)
            entry = wf.entries[idx]

        self.wildcards_used[resolved_key] = entry.value

        # The wildcard value might itself contain template syntax — resolve it
        if any(ch in entry.value for ch in ['{', '__']):
            self._context_stack.append(resolved_key)
            try:
                sub_ast = parse_template(entry.value)
                return self.resolve_nodes(sub_ast)
            finally:
                self._context_stack.pop()

        return entry.value

    def _resolve_variable_ref(self, node: VariableRefNode) -> str:
        value = self.variables.get(node.name)
        if value is None:
            logger.warning("Variable not found: $%s", node.name)
            return "{$" + node.name + "}"

        # The variable value might contain template syntax
        if any(ch in value for ch in ['{', '__']):
            sub_ast = parse_template(value)
            return self.resolve_nodes(sub_ast)

        return value

    def _resolve_variable_set(self, node: VariableSetNode) -> str:
        value = self.resolve_nodes(node.value_nodes)
        self.variables[node.name] = value
        return ""  # assignment produces no output

    def _resolve_numeric_range(self, node: NumericRangeNode) -> str:
        if self.mode == "sequential":
            # In sequential mode, step through the range
            if node.step:
                steps = []
                v = node.min_val
                while v <= node.max_val + 1e-9:
                    steps.append(v)
                    v += node.step
                if not steps:
                    steps = [node.min_val]
                idx = (self.sequential_index + self._seq_counter) % len(steps)
                self._seq_counter += 1
                val = steps[idx]
            elif node.is_int:
                count = int(node.max_val - node.min_val) + 1
                idx = (self.sequential_index + self._seq_counter) % count
                self._seq_counter += 1
                val = node.min_val + idx
            else:
                # For floats without step in sequential mode, just use min
                val = node.min_val
        else:
            if node.step:
                steps = []
                v = node.min_val
                while v <= node.max_val + 1e-9:
                    steps.append(v)
                    v += node.step
                if not steps:
                    steps = [node.min_val]
                val = self._rng.choice(steps)
            elif node.is_int:
                val = self._rng.randint(int(node.min_val), int(node.max_val))
            else:
                val = self._rng.uniform(node.min_val, node.max_val)

        if node.is_int:
            return str(int(val))
        elif node.step:
            # Match the decimal places of the step
            step_str = str(node.step)
            if '.' in step_str:
                decimals = len(step_str.split('.')[1])
            else:
                decimals = 1
            return f"{val:.{decimals}f}"
        else:
            return f"{val:.2f}"

    def _resolve_conditional(self, node: ConditionalNode) -> str:
        var_value = self.variables.get(node.var_name, "")

        if node.operator == "==":
            condition = (var_value == node.compare_value)
        elif node.operator == "!=":
            condition = (var_value != node.compare_value)
        else:
            condition = False

        if condition:
            return self.resolve_nodes(node.true_nodes)
        else:
            return self.resolve_nodes(node.false_nodes)

    def _resolve_expand_marker(self, node: ExpandMarkerNode) -> str:
        if node.text_nodes:
            # {@expand: text} — wrap resolved text in sentinel markers
            inner = self.resolve_nodes(node.text_nodes)
            return f"{EXPAND_START}{inner}{EXPAND_END}"
        else:
            # Bare {@expand} — flag entire prompt for expansion
            self.expand_all = True
            return ""


def cleanup_resolved_text(text: str) -> str:
    """Clean up punctuation artifacts from empty resolutions."""
    import re
    # Collapse multiple commas with optional whitespace: "a, , b" → "a, b"
    text = re.sub(r',(\s*,)+', ',', text)
    # Remove leading comma: ", dramatic lighting" → "dramatic lighting"
    text = re.sub(r'^\s*,\s*', '', text)
    # Remove trailing comma: "a warrior," → "a warrior"
    text = re.sub(r'\s*,\s*$', '', text)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def resolve(
    template: str,
    seed: int = 0,
    mode: str = "random",
    sequential_index: int = 0,
    variables: dict[str, str] | None = None,
    wildcard_index: WildcardIndex | None = None,
) -> str:
    """Convenience function: parse and resolve a template, return the resolved text."""
    ast = parse_template(template)
    resolver = Resolver(
        seed=seed,
        mode=mode,
        sequential_index=sequential_index,
        variables=variables,
        wildcard_index=wildcard_index,
    )
    return cleanup_resolved_text(resolver.resolve_nodes(ast))


def resolve_bundle(
    template: str,
    seed: int = 0,
    mode: str = "random",
    sequential_index: int = 0,
    variables: dict[str, str] | None = None,
    wildcard_index: WildcardIndex | None = None,
) -> PromptBundle:
    """Parse and resolve a template, return a full PromptBundle."""
    ast = parse_template(template)
    resolver = Resolver(
        seed=seed,
        mode=mode,
        sequential_index=sequential_index,
        variables=variables,
        wildcard_index=wildcard_index,
    )
    resolved_text = cleanup_resolved_text(resolver.resolve_nodes(ast))
    return PromptBundle(
        resolved_text=resolved_text,
        template_text=template,
        seed=seed,
        mode=mode,
        sequential_index=sequential_index,
        variables=dict(resolver.variables),
        wildcards_used=resolver.wildcards_used,
        selections_made=resolver.selections_made,
        expand_all=resolver.expand_all,
    )

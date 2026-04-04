"""Core types for PromptAlchemy engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Type alias for variables passed between nodes
PA_VARIABLES = dict[str, str]


@dataclass
class WildcardEntry:
    """A single entry in a wildcard file."""
    value: str
    weight: float = 1.0


@dataclass
class WildcardFile:
    """Parsed contents of a single wildcard file (.txt or .yaml)."""
    name: str  # display name (from yaml) or filename stem
    entries: list[WildcardEntry] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class WildcardIndex:
    """In-memory index mapping wildcard names to their entries."""

    def __init__(self) -> None:
        self._files: dict[str, WildcardFile] = {}

    def add(self, key: str, wf: WildcardFile) -> None:
        """Add or replace a wildcard file entry. Key uses forward-slash paths."""
        self._files[key] = wf

    def remove(self, key: str) -> None:
        self._files.pop(key, None)

    def get(self, key: str) -> WildcardFile | None:
        return self._files.get(key)

    def keys(self) -> list[str]:
        return sorted(self._files.keys())

    def glob(self, pattern: str) -> list[str]:
        """Return keys matching a glob-style pattern.

        Supports:
          - path/* → direct children only (one level deeper)
          - path/** → all descendants at any depth
          - path/**/suffix → keys ending with /suffix at any depth under path
        """
        # Mid-path **: path/**/suffix
        if "/**/" in pattern:
            prefix, _, suffix = pattern.partition("/**/")
            prefix_slash = prefix + "/"
            suffix_slash = "/" + suffix
            return sorted(k for k in self._files
                          if k.startswith(prefix_slash) and
                          (k.endswith(suffix_slash) or k == prefix + "/" + suffix
                           or k[len(prefix_slash):] == suffix))

        # Trailing **: path/**
        if pattern.endswith("/**"):
            prefix = pattern[:-2]  # "path/"
            return sorted(k for k in self._files
                          if k.startswith(prefix) and k != prefix.rstrip("/"))

        # Single *: path/*
        if pattern.endswith("/*"):
            prefix = pattern[:-1]  # "path/"
            return sorted(k for k in self._files
                          if k.startswith(prefix) and "/" not in k[len(prefix):])

        return [k for k in self._files if k == pattern]

    def __len__(self) -> int:
        return len(self._files)

    def __contains__(self, key: str) -> bool:
        return key in self._files


@dataclass
class SelectionRecord:
    """Records a single selection made during resolution."""
    template: str
    resolved: str
    index: int = 0


# Sentinel markers for {@expand: text} sections in resolved text.
# These are embedded by the resolver and consumed by the LLM Expander node.
EXPAND_START = "\x00PA_EXPAND_START\x00"
EXPAND_END = "\x00PA_EXPAND_END\x00"


@dataclass
class PromptBundle:
    """Structured output from prompt resolution."""
    resolved_text: str
    template_text: str
    seed: int = 0
    mode: str = "random"
    sequential_index: int = 0
    variables: dict[str, str] = field(default_factory=dict)
    wildcards_used: dict[str, str] = field(default_factory=dict)
    selections_made: list[SelectionRecord] = field(default_factory=list)
    expand_all: bool = False  # True if bare {@expand} was found

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved_text": self.resolved_text,
            "template_text": self.template_text,
            "seed": self.seed,
            "mode": self.mode,
            "sequential_index": self.sequential_index,
            "variables": dict(self.variables),
            "wildcards_used": dict(self.wildcards_used),
            "selections_made": [
                {"template": s.template, "resolved": s.resolved, "index": s.index}
                for s in self.selections_made
            ],
            "expand_all": self.expand_all,
        }

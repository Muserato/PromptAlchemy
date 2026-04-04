"""PA Prompt Template node for ComfyUI."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.resolver import resolve_bundle
from ..core.file_watcher import create_watched_index, WildcardWatcher
from ..core.types import WildcardIndex

logger = logging.getLogger("PromptAlchemy")

# Default wildcards directory: <this_extension>/wildcards/
_DEFAULT_WILDCARD_DIR = str(Path(__file__).parent.parent / "wildcards")

# Shared default index with file watching (built lazily)
_default_index: WildcardIndex | None = None
_default_watcher: WildcardWatcher | None = None


def _get_default_index() -> WildcardIndex:
    global _default_index, _default_watcher
    if _default_index is None:
        _default_index, _default_watcher = create_watched_index([_DEFAULT_WILDCARD_DIR])
        logger.info(
            "PA Prompt Template: default wildcard index built (%d files)",
            len(_default_index),
        )
    return _default_index


class PAPromptTemplate:
    """Core PromptAlchemy node: resolves prompt templates with wildcards,
    selections, variables, and more."""

    # Track sequential index per node instance id
    _sequential_indices: dict[str, int] = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "template": ("STRING", {"multiline": True, "default": ""}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "mode": (["random", "sequential"],),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 100}),
            },
            "optional": {
                "variables": ("PA_VARIABLES",),
                "wildcard_index": ("PA_WILDCARD_INDEX",),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("PROMPT_BUNDLE", "STRING", "INT")
    RETURN_NAMES = ("prompt_bundle", "resolved_text", "seed")
    OUTPUT_IS_LIST = (True, True, True)
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"

    @classmethod
    def IS_CHANGED(cls, mode, **kwargs):
        if mode == "sequential":
            return float("NaN")
        return kwargs.get("seed", 0)

    def execute(self, template, seed, mode, batch_size=1,
                variables=None, wildcard_index=None, unique_id=None):
        # Use provided wildcard index or build default (with file watching)
        wc_index = wildcard_index if wildcard_index is not None else _get_default_index()

        # Variables
        vars_dict = variables if variables is not None else {}

        # Sequential index tracking
        seq_index = 0
        if mode == "sequential" and unique_id is not None:
            node_key = str(unique_id)
            seq_index = self._sequential_indices.get(node_key, 0)
            self._sequential_indices[node_key] = seq_index + batch_size

        bundles = []
        texts = []
        seeds = []

        for i in range(batch_size):
            current_seed = seed + i if mode == "random" else seed
            current_seq = seq_index + i

            bundle = resolve_bundle(
                template=template,
                seed=current_seed,
                mode=mode,
                sequential_index=current_seq,
                variables=vars_dict,
                wildcard_index=wc_index,
            )
            bundles.append(bundle.to_dict())
            texts.append(bundle.resolved_text)
            seeds.append(current_seed)

        return (bundles, texts, seeds)

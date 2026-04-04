"""PA Prompt Combiner node for ComfyUI."""

from __future__ import annotations

from ..core.types import PromptBundle
from ..core.resolver import cleanup_resolved_text


def _bundle_from_dict(d: dict) -> PromptBundle:
    """Reconstruct a PromptBundle from its dict representation."""
    from ..core.types import SelectionRecord
    return PromptBundle(
        resolved_text=d.get("resolved_text", ""),
        template_text=d.get("template_text", ""),
        seed=d.get("seed", 0),
        mode=d.get("mode", "random"),
        sequential_index=d.get("sequential_index", 0),
        variables=dict(d.get("variables", {})),
        wildcards_used=dict(d.get("wildcards_used", {})),
        selections_made=[
            SelectionRecord(
                template=s.get("template", ""),
                resolved=s.get("resolved", ""),
                index=s.get("index", 0),
            )
            for s in d.get("selections_made", [])
        ],
    )


class PAPromptCombiner:
    """Joins multiple prompt bundles with a separator."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "bundle_1": ("PROMPT_BUNDLE",),
                "separator": ("STRING", {"default": ", ", "multiline": False}),
            },
            "optional": {
                "bundle_2": ("PROMPT_BUNDLE",),
                "bundle_3": ("PROMPT_BUNDLE",),
            },
        }

    RETURN_TYPES = ("PROMPT_BUNDLE", "STRING")
    RETURN_NAMES = ("prompt_bundle", "resolved_text")
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"

    def execute(self, bundle_1: dict, separator: str,
                bundle_2: dict | None = None, bundle_3: dict | None = None):
        bundles_raw = [bundle_1]
        if bundle_2 is not None:
            bundles_raw.append(bundle_2)
        if bundle_3 is not None:
            bundles_raw.append(bundle_3)

        bundles = [_bundle_from_dict(b) for b in bundles_raw]

        # Join resolved texts
        texts = [b.resolved_text for b in bundles if b.resolved_text]
        combined_text = separator.join(texts)

        # Join template texts
        templates = [b.template_text for b in bundles if b.template_text]
        combined_template = separator.join(templates)

        # Merge metadata
        merged_vars: dict[str, str] = {}
        merged_wildcards: dict[str, str] = {}
        merged_selections = []
        seeds = []

        for b in bundles:
            merged_vars.update(b.variables)
            merged_wildcards.update(b.wildcards_used)
            merged_selections.extend(b.selections_made)
            seeds.append(b.seed)

        combined = PromptBundle(
            resolved_text=combined_text,
            template_text=combined_template,
            seed=seeds[0] if seeds else 0,
            mode=bundles[0].mode if bundles else "random",
            sequential_index=bundles[0].sequential_index if bundles else 0,
            variables=merged_vars,
            wildcards_used=merged_wildcards,
            selections_made=merged_selections,
        )

        combined_text = cleanup_resolved_text(combined_text)
        combined.resolved_text = combined_text

        return (combined.to_dict(), combined_text)

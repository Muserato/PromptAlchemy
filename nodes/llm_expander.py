"""PA LLM Expander node for ComfyUI."""

from __future__ import annotations

import logging
import re

from ..core.llm_client import LLMClient
from ..core.types import EXPAND_START, EXPAND_END

logger = logging.getLogger("PromptAlchemy")

_DEFAULT_SYSTEM_PROMPT = (
    "You are an expert Stable Diffusion prompt engineer. Given a base prompt, enhance it "
    "with specific, vivid details that will improve image generation quality. Add relevant "
    "modifiers for lighting, composition, style, and detail. Keep the core subject unchanged. "
    "Output ONLY the enhanced prompt text, no explanations or formatting."
)

# Regex to find sentinel-wrapped expand sections
_EXPAND_PATTERN = re.compile(
    re.escape(EXPAND_START) + r"(.*?)" + re.escape(EXPAND_END),
    re.DOTALL,
)


def _strip_sentinels(text: str) -> str:
    """Remove all expand sentinel markers, returning plain text."""
    return text.replace(EXPAND_START, "").replace(EXPAND_END, "")


class PALLMExpander:
    """Sends prompt text (or marked sections) to an LLM for enhancement."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_bundle": ("PROMPT_BUNDLE",),
                "provider": (["ollama", "openai_compatible", "anthropic"],),
                "endpoint": ("STRING", {"default": "http://localhost:11434"}),
                "model": ("STRING", {"default": "llama3.2"}),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": _DEFAULT_SYSTEM_PROMPT,
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1,
                }),
                "expand_markers_only": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "api_key": ("STRING", {"default": ""}),
            },
        }

    RETURN_TYPES = ("PROMPT_BUNDLE", "STRING", "STRING")
    RETURN_NAMES = ("prompt_bundle", "resolved_text", "original_text")
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"

    def execute(
        self,
        prompt_bundle: dict,
        provider: str,
        endpoint: str,
        model: str,
        system_prompt: str,
        temperature: float,
        expand_markers_only: bool,
        api_key: str = "",
    ):
        resolved_text = prompt_bundle.get("resolved_text", "")
        expand_all = prompt_bundle.get("expand_all", False)

        # Save original (with sentinels stripped) for comparison output
        original_text = _strip_sentinels(resolved_text)

        client = LLMClient()

        if expand_markers_only and not expand_all:
            # Only expand {@expand: text} sections
            has_markers = bool(_EXPAND_PATTERN.search(resolved_text))

            if not has_markers:
                # No markers — pass through unchanged
                logger.info(
                    "PA LLM Expander: expand_markers_only=True but no {@expand: ...} markers "
                    "found in prompt — passing through unchanged."
                )
                out_bundle = dict(prompt_bundle)
                out_bundle["resolved_text"] = original_text
                return (out_bundle, original_text, original_text)

            def _replace_marker(match: re.Match) -> str:
                inner_text = match.group(1)
                return client.expand(
                    text=inner_text,
                    provider=provider,
                    endpoint=endpoint,
                    model=model,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    api_key=api_key,
                )

            expanded_text = _EXPAND_PATTERN.sub(_replace_marker, resolved_text)
            # Clean any remaining sentinels (shouldn't be any, but safety)
            expanded_text = _strip_sentinels(expanded_text)
        else:
            # Expand entire prompt
            clean_text = _strip_sentinels(resolved_text)
            expanded_text = client.expand(
                text=clean_text,
                provider=provider,
                endpoint=endpoint,
                model=model,
                system_prompt=system_prompt,
                temperature=temperature,
                api_key=api_key,
            )

        # Build output bundle
        out_bundle = dict(prompt_bundle)
        out_bundle["resolved_text"] = expanded_text
        out_bundle["expand_all"] = False  # expansion done, clear flag

        return (out_bundle, expanded_text, original_text)

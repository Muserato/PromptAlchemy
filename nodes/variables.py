"""PA Variables node for ComfyUI."""

from __future__ import annotations

import logging

logger = logging.getLogger("PromptAlchemy")


class PAVariables:
    """Parses key=value pairs and outputs a variables dict for template nodes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "variables_text": ("STRING", {
                    "multiline": True,
                    "default": "style=cinematic\ncharacter=warrior",
                }),
            },
            "optional": {
                "upstream_vars": ("PA_VARIABLES",),
            },
        }

    RETURN_TYPES = ("PA_VARIABLES",)
    RETURN_NAMES = ("variables",)
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"

    def execute(self, variables_text: str, upstream_vars=None):
        # Start with upstream variables (if any)
        result: dict[str, str] = {}
        if upstream_vars is not None:
            result.update(upstream_vars)

        # Parse key=value pairs from text
        if variables_text.strip():
            for line_num, line in enumerate(variables_text.splitlines(), 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                eq_pos = line.find("=")
                if eq_pos <= 0:
                    logger.warning(
                        "PA Variables: skipping invalid line %d: %r (expected key=value)",
                        line_num, line,
                    )
                    continue

                key = line[:eq_pos].strip()
                value = line[eq_pos + 1:].strip()

                if not key:
                    logger.warning(
                        "PA Variables: skipping line %d with empty key", line_num
                    )
                    continue

                result[key] = value

        return (result,)

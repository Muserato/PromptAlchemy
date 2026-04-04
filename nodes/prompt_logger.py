"""PA Prompt Logger node for ComfyUI."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("PromptAlchemy")


def _parse_extra_metadata(text: str) -> dict[str, str]:
    """Parse key=value lines into a dict. Skips blank lines and comments."""
    result: dict[str, str] = {}
    if not text or not text.strip():
        return result
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        eq = line.find("=")
        if eq > 0:
            key = line[:eq].strip()
            value = line[eq + 1:].strip()
            if key:
                result[key] = value
    return result


class PAPromptLogger:
    """Logs prompt bundles to a JSONL file. Pure passthrough — does not modify the bundle."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt_bundle": ("PROMPT_BUNDLE",),
                "log_file": ("STRING", {
                    "default": "output/prompt_alchemy_log.jsonl",
                    "multiline": False,
                }),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "extra_metadata": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
            },
        }

    RETURN_TYPES = ("PROMPT_BUNDLE", "STRING")
    RETURN_NAMES = ("prompt_bundle", "resolved_text")
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"
    OUTPUT_NODE = True

    def execute(self, prompt_bundle: dict, log_file: str, enabled: bool,
                extra_metadata: str = ""):
        resolved_text = prompt_bundle.get("resolved_text", "")

        if enabled:
            self._write_log(prompt_bundle, log_file, extra_metadata)

        return (prompt_bundle, resolved_text)

    def _write_log(self, bundle: dict, log_file: str, extra_metadata: str) -> None:
        try:
            # Resolve relative paths against ComfyUI's working directory
            log_path = Path(log_file)
            if not log_path.is_absolute():
                log_path = Path(os.getcwd()) / log_path

            # Create parent directories
            log_path.parent.mkdir(parents=True, exist_ok=True)

            extra = _parse_extra_metadata(extra_metadata)

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "resolved_text": bundle.get("resolved_text", ""),
                "template_text": bundle.get("template_text", ""),
                "seed": bundle.get("seed", 0),
                "mode": bundle.get("mode", "random"),
                "variables": bundle.get("variables", {}),
                "wildcards_used": bundle.get("wildcards_used", {}),
                "selections_made": bundle.get("selections_made", []),
                "extra": extra,
            }

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.warning("PA Prompt Logger: failed to write log: %s", e)

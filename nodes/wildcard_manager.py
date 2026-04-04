"""PA Wildcard Manager node for ComfyUI."""

from __future__ import annotations

import logging
from pathlib import Path

from ..core.file_watcher import create_watched_index, WildcardWatcher
from ..core.types import WildcardIndex

logger = logging.getLogger("PromptAlchemy")

# Default wildcards directory: <this_extension>/wildcards/
_DEFAULT_WILDCARD_DIR = str(Path(__file__).parent.parent / "wildcards")

# Cache: maps frozenset of directories -> (index, watcher)
_cache: dict[frozenset[str], tuple[WildcardIndex, WildcardWatcher]] = {}


class PAWildcardManager:
    """Scans wildcard directories, builds an index, and watches for changes."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "wildcard_dir": ("STRING", {
                    "default": _DEFAULT_WILDCARD_DIR,
                    "multiline": False,
                }),
            },
            "optional": {
                "extra_dirs": ("STRING", {
                    "default": "",
                    "multiline": True,
                }),
            },
        }

    RETURN_TYPES = ("PA_WILDCARD_INDEX", "STRING")
    RETURN_NAMES = ("wildcard_index", "available_wildcards")
    FUNCTION = "execute"
    CATEGORY = "PromptAlchemy"

    def execute(self, wildcard_dir: str, extra_dirs: str = ""):
        # Collect all directories
        dirs: list[str] = []
        if wildcard_dir.strip():
            dirs.append(wildcard_dir.strip())

        if extra_dirs.strip():
            for line in extra_dirs.strip().splitlines():
                line = line.strip()
                if line:
                    dirs.append(line)

        # Validate directories
        valid_dirs: list[str] = []
        for d in dirs:
            p = Path(d)
            if p.is_dir():
                valid_dirs.append(str(p.resolve()))
            else:
                logger.warning("Wildcard directory does not exist: %s", d)

        if not valid_dirs:
            logger.warning("No valid wildcard directories configured")
            index = WildcardIndex()
            return (index, "")

        # Use cached index+watcher if directories match
        cache_key = frozenset(valid_dirs)
        if cache_key in _cache:
            index, _watcher = _cache[cache_key]
        else:
            index, watcher = create_watched_index(valid_dirs)
            _cache[cache_key] = (index, watcher)
            logger.info(
                "Wildcard index built: %d files from %d directories",
                len(index), len(valid_dirs),
            )

        available = ", ".join(index.keys())
        return (index, available)

"""Wildcard file loading and indexing for PromptAlchemy.

Loads .txt and .yaml wildcard files into a WildcardIndex.
Supports:
  - Plain text files (.txt): one entry per line
  - Flat YAML with `entries:` key (our original format)
  - Nested YAML categories (Dynamic Prompts / Impact Pack standard)
  - Inline weight syntax: `1.5::copper gold`
  - Object weight syntax: `{value: x, weight: y}`

No ComfyUI dependencies.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .types import WildcardEntry, WildcardFile, WildcardIndex

logger = logging.getLogger("PromptAlchemy")


# ---------------------------------------------------------------------------
# Entry parsing helpers
# ---------------------------------------------------------------------------

def _parse_entry(item) -> WildcardEntry | None:
    """Parse a single entry from a YAML list into a WildcardEntry.

    Supports:
      - Plain string: "deep crimson" → weight 1.0
      - Inline weight: "1.5::copper gold" → weight 1.5
      - Object syntax: {value: "x", weight: 0.5}
      - Empty string: "" → valid entry, weight 1.0
      - Numbers and other types: converted to string
    """
    if item is None:
        return WildcardEntry(value="", weight=1.0)

    if isinstance(item, dict):
        value = str(item.get("value", ""))
        weight = float(item.get("weight", 1.0))
        return WildcardEntry(value=value, weight=weight)

    text = str(item) if not isinstance(item, str) else item

    # Inline weight syntax: split on FIRST :: only
    if "::" in text:
        weight_str, _, value = text.partition("::")
        try:
            weight = float(weight_str)
            return WildcardEntry(value=value, weight=weight)
        except ValueError:
            pass  # Not a valid weight prefix — treat entire string as value

    return WildcardEntry(value=text, weight=1.0)


def _parse_entry_list(items: list) -> list[WildcardEntry]:
    """Parse a list of raw YAML items into WildcardEntry objects."""
    entries: list[WildcardEntry] = []
    for item in items:
        entry = _parse_entry(item)
        if entry is not None:
            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Nested YAML walking
# ---------------------------------------------------------------------------

def _walk_nested_yaml(
    data: dict,
    prefix: str,
    index: WildcardIndex,
) -> list[WildcardEntry]:
    """Recursively walk a nested YAML dict, registering each category path.

    Returns all entries found at or below this level (for parent flattening).
    """
    all_entries: list[WildcardEntry] = []
    # Direct list entries at this level (for mixed case C)
    direct_entries: list[WildcardEntry] = []

    for key, value in data.items():
        child_path = f"{prefix}/{key}" if prefix else key

        if isinstance(value, list):
            # Leaf: list of entries
            entries = _parse_entry_list(value)
            if entries:
                index.add(child_path, WildcardFile(name=key, entries=entries))
                all_entries.extend(entries)

        elif isinstance(value, dict):
            # Recurse into nested category
            child_entries = _walk_nested_yaml(value, child_path, index)
            all_entries.extend(child_entries)

        # Non-list, non-dict leaf values (strings, numbers) are ignored
        # per Dynamic Prompts behavior.

    # Also handle mixed Case C: if the parent data dict was passed items
    # that are list items alongside dict items, the caller handles that
    # via _walk_mixed_node.

    return all_entries


def _walk_mixed_node(
    items: list | None,
    children: dict,
    path: str,
    index: WildcardIndex,
) -> list[WildcardEntry]:
    """Handle a YAML node that has both direct list entries and subcategories."""
    all_entries: list[WildcardEntry] = []

    # Direct entries at this level
    if items:
        direct = _parse_entry_list(items)
        all_entries.extend(direct)

    # Recurse into child dicts
    child_entries = _walk_nested_yaml(children, path, index)
    all_entries.extend(child_entries)

    return all_entries


# ---------------------------------------------------------------------------
# File loaders
# ---------------------------------------------------------------------------

def load_txt_file(path: Path) -> WildcardFile:
    """Load a plain text wildcard file (one entry per line, # comments, blank lines ignored)."""
    entries: list[WildcardEntry] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                entries.append(WildcardEntry(value=line))
    except Exception as e:
        logger.warning("Failed to load wildcard file %s: %s", path, e)

    return WildcardFile(name=path.stem, entries=entries)


def load_yaml_file(path: Path) -> WildcardFile:
    """Load a YAML wildcard file. Detects flat vs nested format automatically."""
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed — cannot load %s", path)
        return WildcardFile(name=path.stem)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load YAML wildcard file %s: %s", path, e)
        return WildcardFile(name=path.stem)

    if not isinstance(data, dict):
        logger.warning("YAML wildcard file %s has invalid format (expected dict)", path)
        return WildcardFile(name=path.stem)

    # Case A: flat format with top-level `entries` key
    if "entries" in data:
        return _load_yaml_flat(data, path)

    # Case B/C: nested category format
    return None  # Sentinel — caller uses load_yaml_nested instead


def _load_yaml_flat(data: dict, path: Path) -> WildcardFile:
    """Load our original flat YAML format with `entries:` key."""
    name = data.get("name", path.stem)
    tags = data.get("tags", [])
    raw_entries = data.get("entries", [])
    entries = _parse_entry_list(raw_entries)
    return WildcardFile(name=name, entries=entries, tags=tags)


def load_yaml_nested(path: Path, base_key: str, index: WildcardIndex) -> None:
    """Load a nested YAML file and register all category paths into the index.

    base_key is the file's key prefix (e.g. "characters/mythological" for
    wildcards/characters/mythological.yaml).
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed — cannot load %s", path)
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load YAML wildcard file %s: %s", path, e)
        return

    if not isinstance(data, dict):
        logger.warning("YAML wildcard file %s has invalid format (expected dict)", path)
        return

    # Walk the top-level keys
    all_entries: list[WildcardEntry] = []

    for top_key, top_value in data.items():
        key_path = f"{base_key}/{top_key}" if base_key != top_key else top_key

        # If the file's base_key matches the single top-level key,
        # treat the children as direct subcategories of base_key.
        # e.g., file "characters/mythological.yaml" with top key "mythological"
        # → register as "characters/mythological/greek" not "characters/mythological/mythological/greek"
        if len(data) == 1 and top_key == Path(base_key).name:
            key_path = base_key

        if isinstance(top_value, list):
            entries = _parse_entry_list(top_value)
            if entries:
                index.add(key_path, WildcardFile(name=top_key, entries=entries))
                all_entries.extend(entries)

        elif isinstance(top_value, dict):
            # Check for mixed case: dict might contain both list items
            # and sub-dicts. Separate them.
            child_dicts = {}
            child_lists = []
            for k, v in top_value.items():
                if isinstance(v, (list, dict)):
                    child_dicts[k] = v
                # Non-list/dict values ignored

            child_entries = _walk_nested_yaml(
                {k: v for k, v in top_value.items()},
                key_path,
                index,
            )
            all_entries.extend(child_entries)

    # Register the flattened parent with ALL entries from all subcategories
    if all_entries:
        # Use base_key for the parent (e.g., "characters/mythological")
        parent_key = base_key
        if len(data) == 1:
            only_key = next(iter(data))
            if only_key == Path(base_key).name:
                parent_key = base_key
            else:
                parent_key = f"{base_key}/{only_key}"

        index.add(parent_key, WildcardFile(
            name=Path(parent_key).name,
            entries=all_entries,
        ))


# ---------------------------------------------------------------------------
# Index building
# ---------------------------------------------------------------------------

def _key_from_path(filepath: Path, base_dir: Path) -> str:
    """Convert a file path to a wildcard key (forward-slash, no extension)."""
    rel = filepath.relative_to(base_dir)
    parts = list(rel.parts)
    # Remove extension from last part
    parts[-1] = rel.stem
    return "/".join(parts)


def build_index(directories: list[str | Path]) -> WildcardIndex:
    """Scan directories for .txt and .yaml wildcard files and build an index."""
    index = WildcardIndex()

    for dir_path in directories:
        dir_path = Path(dir_path)
        if not dir_path.is_dir():
            logger.warning("Wildcard directory does not exist: %s", dir_path)
            continue

        for root, _dirs, files in os.walk(dir_path):
            root_path = Path(root)
            for filename in sorted(files):
                filepath = root_path / filename
                ext = filepath.suffix.lower()

                if ext == ".txt":
                    wf = load_txt_file(filepath)
                    key = _key_from_path(filepath, dir_path)
                    index.add(key, wf)

                elif ext in (".yaml", ".yml"):
                    key = _key_from_path(filepath, dir_path)
                    # Try flat format first
                    wf = load_yaml_file(filepath)
                    if wf is not None:
                        # Flat format — register as single key
                        index.add(key, wf)
                    else:
                        # Nested format — register subcategory paths
                        load_yaml_nested(filepath, key, index)

    return index


def reload_file(index: WildcardIndex, filepath: Path, base_dir: Path) -> None:
    """Reload a single file into the index (for hot-reload)."""
    key = _key_from_path(filepath, base_dir)
    ext = filepath.suffix.lower()

    if not filepath.exists():
        # Remove this key and any sub-keys (for nested YAML)
        keys_to_remove = [k for k in index.keys() if k == key or k.startswith(key + "/")]
        for k in keys_to_remove:
            index.remove(k)
        if keys_to_remove:
            logger.info("Wildcard removed: %s (%d keys)", key, len(keys_to_remove))
        return

    if ext == ".txt":
        wf = load_txt_file(filepath)
        index.add(key, wf)
        logger.info("Wildcard reloaded: %s (%d entries)", key, len(wf.entries))

    elif ext in (".yaml", ".yml"):
        # Remove old keys for this file first (nested might have changed structure)
        old_keys = [k for k in index.keys() if k == key or k.startswith(key + "/")]
        for k in old_keys:
            index.remove(k)

        wf = load_yaml_file(filepath)
        if wf is not None:
            index.add(key, wf)
            logger.info("Wildcard reloaded: %s (%d entries)", key, len(wf.entries))
        else:
            load_yaml_nested(filepath, key, index)
            new_keys = [k for k in index.keys() if k == key or k.startswith(key + "/")]
            logger.info("Wildcard reloaded (nested): %s (%d keys)", key, len(new_keys))

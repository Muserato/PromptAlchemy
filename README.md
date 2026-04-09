# ComfyUI-PromptAlchemy

A modern prompt templating system for ComfyUI — wildcards, variables, conditionals, LLM expansion, and prompt logging in clean composable nodes.

**PromptAlchemy** replaces the abandoned [Dynamic Prompts](https://github.com/adieyal/comfyui-dynamicprompts) extension with 6 focused, composable nodes instead of 22 specialized ones. It's backward-compatible with existing `{a|b|c}` and `__wildcard__` syntax, and adds variables, conditionals, numeric ranges, LLM-powered expansion, and full prompt logging.

---

## Features

- **6 composable nodes** — Template, Variables, Wildcard Manager, Combiner, LLM Expander, Logger
- **Backward compatible** — existing `{a|b|c}` selections and `__wildcard__` files work as-is
- **Hot-reload wildcards** — edit wildcard files without restarting ComfyUI
- **LoRA-safe** — `<lora:some__model__name:1.0>` passes through unbroken
- **LLM-powered expansion** — enhance prompts via Ollama, OpenAI-compatible, or Anthropic APIs
- **Deterministic seeds** — same seed = same output, every time
- **Sequential mode** — iterate through options systematically across queue runs
- **Weighted selections** — control probability of each option
- **YAML wildcards** — weighted entries, metadata tags, and portable relative references
- **Prompt logging** — JSONL log of every resolved prompt for traceability
- **Variables and conditionals** — build dynamic, reusable templates
- **Numeric ranges** — random values for CFG, steps, weights, and more

---

## Installation

### Via ComfyUI Manager

Search for **PromptAlchemy** in the ComfyUI Manager and click Install.

### Manual Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Muserato/PromptAlchemy.git ComfyUI-PromptAlchemy
cd ComfyUI-PromptAlchemy
pip install -r requirements.txt
```

**Optional** — install `watchdog` for efficient file-system-based wildcard hot-reload (otherwise falls back to 5-second polling):

```bash
pip install watchdog
```

Restart ComfyUI after installation.

---

## Quick Start

1. Add a **PA Prompt Template** node
2. Connect its `resolved_text` output to a **CLIP Text Encode** node
3. Write a template:

```
a {beautiful|stunning|majestic} __colors__ dragon in __art_styles__ style, __lighting__
```

4. Queue the prompt — PromptAlchemy resolves all `{selections}` and `__wildcards__` into final text

Example output: `a stunning emerald dragon in cyberpunk style, golden hour sunlight`

---

## Syntax Reference

### Basic Selections

| Syntax | Description | Example Output |
|--------|-------------|----------------|
| `{red\|blue\|green}` | Random pick from options | `blue` |
| `{2$$red\|blue\|green}` | Pick 2, comma-separated | `red, green` |
| `{2-4$$red\|blue\|green\|yellow}` | Pick 2 to 4 | `red, blue, yellow` |
| `{2$$ and $$red\|blue\|green}` | Pick 2 with custom separator | `red and blue` |
| `{0.7::dramatic\|0.3::soft}` | Weighted random (70%/30%) | `dramatic` |

### Wildcards

| Syntax | Description |
|--------|-------------|
| `__colors__` | Random line from `wildcards/colors.txt` |
| `__animals/mammals__` | Random line from `wildcards/animals/mammals.txt` |
| `__animals/*__` | Random file from `animals/` directory, then random line |

### Variables

| Syntax | Description |
|--------|-------------|
| `{$style}` | Reference a variable |
| `{$style=cinematic}` | Set a variable inline (produces no output) |

Variables can be set via the **PA Variables** node or inline in templates.

### Numeric Ranges

| Syntax | Description | Example Output |
|--------|-------------|----------------|
| `{steps:20-35}` | Random integer in range | `27` |
| `{weight:0.8-1.3}` | Random float (2 decimal places) | `1.07` |
| `{cfg:5.0-9.0:0.5}` | Float in range with step | `7.0` |

### Conditionals

| Syntax | Description |
|--------|-------------|
| `{if $style==cinematic: epic lighting \| soft glow}` | If style is "cinematic", use true branch |
| `{if $style!=photo: illustration, artwork}` | If style is not "photo", use this text |

### LLM Expansion Markers

| Syntax | Description |
|--------|-------------|
| `{@expand: a muscular warrior}` | Send this text to LLM Expander for enhancement |
| `{@expand}` | Flag entire prompt for LLM expansion |

Markers are only processed when a **PA LLM Expander** node is connected. Otherwise, `{@expand: text}` outputs the inner text unchanged.

### Nesting

All syntax can be nested freely:

```
a {red|blue} {cat|{big|small} dog}
{if $mood==dark: {ominous|foreboding} | {bright|cheerful}} atmosphere
a __colors__ __animals/{$type}__
```

### Sequential Mode

When a Template node is set to **sequential** mode, selections and wildcards iterate in order instead of picking randomly:

```
{a|b|c}  →  Queue 1: "a", Queue 2: "b", Queue 3: "c", Queue 4: "a" (cycles)
```

### Escapes and Comments

| Syntax | Description |
|--------|-------------|
| `\{` `\}` | Literal braces (not parsed) |
| `\_\_` | Literal double underscore (not a wildcard) |
| `// comment` | Line comment (stripped from output) |
| `/* block */` | Block comment (stripped) |

---

## Node Reference

### PA Prompt Template

The core node. Parses and resolves prompt templates.

| Input | Type | Description |
|-------|------|-------------|
| `template` | STRING (multiline) | Prompt template with syntax |
| `seed` | INT | Random seed (deterministic) |
| `mode` | random / sequential | Selection mode |
| `variables` | PA_VARIABLES (optional) | Variables from Variables node |
| `wildcard_index` | PA_WILDCARD_INDEX (optional) | Index from Wildcard Manager |

| Output | Type | Description |
|--------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Full structured output |
| `resolved_text` | STRING | Plain text for CLIP Text Encode |
| `seed` | INT | The seed used |

**Examples:**

Minimum viable template — selections and wildcards:
```
a {beautiful|stunning|majestic} __colors__ dragon in __art_styles__ style, __lighting__
```
Resolved: `a stunning emerald dragon in oil painting style, volumetric lighting`

Variables and conditionals (connect a Variables node with `style=cinematic`, `subject=warrior`):
```
a {$subject} in {$style} style, {if $style==cinematic: dramatic rim lighting | soft ambient light}, __environments/outdoor__
```
Resolved: `a warrior in cinematic style, dramatic rim lighting, misty highland cliffs`

Numeric range inside a LoRA weight + multi-select quality tags:
```
portrait, <lora:detail_enhancer:{weight:0.8-1.2}>, {2$$sharp focus|fine detail|intricate texture}, __quality_boosters__
```
Resolved: `portrait, <lora:detail_enhancer:1.07>, sharp focus, fine detail, masterpiece`

---

### PA Variables

Defines key-value variables for use in templates.

| Input | Type | Description |
|-------|------|-------------|
| `variables_text` | STRING (multiline) | `key=value` pairs, one per line |
| `upstream_vars` | PA_VARIABLES (optional) | Variables from another Variables node |

| Output | Type | Description |
|--------|------|-------------|
| `variables` | PA_VARIABLES | Variable dict |

**Format:**
```
style=cinematic
character=Zeus
lighting=volumetric
```

Lines starting with `#` are comments. Multiple Variables nodes can be chained — downstream values override upstream.

**Examples:**

Define a reusable style preset and reference it throughout your template:
```
# variables_text
style=cinematic
character=warrior
lighting=volumetric
```
Template: `a {$character} in {$style} style, {$lighting}, {if $style==cinematic: anamorphic lens flare}`

Chain two Variables nodes for global defaults with per-scene overrides — upstream node defines `style=cinematic, mood=epic`; downstream node defines `mood=serene`. The template sees `style=cinematic, mood=serene` (downstream wins on conflict, upstream values are kept otherwise).

### PA Wildcard Manager

Scans directories for wildcard files and provides a shared index.

| Input | Type | Description |
|-------|------|-------------|
| `wildcard_dir` | STRING | Path to wildcards directory |
| `extra_dirs` | STRING (multiline, optional) | Additional directories, one per line |

| Output | Type | Description |
|--------|------|-------------|
| `wildcard_index` | PA_WILDCARD_INDEX | Index for Template nodes |
| `available_wildcards` | STRING | Comma-separated list of available wildcard names |

If no Wildcard Manager is connected, Template nodes automatically use the built-in `wildcards/` directory.

**Examples:**

Merge your own wildcard pack with the built-in wildcards:
```
wildcard_dir:  ComfyUI-PromptAlchemy/wildcards

extra_dirs:
C:/MyWildcards/portraits
C:/MyWildcards/vehicles
```
Now `__portraits/style__` and `__vehicles/cars__` resolve alongside the built-in `__colors__` and `__art_styles__`.

Connect the `available_wildcards` output to a **Show Text** node to inspect every loaded wildcard name before writing your template — useful when pointing to a large third-party wildcard pack.

### PA Prompt Combiner

Joins multiple resolved prompts with a separator.

| Input | Type | Description |
|-------|------|-------------|
| `bundle_1` | PROMPT_BUNDLE | First prompt |
| `bundle_2` | PROMPT_BUNDLE (optional) | Second prompt |
| `bundle_3` | PROMPT_BUNDLE (optional) | Third prompt |
| `separator` | STRING | Join separator (default: `", "`) |

| Output | Type | Description |
|--------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Combined bundle |
| `resolved_text` | STRING | Combined text |

**Examples:**

Classic 3-part prompt — subject, environment, quality boosters joined with `", "`:

| Slot | Template | Resolved |
|------|----------|----------|
| bundle_1 | `a {majestic\|fierce} __characters/archetypes__` | `a fierce rogue` |
| bundle_2 | `in __environments/outdoor__` | `in a misty forest` |
| bundle_3 | `__quality_boosters__, __lighting__` | `masterpiece, golden hour sunlight` |

Combined (separator `", "`): `a fierce rogue, in a misty forest, masterpiece, golden hour sunlight`

Append a style tag without touching the main prompt — set separator to `" "` and bundle_2 to `| style: __art_styles__`, so the final text reads `<your prompt> | style: oil painting` — useful for SDXL style conditioning.

### PA LLM Expander

Sends prompt text to an LLM for enhancement. Fully optional.

| Input | Type | Description |
|-------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Input bundle |
| `provider` | ollama / openai_compatible / anthropic | LLM provider |
| `endpoint` | STRING | API endpoint URL |
| `model` | STRING | Model name |
| `system_prompt` | STRING (multiline) | Instructions for the LLM |
| `temperature` | FLOAT (0.0-2.0) | Sampling temperature |
| `expand_markers_only` | BOOLEAN | If true, only expand `{@expand}` sections |
| `api_key` | STRING (optional) | API key for authenticated providers |

| Output | Type | Description |
|--------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Bundle with expanded text |
| `resolved_text` | STRING | Expanded text |
| `original_text` | STRING | Pre-expansion text |

**Examples:**

Flag the entire prompt for LLM expansion with a bare `{@expand}` marker — the LLM rewrites the whole thing:
```
{@expand} a knight, forest, dramatic lighting
```
LLM output: `A battle-worn knight clad in ornate silver armor stands at the edge of an ancient forest, shafts of golden light piercing the canopy, casting long dramatic shadows across mossy stone ruins`

Expand only one section while keeping the rest of the prompt exact — set `expand_markers_only` to `true`:
```
masterpiece, {@expand: a knight standing at the edge of a forest}, soft bokeh background
```
LLM expands only the marked part: `masterpiece, a battle-worn knight in ornate plate armor, ancient moss-covered trees looming behind him, dappled light filtering through oak branches, soft bokeh background`

Use a custom system prompt to lock in a style — replace the default with:
```
You are an expert prompt writer for anime illustrations in the style of Studio Ghibli.
Enhance the prompt with nature imagery, soft light, and hand-drawn warmth.
Output ONLY the enhanced prompt, no explanations.
```

### PA Prompt Logger

Logs every resolved prompt to a JSONL file. Pure passthrough — does not modify the prompt.

| Input | Type | Description |
|-------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Bundle to log |
| `log_file` | STRING | Log file path (default: `output/prompt_alchemy_log.jsonl`) |
| `enabled` | BOOLEAN | Toggle logging on/off |
| `extra_metadata` | STRING (multiline, optional) | Additional `key=value` pairs for log |

| Output | Type | Description |
|--------|------|-------------|
| `prompt_bundle` | PROMPT_BUNDLE | Pass-through |
| `resolved_text` | STRING | Pass-through |

**Examples:**

Tag log entries with project metadata so you can filter the JSONL file later:
```
# extra_metadata
project=dragons_series
artist=jcb
session=batch_001
```
Each log entry will include `"extra": {"project": "dragons_series", "artist": "jcb", "session": "batch_001"}` alongside the resolved text, seed, variables, and wildcard choices.

Insert the Logger between the LLM Expander and CLIP Text Encode to record the post-expansion text. Toggle it off with `enabled=false` during fast iteration without disconnecting the node.

---

## Wildcard Files

### Plain Text (.txt)

One entry per line. Blank lines and `#` comments are ignored.

```
# moods.txt
serene
ominous
triumphant
melancholic
```

### Nested YAML (.yaml) — Recommended for organized collections

The standard format used by Dynamic Prompts, Impact Pack, and most wildcard packs. Categories are nested dicts with lists of entries at the leaves:

```yaml
# colors.yaml
colors:
  warm:
    - deep crimson
    - burnt amber
    - copper gold
  cool:
    - sapphire blue
    - ice blue
    - midnight blue
  jewel:
    - emerald green
    - ruby red
    - amethyst purple
```

This registers multiple wildcard paths from a single file:

| Reference | Picks from |
|-----------|-----------|
| `__colors/warm__` | warm list only |
| `__colors/cool__` | cool list only |
| `__colors__` | ALL entries across all subcategories |
| `__colors/*__` | random subcategory, then random entry from it |

Nesting can be arbitrarily deep. Existing Dynamic Prompts wildcard packs work as-is.

### Weighted Entries

Control how likely each entry is to be picked. Two syntaxes are supported:

**Inline weight** (recommended) — same `weight::value` syntax as template selections:

```yaml
mythological:
  greek:
    - Zeus
    - 1.5::Hercules
    - 0.5::Hephaestus
```

**Object weight** — explicit key-value pairs:

```yaml
entries:
  - value: golden hour sunlight
    weight: 1.5
  - value: neon rim lighting
    weight: 0.8
```

Default weight is `1.0`. A weight of `1.5` means 50% more likely than `1.0`.

### Empty String Entries

An empty string `""` is a valid entry. When selected, it produces no text — letting the model decide. Useful for optional modifiers:

```yaml
colors:
  warm:
    - deep crimson
    - burnt amber
    - ""
```

### Flat YAML (legacy format)

The original format with a top-level `entries` key is still fully supported:

```yaml
name: Lighting Styles
tags: [lighting, atmosphere]
entries:
  - volumetric lighting
  - 1.5::golden hour sunlight
  - value: neon rim lighting
    weight: 0.8
```

### Directory Structure

```
wildcards/
├── art_styles.txt                → __art_styles__
├── moods.txt                     → __moods__
├── compositions.txt              → __compositions__
├── quality_boosters.txt          → __quality_boosters__
├── colors.yaml                   → __colors__, __colors/warm__, __colors/cool__, ...
├── lighting.yaml                 → __lighting__, __lighting/dramatic__, ...
├── materials.yaml                → __materials__, __materials/metal__, ...
├── characters/
│   ├── mythological.yaml         → __characters/mythological/greek__, ...
│   └── archetypes.yaml           → __characters/archetypes/warrior__, ...
├── environments/
│   ├── indoor.yaml               → __environments/indoor/cozy__, ...
│   ├── outdoor.yaml              → __environments/outdoor/wilderness__, ...
│   └── outdoor/
│       ├── weather.yaml          → __environments/outdoor/weather/stormy__, ...
│       └── seasons.yaml          → __environments/outdoor/seasons/autumn__, ...
├── scenes/
│   └── portrait_builder.yaml     → self-contained with relative references
└── themes/
    ├── fantasy.yaml              → cross-file assembly with globs
    └── scifi.yaml                → glob pattern demos
```

> **Starter Kit:** PromptAlchemy ships with example wildcard files demonstrating every feature. Use them as-is or replace with your own collections. See `wildcards/scenes/portrait_builder.yaml` for a self-contained demo of relative references, weighted entries, cross-file wildcards, and selection syntax all in one file.

### Glob Patterns

| Pattern | Behavior |
|---------|----------|
| `__colors/warm__` | Pick from the `warm` subcategory |
| `__colors__` | Pick from ALL entries across all subcategories |
| `__colors/*__` | Pick a random direct subcategory, then a random entry from it |
| `__colors/**__` | Pick from any subcategory at any nesting depth |
| `__colors/**/pastels__` | Pick from any `pastels` key at any depth under `colors` |

The mid-path `**` glob is useful for deeply nested collections. For example, with a YAML structure like `colors/reds/pastels`, `colors/greens/pastels`, `colors/blues/pastels` — the pattern `__colors/**/pastels__` pools all entries from every matching `pastels` subcategory and picks from the combined set.

### Relative Wildcard References

Wildcard entries can reference other wildcards using short, relative names. When a wildcard name isn't found as an absolute path, PromptAlchemy walks up the current file's path to find a match. This makes wildcard files **portable** — you can move or rename a folder without breaking internal references.

**How it works:**

1. The name is tried as-is (absolute lookup) — if found, it's used immediately
2. Only if not found, the resolver tries prepending parent paths from the current context, walking upward

**Example:** A file at `wildcards/themes/fantasy.yaml`:

```yaml
fantasy:
  creatures:
    - "a __palette__ __world/biomes__ dragon"
  palette:
    - golden
    - silver
  world:
    biomes:
      - forest
      - mountain
```

When resolving `creatures`, the entry references `__palette__` and `__world/biomes__`:

- `__palette__` → absolute lookup fails → tries `themes/fantasy/creatures/palette` (not found) → tries `themes/fantasy/palette` → found!
- `__world/biomes__` → absolute lookup fails → tries `themes/fantasy/creatures/world/biomes` (not found) → tries `themes/fantasy/world/biomes` → found!

If you move the entire `themes/fantasy.yaml` file to `my_pack/fantasy.yaml`, all internal references still work because they resolve relative to the current context.

**Backward compatibility:** Absolute paths always take priority. If `__palette__` exists at both the root level and within the current file's scope, the root-level one wins (matching existing behavior). Relative resolution only activates when the absolute lookup finds nothing.

### Hot-Reload

Wildcard files are watched for changes. Edit a file and queue again — PromptAlchemy picks up the new content automatically without restarting ComfyUI.

- With `watchdog` installed: instant file-system events
- Without `watchdog`: polling every 5 seconds

---

## LLM Expander Setup

The LLM Expander communicates via plain HTTP — no provider-specific packages required.

### Ollama (Local)

1. Install [Ollama](https://ollama.ai) and pull a model: `ollama pull llama3.2`
2. Set provider to `ollama`
3. Endpoint: `http://localhost:11434` (default)
4. Model: `llama3.2`

### OpenAI-Compatible

Works with OpenAI, Together, Groq, LM Studio, and any OpenAI-compatible endpoint.

1. Set provider to `openai_compatible`
2. Endpoint: `https://api.openai.com` (or your provider's URL)
3. Model: `gpt-4o` (or your model)
4. API Key: your key

### Anthropic

1. Set provider to `anthropic`
2. Endpoint: `https://api.anthropic.com`
3. Model: `claude-sonnet-4-20250514`
4. API Key: your Anthropic API key

### Custom System Prompt

The default system prompt instructs the LLM to enhance prompts for Stable Diffusion. You can customize it for your use case — for example, to enforce a particular style or add negative prompt awareness.

If the LLM is unreachable or returns an error, the original text passes through unchanged with a warning in the console.

---

## Migration from Dynamic Prompts

### What works the same

- `{a|b|c}` random selection
- `__wildcard__` file references
- Plain text `.txt` wildcard files (one entry per line)
- Nesting `{a {red|blue} thing|simple}`

### What's new

- `{$variables}` and `{$var=value}` inline assignment
- `{if $var==value: ...}` conditionals
- `{steps:20-35}` numeric ranges
- `{0.7::option}` weighted selections
- `{@expand: text}` LLM expansion markers
- `{2$$a|b|c}` multi-select (fixed — it's broken in Dynamic Prompts)
- YAML wildcard files with weights and relative references
- Sequential mode for systematic iteration
- JSONL prompt logging
- Hot-reload wildcards without restart

### What's different

- Node names start with **PA** (PA Prompt Template, PA Variables, etc.)
- Variables use `{$name}` syntax instead of Dynamic Prompts' `__name^var__`
- PromptAlchemy passes structured `PROMPT_BUNDLE` data between nodes, not just strings
- 6 nodes instead of 22 — composable rather than specialized

### Wildcard Compatibility

Your existing `.txt` wildcard files work as-is. Nested YAML wildcard packs from Dynamic Prompts and Impact Pack also load natively — just point the PA Wildcard Manager to your existing wildcards directory, or drop the files into `ComfyUI-PromptAlchemy/wildcards/`.

---

## Example Workflows

Located in `example_workflows/`:

| Workflow | Description |
|----------|-------------|
| `basic_random.json` | Minimal: Template with selections and wildcards |
| `variables_and_wildcards.json` | Variables + Wildcard Manager + Template |
| `combined_prompts.json` | Two Templates joined by a Combiner |
| `llm_expansion.json` | Template with `{@expand}` marker + LLM Expander |
| `batch_sequential.json` | Sequential mode for systematic exploration |
| `full_pipeline.json` | All 6 nodes connected end-to-end |

---

## Troubleshooting

**Nodes not appearing in ComfyUI**
- Restart ComfyUI and check the console for import errors
- Verify `requirements.txt` dependencies are installed: `pip install -r requirements.txt`

**Wildcards not resolving (showing raw `__name__`)**
- Check that the wildcard file exists in the `wildcards/` directory
- Verify the file name matches (without extension): `colors.txt` = `__colors__`
- If using a Wildcard Manager, check the `available_wildcards` output

**LLM Expander not responding**
- Verify your LLM server is running (`ollama serve` for Ollama)
- Check the endpoint URL and model name
- Check the ComfyUI console for connection warnings
- The prompt passes through unchanged on any LLM error — it never crashes

**LoRA names with `__` in them**
- PromptAlchemy automatically handles this — `<lora:cool__model__v2:1.0>` passes through untouched
- Only `__word__` patterns outside of `<lora:>` and `<hypernet:>` tags are treated as wildcards

**Sequential mode not advancing**
- Sequential mode tracks position per node instance — each queue run advances by one
- The index resets when ComfyUI restarts

---

## License

MIT License. See [LICENSE](LICENSE) for details.

Built as a modern replacement for the abandoned [Dynamic Prompts](https://github.com/adieyal/comfyui-dynamicprompts) extension, with gratitude for the syntax conventions it established.

For bug reports and feature requests, please open an issue on GitHub.

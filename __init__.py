"""ComfyUI-PromptAlchemy: Modular prompt templating and generation system."""

try:
    from .nodes.prompt_template import PAPromptTemplate
    from .nodes.wildcard_manager import PAWildcardManager
    from .nodes.variables import PAVariables
    from .nodes.prompt_combiner import PAPromptCombiner
    from .nodes.llm_expander import PALLMExpander
    from .nodes.prompt_logger import PAPromptLogger

    NODE_CLASS_MAPPINGS = {
        "PAPromptTemplate": PAPromptTemplate,
        "PAWildcardManager": PAWildcardManager,
        "PAVariables": PAVariables,
        "PAPromptCombiner": PAPromptCombiner,
        "PALLMExpander": PALLMExpander,
        "PAPromptLogger": PAPromptLogger,
    }

    NODE_DISPLAY_NAME_MAPPINGS = {
        "PAPromptTemplate": "PA Prompt Template \u2728",
        "PAWildcardManager": "PA Wildcard Manager \U0001f4c1",
        "PAVariables": "PA Variables \U0001f524",
        "PAPromptCombiner": "PA Prompt Combiner \U0001f517",
        "PALLMExpander": "PA LLM Expander \U0001f9e0",
        "PAPromptLogger": "PA Prompt Logger \U0001f4dd",
    }
except ImportError:
    # When imported outside ComfyUI (e.g. during testing), skip node registration
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

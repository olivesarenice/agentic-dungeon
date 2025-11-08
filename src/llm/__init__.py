"""
LLM package for language model interactions.
"""

from .llm_module import LLMModule, create_llm_module
from .prompts import PromptBuilder, PromptTemplates

__all__ = ["LLMModule", "create_llm_module", "PromptTemplates", "PromptBuilder"]

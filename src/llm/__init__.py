"""
LLM package for language model interactions.
"""

from .llm_module import (
    LLMModule,
    create_fast_llm,
    create_llm_module,
    create_quality_llm,
)
from .prompts import PromptBuilder, PromptTemplates

__all__ = [
    "LLMModule",
    "create_llm_module",
    "create_fast_llm",
    "create_quality_llm",
    "PromptTemplates",
    "PromptBuilder",
]

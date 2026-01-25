"""
LLM-based prompt optimization for image generation models.
Uses a fast LLM to convert structured prompts to model-specific formats.
"""

from typing import Optional

from llm.llm_module import create_fast_llm
from llm.prompts import PromptTemplates


class PromptOptimizer:
    """LLM-based optimizer that converts prompts for different image generation models."""

    def __init__(self):
        """Initialize the optimizer with a fast LLM for prompt conversion."""
        # Use fast LLM for efficient prompt optimization
        self.llm = create_fast_llm(
            system_prompt="You are an expert at optimizing image generation prompts. "
            "You convert structured prompts into dense narrative formats that work best "
            "for specific image models. You focus on concrete visual descriptions and "
            "remove abstract or non-visual elements."
        )
        print("📝 Prompt optimizer initialized with fast LLM")

    @staticmethod
    def is_flash_model(model_name: str) -> bool:
        """Check if the model is a Flash variant that needs optimization."""
        return "flash" in model_name.lower()

    @staticmethod
    def is_pro_model(model_name: str) -> bool:
        """Check if the model is a Pro variant that uses structured prompts."""
        return "pro" in model_name.lower()

    def optimize_for_flash(
        self,
        art_style: str,
        room_name: str,
        room_description: str,
        player_info: Optional[str] = None,
    ) -> str:
        """
        Use an LLM to convert a structured prompt to Flash-optimized format.

        The LLM will:
        1. Front-load the art style
        2. Convert abstract concepts to concrete visuals
        3. Remove non-visual elements
        4. Create a dense narrative paragraph

        Args:
            art_style: Art style description
            room_name: Name of the room
            room_description: Description of the room
            player_info: Optional player information

        Returns:
            Flash-optimized dense narrative prompt
        """
        # Build the optimization prompt
        player_text = f"Players: {player_info}" if player_info else ""

        optimization_prompt = PromptTemplates.FLASH_IMAGE_OPTIMIZER.substitute(
            art_style=art_style,
            room_name=room_name,
            room_description=room_description,
            player_info=player_text,
        )

        # Use the fast LLM to optimize
        print("🔧 Converting to Flash-optimized dense narrative format...")
        optimized_prompt = self.llm.get_response(optimization_prompt, temperature=0.3)

        if optimized_prompt:
            print(f"✨ Optimized prompt ({len(optimized_prompt)} chars)")
            return optimized_prompt.strip()
        else:
            # Fallback to basic concatenation if LLM fails
            print("⚠️ Optimization failed, using fallback format")
            return f"{art_style} showing {room_name}. {room_description}"

    def optimize_prompt(
        self,
        model_name: str,
        original_prompt: str,
        art_style: str,
        room_name: str,
        room_description: str,
        player_info: Optional[str] = None,
    ) -> str:
        """
        Main entry point - optimizes prompt based on model type.

        Args:
            model_name: Name of the image generation model
            original_prompt: Original structured prompt (used as fallback)
            art_style: Art style description
            room_name: Name of the room
            room_description: Description of the room
            player_info: Optional player information

        Returns:
            Optimized prompt for the specific model
        """
        if True:  # self.is_flash_model(model_name):
            # Use LLM to convert to Flash-optimized format
            return self.optimize_for_flash(
                art_style=art_style,
                room_name=room_name,
                room_description=room_description,
                player_info=player_info,
            )
        else:
            # Pro models or unknown models - use original structured format
            print("📝 Using original structured format for Pro/standard model")
            return original_prompt


# Singleton instance for reuse
_optimizer_instance: Optional[PromptOptimizer] = None


def get_prompt_optimizer() -> PromptOptimizer:
    """Get or create the singleton PromptOptimizer instance."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = PromptOptimizer()
    return _optimizer_instance

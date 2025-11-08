"""
Helper utility functions.
"""

from datetime import datetime, timezone


def iso_ts() -> str:
    """
    Get current timestamp in ISO format.

    Returns:
        ISO formatted timestamp string
    """
    return datetime.now(timezone.utc).isoformat()


def safe_input(prompt: str, color_func=None) -> str:
    """
    Get user input with automatic /q quit detection.

    Args:
        prompt: The prompt to display
        color_func: Optional color function to format prompt (e.g., Colors.input_prompt)

    Returns:
        User input string

    Raises:
        QuitGameException: If user enters /q
    """
    from .colors import Colors
    from .exceptions import QuitGameException

    # Apply color if provided
    if color_func:
        formatted_prompt = color_func(prompt)
    else:
        formatted_prompt = prompt

    user_input = input(formatted_prompt).strip()

    # Check for quit command
    if user_input.lower() == "/q":
        raise QuitGameException("Player quit the game")

    return user_input

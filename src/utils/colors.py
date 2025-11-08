"""
Color utilities for consistent terminal output formatting.

Color scheme:
- Yellow: Info directed to player (prompts, DM dialogue, info)
- Green: Explicit player input prompts
- Blue: Data-related changes (room updates, player memory, etc.)
- Default: Debugging and general server statements
"""


class Colors:
    """ANSI color codes for terminal output."""

    # Main colors
    YELLOW = "\033[93m"  # Player-directed info
    GREEN = "\033[92m"  # Input prompts
    BLUE = "\033[94m"  # Data changes
    RED = "\033[91m"  # Errors

    # Reset
    RESET = "\033[0m"

    @staticmethod
    def player_info(text: str) -> str:
        """Format text as player-directed information (yellow)."""
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def input_prompt(text: str) -> str:
        """Format text as input prompt (green)."""
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def data_change(text: str) -> str:
        """Format text as data change notification (blue)."""
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def error(text: str) -> str:
        """Format text as error message (red)."""
        return f"{Colors.RED}{text}{Colors.RESET}"

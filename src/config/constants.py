"""
Constants and configuration values for the game.
Centralizes magic numbers and configuration parameters.
"""


class GameConstants:
    """Game-related constants."""

    # Room generation
    MAX_ROOM_PATHS = 3
    DEFAULT_DESCRIPTION_WORDS = (
        40  # Reduced from 100 for concise D&D-style descriptions
    )

    # CLI rendering
    CLI_CELL_HEIGHT = 5
    CLI_CELL_WIDTH = 9

    # Player limits
    MAX_PLAYERS = 10
    MAX_ACTION_DETAIL_LENGTH = 200
    N_NPCS = 5
    N_HUMANS = 0

    # NPC behavior
    NPC_MOVE_PROBABILITY = 0.2  # 0.0 = never move, 1.0 = always move (vs TALK/INTERACT)

    # Memory limits
    MAX_MEMORY_EVENTS = 50
    MAX_INTERACTION_HISTORY = 20


class LLMConstants:
    """LLM-related constants."""

    # Response limits
    MIN_RESPONSE_WORDS = 1
    MAX_RESPONSE_WORDS = 1000
    DEFAULT_DESCRIPTION_WORDS = 20

    # Retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

"""
Game configuration using enums and constants for type safety.
"""

from dataclasses import dataclass

from config.constants import GameConstants
from config.enums import ActionType, Direction
from models import Action, Move


@dataclass
class GameConfigs:
    """
    Central configuration for game moves and actions.
    Uses enums for type safety instead of raw strings.
    """

    _moves: dict[str, Move] = None
    _actions: dict[str, Action] = None

    def __post_init__(self):
        """Initialize moves and actions using enums."""
        if self._moves is None:
            self._moves = {
                Direction.NORTH.value: Move(
                    Direction.NORTH.value,
                    Direction.NORTH.translation,
                    Direction.NORTH.opposite.value,
                ),
                Direction.SOUTH.value: Move(
                    Direction.SOUTH.value,
                    Direction.SOUTH.translation,
                    Direction.SOUTH.opposite.value,
                ),
                Direction.EAST.value: Move(
                    Direction.EAST.value,
                    Direction.EAST.translation,
                    Direction.EAST.opposite.value,
                ),
                Direction.WEST.value: Move(
                    Direction.WEST.value,
                    Direction.WEST.translation,
                    Direction.WEST.opposite.value,
                ),
            }

        if self._actions is None:
            self._actions = {
                # OBSERVE removed - happens automatically when entering rooms
                ActionType.TALK.value: Action(
                    ActionType.TALK.value,
                    description="Make a comment about something that everyone in the room can hear.",
                    player_prompt="What do you say?",
                    affects_room=False,
                    affects_players=True,
                ),
                ActionType.INTERACT.value: Action(
                    ActionType.INTERACT.value,
                    description="Modify something about the room. Other people can see you do this. You can only do 1 exact action, nothing more to follow up.",
                    player_prompt="What do you do?",
                    affects_room=True,
                    affects_players=True,
                ),
            }


# Create a default instance for backward compatibility
_default_config = GameConfigs()
GameConfigs._moves = _default_config._moves
GameConfigs._actions = _default_config._actions

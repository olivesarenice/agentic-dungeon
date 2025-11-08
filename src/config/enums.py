"""
Type-safe enums for game logic.
Prevents string typos and provides better IDE support.
"""

from enum import Enum


class ActionType(Enum):
    """Enum for player action types."""

    OBSERVE = "OBSERVE"
    TALK = "TALK"
    INTERACT = "INTERACT"
    MOVE_IN = "MOVE_IN"
    MOVE_OUT = "MOVE_OUT"


class Direction(Enum):
    """Enum for movement directions with associated properties."""

    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"

    @property
    def opposite(self) -> "Direction":
        """Get the opposite direction."""
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        }
        return opposites[self]

    @property
    def translation(self) -> tuple[int, int]:
        """Get the coordinate translation for this direction."""
        translations = {
            Direction.NORTH: (0, 1),
            Direction.SOUTH: (0, -1),
            Direction.EAST: (1, 0),
            Direction.WEST: (-1, 0),
        }
        return translations[self]


class PlayerType(Enum):
    """Enum for player types."""

    HUMAN = "HUMAN"
    NPC = "NPC"


class DecisionType(Enum):
    """Enum for decision types that controllers handle."""

    MOVE = "MOVE"
    ACT = "ACT"

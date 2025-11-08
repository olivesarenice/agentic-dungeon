"""
Event dataclasses for tracking game events.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class GameEvent:
    """A structured log of an event that occurred in the game."""

    timestamp: str  # ISO format timestamp
    room_id: str
    actor_id: str  # these can only be players
    actor_name: str
    action_type: str  # e.g., "TALK", "INTERACT", "MOVE_IN", "MOVE_OUT"
    content: str  # e.g., "Hello, anyone here?", "Pulls a lever"

    @staticmethod
    def create_move_out_event(
        room_id: str, actor_id: str, actor_name: str
    ) -> "GameEvent":
        """Create a MOVE_OUT event."""
        return GameEvent(
            timestamp=datetime.now().isoformat(),
            room_id=room_id,
            actor_id=actor_id,
            actor_name=actor_name,
            action_type="MOVE_OUT",
            content=f"{actor_name} left the room.",
        )

    @staticmethod
    def create_move_in_event(
        room_id: str, actor_id: str, actor_name: str
    ) -> "GameEvent":
        """Create a MOVE_IN event."""
        return GameEvent(
            timestamp=datetime.now().isoformat(),
            room_id=room_id,
            actor_id=actor_id,
            actor_name=actor_name,
            action_type="MOVE_IN",
            content=f"{actor_name} entered the room.",
        )

    @staticmethod
    def create_action_event(
        room_id: str, actor_id: str, actor_name: str, action_type: str, content: str
    ) -> "GameEvent":
        """Create an action event (TALK, INTERACT, etc.)."""
        return GameEvent(
            timestamp=datetime.now().isoformat(),
            room_id=room_id,
            actor_id=actor_id,
            actor_name=actor_name,
            action_type=action_type,
            content=content,
        )

"""
Memory-related dataclasses and classes for player memory management.
"""

from dataclasses import dataclass, field
from typing import Optional

from .events import GameEvent


@dataclass
class PlayerEntry:
    """Entry in a player's memory about another player."""

    name: str
    description: str  # description of the player as remembered by the agent
    last_seen_room_id: str  # the room where the player was last encountered
    interaction_history: list[GameEvent] = field(
        default_factory=list
    )  # Direct interactions (e.g., TALK)

    def update_description(self, new_description: str) -> None:
        """Update the description of the player."""
        self.description = new_description


@dataclass
class RoomEntry:
    """Entry in a player's memory about a room."""

    id: str
    name: str  # from the room itself
    description: str  # description of the room as remembered by the player
    observed_events: list[GameEvent] = field(
        default_factory=list
    )  # Events witnessed in this room

    def update_description(self, new_description: str) -> None:
        """Update the description of the room."""
        self.description = new_description


class Memory:
    """
    The agent's mental model of the game world from their perspective.
    Uses regular dicts with explicit handling instead of defaultdict to prevent
    accidental creation of empty entries.
    """

    def __init__(self):
        self.known_players: dict[str, PlayerEntry] = {}
        self.known_rooms: dict[str, RoomEntry] = {}
        self.preferences: dict[str, str] = {}

    def get_player(self, player_name: str) -> Optional[PlayerEntry]:
        """Safely get a player entry."""
        return self.known_players.get(player_name)

    def add_player(self, player_entry: PlayerEntry) -> None:
        """Add or update a player entry."""
        self.known_players[player_entry.name] = player_entry

    def has_player(self, player_name: str) -> bool:
        """Check if player is known."""
        return player_name in self.known_players

    def get_room(self, room_id: str) -> Optional[RoomEntry]:
        """Safely get a room entry."""
        return self.known_rooms.get(room_id)

    def add_room(self, room_entry: RoomEntry) -> None:
        """Add or update a room entry."""
        self.known_rooms[room_entry.id] = room_entry

    def has_room(self, room_id: str) -> bool:
        """Check if room is known."""
        return room_id in self.known_rooms

"""
Room class and related dataclasses.
"""

from dataclasses import dataclass

import fictional_names
import fictional_names.name_generator
from FantasyNameGenerator.Stores import Town


class Room:
    """Represents a room in the game world."""

    def __init__(self, coords: tuple[int, int], description: str = ""):
        self.id, self.name = self.new_details()
        self.coords = coords
        self.paths: dict[str, str] = {}  # {"N":room_id, "S":room_id}
        self.players_inside: set[str] = set()  # {player_id}
        self.description = description
        # Note: Room creation message removed - it was printing on every DB load

    @staticmethod
    def new_details() -> tuple[str, str]:
        """Generate a unique room ID and name."""
        fantasy_name_component = (
            fictional_names.name_generator.generate_name(
                style="dwarven", library=False
            ).split(" ")[0]
            + "'s"
        )

        location = Town.generate()

        name = f"{fantasy_name_component} {location}"
        id_slug = f"{fantasy_name_component.replace("'", "").lower()}-{location.replace(" ", "-").lower()}"
        return id_slug, name

    def update_description(self, new_description: str) -> None:
        """Update the room's description."""
        self.description = new_description
        print(f"Room {self.name} updated: {self.description}.")


@dataclass
class Connection:
    """Represents a connection between rooms."""

    direction: str
    # Other attributes can be added here as needed

"""
Room class and related dataclasses.
"""

from dataclasses import dataclass

import fictional_names
import fictional_names.name_generator
from FantasyNameGenerator.Stores import Town


class Room:
    """Represents a room in the game world."""

    def __init__(
        self,
        coords: tuple[int, int],
        description: str = "",
        name: str = None,
        room_id: str = None,
    ):
        if name and room_id:
            self.id = room_id
            self.name = name
        else:
            self.id, self.name = self.new_details()
        self.coords = coords
        self.paths: dict[str, str] = {}  # {"N":room_id, "S":room_id}
        self.players_inside: set[str] = set()  # {player_id}
        self.description = description
        self.image_filepath: str | None = None  # Path to generated scene image

        # V3: Treasure hunt attributes
        self.has_treasure: bool = False
        self.is_starting_room: bool = False

        # Note: Room creation message removed - it was printing on every DB load

    @staticmethod
    def new_details() -> tuple[str, str]:
        """Generate a unique room ID and name (fallback method)."""
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

    @staticmethod
    def generate_id_from_name(name: str) -> str:
        """Generate a URL-safe ID slug from a room name."""
        import re
        import uuid

        # Convert to lowercase and replace spaces/special chars with hyphens
        slug = re.sub(r"[^\w\s-]", "", name.lower())
        slug = re.sub(r"[-\s]+", "-", slug).strip("-")

        # Add a short unique suffix to ensure uniqueness
        unique_suffix = str(uuid.uuid4())[:8]
        return f"{slug}-{unique_suffix}"

    def update_description(self, new_description: str) -> None:
        """Update the room's description."""
        self.description = new_description
        print(f"Room {self.name} updated: {self.description}.")


@dataclass
class Connection:
    """Represents a connection between rooms."""

    direction: str
    # Other attributes can be added here as needed

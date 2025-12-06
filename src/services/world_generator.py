"""
World generator for creating and managing rooms using database persistence.
"""

import random
from typing import Optional

from sqlalchemy.orm import Session

from config import GameConfigs
from config.constants import GameConstants
from llm import LLMModule, PromptTemplates, create_llm_module
from models import Room
from repositories import RoomRepository, WorldRepository


class WorldGenerator:
    """
    Handles world generation including room creation and connections.
    Uses database for persistence.
    """

    def __init__(self, session: Session, world_id: str):
        """
        Initialize world generator with database session.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this generator operates on
        """
        self.session = session
        self.world_id = world_id
        self.room_repo = RoomRepository(session, world_id)

        # Get world theme
        world_repo = WorldRepository(session)
        db_world = world_repo.get(world_id)
        self.world_theme = db_world.theme if db_world and db_world.theme else None

        # LLM for room descriptions - include world theme in system prompt
        dm_system_prompt = PromptTemplates.DM_SYSTEM_PROMPT
        if self.world_theme:
            dm_system_prompt = f"{dm_system_prompt}\n\nIMPORTANT: This world has the following theme/setting:\n{self.world_theme}\n\nAll room names and descriptions should fit this theme."

        self.dm_generator_module: LLMModule = create_llm_module(dm_system_prompt)

    def _translate(
        self, current_coords: tuple[int, int], move_direction: str
    ) -> tuple[int, int]:
        """
        Translate coordinates in a given direction.

        Time Complexity: O(1)
        """
        translation = GameConfigs._moves[move_direction].translate
        new_coords = (
            current_coords[0] + translation[0],
            current_coords[1] + translation[1],
        )
        return new_coords

    def _get_adjacent_rooms(self, room: Room) -> dict[str, Optional[Room]]:
        """
        Get all adjacent rooms to a given room.

        Time Complexity: O(1) - fixed number of directions
        """
        adjacent_coords = {
            d: self._translate(room.coords, d) for d in GameConfigs._moves.keys()
        }
        rooms = {}
        for d, c in adjacent_coords.items():
            adjacent_room = self.room_repo.get_by_coords(c[0], c[1])
            rooms[d] = adjacent_room
        return rooms

    def create_room(
        self,
        coords: tuple[int, int],
        from_room: Optional[Room] = None,
        from_direction: Optional[str] = None,
    ) -> Room:
        """
        Create a new room with connections.

        Args:
            coords: Coordinates for the new room
            from_room: Room this was created from (if any)
            from_direction: Direction from the from_room to this room

        Returns:
            The created Room

        Time Complexity: O(1)
        The number of adjacent rooms and potential paths is constant (max 4).
        """
        print(
            f"Creating room at {coords} from room {from_room.id if from_room else 'None'}"
        )

        # Get adjacent rooms info before creating the room (we need coords but not a full Room object yet)
        # Temporarily create a basic room object just to get adjacent room info
        temp_room = Room(coords)
        adjacent_rooms = self._get_adjacent_rooms(temp_room)

        # Generate room name with LLM using adjacent room context
        # Add randomness: 30% chance to introduce a completely new biome/discovery
        import random

        should_introduce_new_biome = random.random() < 0.3  # 30% chance

        adjacent_hints = []
        for direction, aroom in adjacent_rooms.items():
            if aroom:
                adjacent_hints.append(f"{direction.upper()}: connects to {aroom.name}")

        if adjacent_hints:
            adjacent_context = "Connected areas: " + ", ".join(adjacent_hints)
            if should_introduce_new_biome:
                adjacent_context += "\n\nSPECIAL: This room opens up into a COMPLETELY NEW area - introduce a surprising discovery or biome shift! Examples: sudden cavern, hidden garden, trapped library, crystal chamber, etc."
        else:
            adjacent_context = "This is the first room in an unexplored area"

        name_prompt = PromptTemplates.WORLD_GEN_ROOM_NAME.substitute(
            adjacent_rooms=adjacent_context
        )
        generated_name = self.dm_generator_module.get_response(name_prompt).strip()
        # Remove quotes if the LLM added them
        generated_name = generated_name.strip('"').strip("'")

        # Generate ID from the name
        room_id = Room.generate_id_from_name(generated_name)

        # Create the room with the generated name and ID
        room = Room(coords, name=generated_name, room_id=room_id)
        paths = {}

        # Add connection from the room this was created from
        if from_room is not None and from_direction is not None:
            paths[from_direction] = from_room.id

        # Prioritize connections to adjacent rooms that are already pointing here
        for d, aroom in adjacent_rooms.items():
            if len(paths) >= GameConstants.MAX_ROOM_PATHS:
                break
            if d in paths:
                continue
            if aroom:
                pole = GameConfigs._moves[d].pole
                if pole in aroom.paths and aroom.paths[pole] is None:
                    paths[d] = aroom.id

        # Fill remaining path slots randomly from other valid potential paths
        if len(paths) < GameConstants.MAX_ROOM_PATHS:
            potential_paths = {}
            for d, aroom in adjacent_rooms.items():
                if d in paths:
                    continue
                if aroom is None:
                    potential_paths[d] = None
                    continue
                if len(aroom.paths) < GameConstants.MAX_ROOM_PATHS:
                    potential_paths[d] = aroom.id
                    continue

            remaining_slots = GameConstants.MAX_ROOM_PATHS - len(paths)
            num_to_sample = min(len(potential_paths), remaining_slots)

            if num_to_sample > 0:
                new_path_directions = random.sample(
                    list(potential_paths.keys()), num_to_sample
                )
                new_paths = {d: potential_paths[d] for d in new_path_directions}
                paths.update(new_paths)

        print(f"New paths for room {room.id}: {paths}")

        # Generate room description using LLM with surrounding room context
        path_descriptions = {
            d: desc if desc is not None else "unknown" for d, desc in paths.items()
        }

        # Gather adjacent room information for continuity
        adjacent_hints = []
        for direction, aroom in adjacent_rooms.items():
            if aroom and aroom.description:
                # Provide room name AND description snippet for better context
                # Use more of the description to convey biome themes clearly
                desc_snippet = (
                    aroom.description[:150] + "..."
                    if len(aroom.description) > 150
                    else aroom.description
                )
                adjacent_hints.append(
                    f"{direction.upper()}: '{aroom.name}' - {desc_snippet}"
                )

        # Format adjacent context string with descriptions
        if adjacent_hints:
            adjacent_context = "Adjacent rooms:\n" + "\n".join(adjacent_hints)
            # Add the same biome shift hint if it was triggered
            if should_introduce_new_biome:
                adjacent_context += "\n\nSPECIAL: This room reveals a COMPLETELY NEW discovery - describe a dramatic shift or surprising new element! Think: hidden waterfall, ancient vault, mushroom forest, trapped civilization, etc."
        else:
            adjacent_context = "This is the first room in unexplored territory - create something vivid and memorable!"

        prompt = PromptTemplates.WORLD_GEN_ROOM_DESCRIPTION.substitute(
            word_count=GameConstants.DEFAULT_DESCRIPTION_WORDS,
            room_name=room.name,
            room_paths=path_descriptions,
            adjacent_rooms=adjacent_context,
        )
        description = self.dm_generator_module.get_response(prompt)
        room.update_description(description)
        room.paths = paths

        # Save room to database
        self.room_repo.add(room)

        # Update paths of connected rooms
        for d, room_id in room.paths.items():
            if room_id:
                aroom = self.room_repo.get(room_id)
                if aroom:
                    aroom.paths[GameConfigs._moves[d].pole] = room.id

                    prompt = PromptTemplates.WORLD_GEN_ROOM_CONNECTION.substitute(
                        room_name=aroom.name,
                        new_room_name=room.name,
                        direction=GameConfigs._moves[d].pole,
                        current_description=aroom.description,
                    )
                    new_description = self.dm_generator_module.get_response(prompt)

                    print(
                        f"\033[92m"
                        f"""
                    Adjacent room {aroom.name} updated:
                    FROM = {aroom.description}.
                    
                    TO = {new_description}"""
                        f"\033[0m\n"
                    )

                    aroom.update_description(new_description)
                    # Update in database
                    self.room_repo.update(aroom)

        return room

    def create_world(self, starting_room_coords: tuple[int, int] = (0, 0)) -> Room:
        """
        Create the starting room for the world.

        Args:
            starting_room_coords: Coordinates for the starting room

        Returns:
            The starting room

        Time Complexity: O(1)
        """
        print("Creating world...")
        starting_room = self.create_room(starting_room_coords)
        print("World created.")
        return starting_room

    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID from database."""
        return self.room_repo.get(room_id)

    def get_room_at_coords(self, coords: tuple[int, int]) -> Optional[Room]:
        """Get a room at specific coordinates from database."""
        return self.room_repo.get_by_coords(coords[0], coords[1])

    def room_exists_at_coords(self, coords: tuple[int, int]) -> bool:
        """Check if a room exists at coordinates."""
        return self.room_repo.get_by_coords(coords[0], coords[1]) is not None

    def get_all_room_ids(self) -> list[str]:
        """Get list of all room IDs from database."""
        return self.room_repo.get_all_ids()

    def get_rooms_dict(self) -> dict[str, Room]:
        """Get dictionary of all rooms from database."""
        rooms = self.room_repo.get_all()
        return {room.id: room for room in rooms}

    def get_map_dict(self) -> dict[tuple[int, int], str]:
        """Get coordinate to room_id mapping from database."""
        return self.room_repo.get_map()

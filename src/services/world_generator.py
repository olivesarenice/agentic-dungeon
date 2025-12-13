"""
World generator for creating and managing rooms using database persistence.
"""

import random
from typing import Optional

from sqlalchemy.orm import Session

from config import GameConfigs
from config.constants import GameConstants, ImageGenerationConstants
from llm import LLMModule, PromptTemplates, create_quality_llm
from llm.text2img_module import Text2ImageGenerator, create_text2img_generator
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

        # Get world theme and art style
        world_repo = WorldRepository(session)
        db_world = world_repo.get(world_id)
        self.world_theme = db_world.theme if db_world and db_world.theme else None
        self.world_art_style = (
            db_world.art_style if db_world and db_world.art_style else "retro_anime"
        )

        # Debug logging
        print(f"[WORLD_GEN] World ID: {world_id}")
        print(f"[WORLD_GEN] DB World found: {db_world is not None}")
        if db_world:
            print(f"[WORLD_GEN] DB World theme: {repr(db_world.theme)}")
            print(f"[WORLD_GEN] DB World art_style: {repr(db_world.art_style)}")
        print(f"[WORLD_GEN] Using theme: {repr(self.world_theme)}")
        print(f"[WORLD_GEN] Using art_style: {repr(self.world_art_style)}")

        # LLM for room descriptions - include world theme in system prompt
        # Use QUALITY model for creative room generation
        dm_system_prompt = PromptTemplates.DM_SYSTEM_PROMPT
        if self.world_theme:
            dm_system_prompt = f"{dm_system_prompt}\n\nIMPORTANT: This world has the following theme/setting:\n{self.world_theme}\n\nAll room names and descriptions should fit this theme."
            print(f"[WORLD_GEN] Added theme to system prompt")
        else:
            print(f"[WORLD_GEN] No theme - using default system prompt")

        # Debug: Print the actual system prompt being used
        print(f"[WORLD_GEN] System prompt length: {len(dm_system_prompt)} chars")
        print(f"[WORLD_GEN] System prompt preview: {dm_system_prompt[:200]}...")
        if self.world_theme and self.world_theme in dm_system_prompt:
            print(
                f"[WORLD_GEN] ✓ Theme '{self.world_theme}' confirmed in system prompt"
            )
        elif self.world_theme:
            print(
                f"[WORLD_GEN] ✗ WARNING: Theme '{self.world_theme}' NOT found in system prompt!"
            )

        self.dm_generator_module: LLMModule = create_quality_llm(dm_system_prompt)

        # Initialize text-to-image generator if enabled
        self.image_generator: Optional[Text2ImageGenerator] = None
        if ImageGenerationConstants.ENABLED:
            try:
                self.image_generator = create_text2img_generator(
                    output_dir=ImageGenerationConstants.OUTPUT_DIR
                )
                print("Image generation enabled")
            except Exception as e:
                print(f"Warning: Could not initialize image generator: {e}")
                print("Continuing without image generation...")

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

    def _generate_room_scene_image(
        self, room: Room, reference_image_path: Optional[str] = None
    ) -> None:
        """
        Generate a scene image for the room and update the room's image_filepath.

        Args:
            room: The room to generate an image for
            reference_image_path: Optional path to existing image for grounding/consistency
        """
        if not self.image_generator:
            return

        try:
            # Get the art style for this world
            art_style = ImageGenerationConstants.ART_STYLES.get(
                self.world_art_style, ImageGenerationConstants.ART_STYLES["retro_anime"]
            )

            # Use the generate_room_scene method which handles optimization
            image_path = self.image_generator.generate_room_scene(
                room_name=room.name,
                room_description=room.description,
                player_info="Draw the scene WITHOUT any people or characters. Show only the environment and location.",
                art_style=art_style,
                room_id=room.id,
                reference_image_path=reference_image_path,
                use_optimization=ImageGenerationConstants.USE_PROMPT_OPTIMIZATION,
            )

            # Update room with image path
            room.image_filepath = image_path

            # Persist to database
            self.room_repo.update(room)

            if reference_image_path:
                print(
                    f"✨ Updated scene image for {room.name} (with grounding): {image_path}"
                )
            else:
                print(f"✨ Generated scene image for {room.name}: {image_path}")

        except Exception as e:
            print(f"Warning: Could not generate image for room {room.name}: {e}")
            # Continue without image

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
        # Use temperature=1.0 for maximum creativity in room names
        generated_name = self.dm_generator_module.get_response(
            name_prompt, temperature=1.0
        ).strip()
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

        # Generate scene image for the new room
        self._generate_room_scene_image(room)

        # Update paths of connected rooms (but don't regenerate descriptions/images)
        for d, room_id in room.paths.items():
            if room_id:
                aroom = self.room_repo.get(room_id)
                if aroom:
                    # Just update the path connection
                    aroom.paths[GameConfigs._moves[d].pole] = room.id
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

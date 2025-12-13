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
        direction_from_parent: Optional[str] = None,
        generate_image: bool = True,
    ) -> Room:
        """
        V3 Optimized: Create a room in sequential BFS generation.
        Simplified for grid world where all rooms are pre-generated.

        Args:
            coords: Coordinates for the new room
            from_room: Room this was created from (if any)
            direction_from_parent: Direction from parent TO this room (e.g., "S" = this room is South of parent)
            generate_image: Whether to generate image immediately (False for batch generation)

        Returns:
            The created Room
        """
        print(
            f"Creating room at {coords} from {from_room.name if from_room else 'START'} going {direction_from_parent or 'N/A'}"
        )

        # Get adjacent rooms for context (for LLM description generation)
        temp_room = Room(coords)
        adjacent_rooms = self._get_adjacent_rooms(temp_room)

        # V3: Simple bidirectional connection logic for BFS
        paths = {}

        if from_room is not None and direction_from_parent is not None:
            # Set up BACKWARD connection (from this room back to parent)
            # If parent went S to reach us, we go N to return
            opposite_direction = GameConfigs._moves[direction_from_parent].pole
            paths[opposite_direction] = from_room.id
            print(f"  → Backward path: {opposite_direction} → {from_room.name}")

        # Generate name AND description in single LLM call
        generated_name, description = self._generate_room_name_and_description(
            coords, from_room, adjacent_rooms, paths
        )

        # Create the room
        room_id = Room.generate_id_from_name(generated_name)
        room = Room(coords, name=generated_name, room_id=room_id)
        room.update_description(description)
        room.paths = paths

        print(f"  ✓ Created: {room.name} with paths {list(paths.keys())}")

        # Save room to database
        self.room_repo.add(room)

        # Generate image (optional - can be batched)
        if generate_image:
            self._generate_room_scene_image(room)

        # V3: Set up FORWARD connection in parent room
        if from_room is not None and direction_from_parent is not None:
            from_room.paths[direction_from_parent] = room.id
            self.room_repo.update(from_room)
            print(
                f"  ✓ Forward path: {from_room.name} → {direction_from_parent} → {room.name}"
            )

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

    def create_organic_labyrinth(
        self, max_rooms: int, starting_coords: tuple[int, int] = None
    ) -> Room:
        """
        V3 Organic: Create a natural, winding labyrinth with specified number of rooms.
        Uses random branching instead of filling a perfect grid.

        Args:
            max_rooms: Target number of rooms (e.g., 4, 16, 25)
            starting_coords: Starting coordinates (defaults to origin)

        Returns:
            The starting room
        """
        from collections import deque

        if starting_coords is None:
            starting_coords = (0, 0)

        print(f"\n🌿 Creating organic labyrinth with {max_rooms} rooms...")
        print(f"   Starting at: {starting_coords}")
        print(f"\n📝 Phase 1: Generating labyrinth structure...\n")

        # Step 1: Create starting room
        starting_room = self._create_simple_room(starting_coords, None, None)
        starting_room.is_starting_room = True
        self.room_repo.update(starting_room)

        all_rooms = [starting_room]
        occupied_coords = {starting_coords}

        # Queue: (coords, parent_room, came_from_direction, depth)
        queue = deque([(starting_coords, starting_room, None, 0)])
        room_count = 1

        # Step 2: Organically grow the labyrinth
        while queue and room_count < max_rooms:
            current_coords, current_room, came_from, depth = queue.popleft()

            # Reload room to get latest paths
            current_room = self.room_repo.get_by_coords(
                current_coords[0], current_coords[1]
            )

            print(f"\n{'='*70}")
            print(f"GROWING FROM ROOM #{room_count}")
            print(f"Room: '{current_room.name}' at {current_coords} (depth {depth})")
            print(f"Current paths: {dict(current_room.paths)}")
            print(f"{'='*70}")

            # Determine number of exits for this room (organic branching)
            available_directions = [d for d in ["N", "S", "E", "W"] if d != came_from]
            num_exits = self._decide_branch_count(
                depth, room_count, max_rooms, available_directions
            )

            # Randomly select which directions to branch
            if num_exits > 0:
                random.shuffle(available_directions)
                selected_directions = available_directions[:num_exits]
            else:
                selected_directions = []

            print(f"Branching to {num_exits} direction(s): {selected_directions}")

            # Try selected directions
            for direction in selected_directions:
                if room_count >= max_rooms:
                    break

                next_coords = self._translate(current_coords, direction)

                print(f"\nDirection {direction} → {next_coords}:", end=" ")

                # Check if coordinates already occupied
                if next_coords in occupied_coords:
                    print("ALREADY OCCUPIED")
                    continue

                # Create new room
                print("CREATING...")

                # Get opposite direction for backward connection
                opposite = GameConfigs._moves[direction].pole

                # Create new room
                new_room = self._create_simple_room(next_coords, current_room, opposite)
                room_count += 1
                all_rooms.append(new_room)

                # Connect: parent → direction → child
                current_room.paths[direction] = new_room.id
                self.room_repo.update(current_room)
                self.session.commit()

                print(f"  ✓ Created '{new_room.name}'")
                print(f"  ✓ {current_room.name} → {direction} → {new_room.name}")

                occupied_coords.add(next_coords)
                queue.append((next_coords, new_room, opposite, depth + 1))

        print(f"\n✅ Generated {len(all_rooms)} rooms in organic labyrinth\n")

        # Step 3: Batch generate images
        if self.image_generator:
            print(f"🎨 Phase 2: Generating images for {len(all_rooms)} rooms...")
            self._batch_generate_images(all_rooms)
            print(f"✅ All images generated!\n")

        # Reload and return starting room
        return self.room_repo.get_by_coords(starting_coords[0], starting_coords[1])

    def _decide_branch_count(
        self, depth: int, current_count: int, max_rooms: int, available_dirs: list
    ) -> int:
        """
        Decide how many branches to create from current room.
        Creates organic, winding paths with controlled branching.

        Args:
            depth: Current depth from starting room
            current_count: Number of rooms created so far
            max_rooms: Target total rooms
            available_dirs: Available directions (excluding where we came from)

        Returns:
            Number of branches to create (0-4)
        """
        rooms_remaining = max_rooms - current_count

        # Don't branch if we're at max
        if rooms_remaining <= 0:
            return 0

        # SPECIAL: Starting room (depth 0) ALWAYS branches in all 4 directions
        if depth == 0:
            return min(4, len(available_dirs), rooms_remaining)

        # Early in generation: higher branch probability for spreading out
        if current_count < max_rooms * 0.3:
            # 40% chance of 2-3 branches, 50% chance of 1 branch, 10% dead end
            r = random.random()
            if r < 0.15:
                return min(3, len(available_dirs), rooms_remaining)
            elif r < 0.40:
                return min(2, len(available_dirs), rooms_remaining)
            elif r < 0.90:
                return min(1, rooms_remaining)
            else:
                return 0  # Dead end

        # Mid generation: balanced
        elif current_count < max_rooms * 0.7:
            # 60% single branch, 25% double branch, 15% dead end
            r = random.random()
            if r < 0.25:
                return min(2, len(available_dirs), rooms_remaining)
            elif r < 0.85:
                return min(1, rooms_remaining)
            else:
                return 0

        # Late generation: mostly linear to finish up
        else:
            # 80% single branch, 20% dead end
            if random.random() < 0.80:
                return min(1, rooms_remaining)
            else:
                return 0

    def create_grid_world(
        self, grid_size: int, starting_coords: tuple[int, int] = None
    ) -> Room:
        """
        V3: Create complete NxN grid of connected rooms.
        DEPRECATED: Use create_organic_labyrinth() for more natural dungeons.

        Args:
            grid_size: Size of the grid (2, 3, or 4)
            starting_coords: Starting coordinates (defaults to center)

        Returns:
            The starting room
        """
        from collections import deque

        if starting_coords is None:
            center = grid_size // 2
            starting_coords = (center, center)

        print(f"\n🏗️  Creating {grid_size}x{grid_size} grid world...")
        print(f"   Starting at: {starting_coords}")
        print(f"\n📝 Phase 1: Generating rooms and connections...\n")

        # Step 1: Create starting room
        starting_room = self._create_simple_room(starting_coords, None, None)
        starting_room.is_starting_room = True
        self.room_repo.update(starting_room)

        all_rooms = [starting_room]
        visited = {starting_coords}
        queue = deque([starting_coords])
        room_count = 1

        # Step 2: BFS to create all connected rooms
        while queue:
            current_coords = queue.popleft()

            # Reload current room from DB to get latest paths
            current_room = self.room_repo.get_by_coords(
                current_coords[0], current_coords[1]
            )

            print(f"\n{'='*70}")
            print(f"PROCESSING ROOM #{room_count}")
            print(f"Room: '{current_room.name}' at {current_coords}")
            print(f"Current paths: {dict(current_room.paths)}")
            print(f"{'='*70}")

            # Try all 4 directions
            for direction in ["N", "S", "E", "W"]:
                next_coords = self._translate(current_coords, direction)
                x, y = next_coords

                print(f"\nDirection {direction} → {next_coords}:", end=" ")

                # Check bounds
                if not (0 <= x < grid_size and 0 <= y < grid_size):
                    print("OUT OF BOUNDS")
                    continue

                # Check if already visited
                if next_coords in visited:
                    print("ALREADY VISITED")
                    continue

                # Create new room
                print("CREATING...")

                # Get opposite direction for backward connection
                opposite = GameConfigs._moves[direction].pole

                # Create new room
                new_room = self._create_simple_room(next_coords, current_room, opposite)
                room_count += 1
                all_rooms.append(new_room)

                # Connect: parent → direction → child
                current_room.paths[direction] = new_room.id
                self.room_repo.update(current_room)

                # Force commit to ensure changes are persisted
                self.session.commit()

                # Verify it was saved
                verification = self.room_repo.get_by_coords(
                    current_coords[0], current_coords[1]
                )
                print(f"  ✓ Created '{new_room.name}'")
                print(f"  ✓ {current_room.name} → {direction} → {new_room.name}")
                print(f"  ✓ {new_room.name} → {opposite} → {current_room.name}")
                print(f"  ✓ Parent in-memory paths: {dict(current_room.paths)}")
                print(f"  ✓ Parent DB paths: {dict(verification.paths)}")

                visited.add(next_coords)
                queue.append(next_coords)

        print(f"\n✅ Generated {len(all_rooms)} rooms\n")

        # Step 3: Batch generate images
        if self.image_generator:
            print(f"🎨 Phase 2: Generating images for {len(all_rooms)} rooms...")
            self._batch_generate_images(all_rooms)
            print(f"✅ All images generated!\n")

        # Reload and return starting room
        return self.room_repo.get_by_coords(starting_coords[0], starting_coords[1])

    def _create_simple_room(
        self,
        coords: tuple[int, int],
        from_room: Optional[Room],
        backward_direction: Optional[str],
    ) -> Room:
        """
        Create a room with optional backward connection to parent.

        Args:
            coords: Room coordinates
            from_room: Parent room (if any)
            backward_direction: Direction from child back to parent (e.g., "N" means go North to return)

        Returns:
            Created room
        """
        # Get adjacent rooms for LLM context
        temp_room = Room(coords)
        adjacent_rooms = self._get_adjacent_rooms(temp_room)

        # Set up backward connection if this is a child room
        paths = {}
        if from_room and backward_direction:
            paths[backward_direction] = from_room.id

        # Generate name and description
        name, description = self._generate_room_name_and_description(
            coords, from_room, adjacent_rooms, paths
        )

        # Create room object
        room_id = Room.generate_id_from_name(name)
        room = Room(coords, name=name, room_id=room_id)
        room.update_description(description)
        room.paths = paths

        # Save to database
        self.room_repo.add(room)

        return room

    def _batch_generate_images(self, rooms: list[Room]) -> None:
        """
        Generate images for multiple rooms in parallel for efficiency.

        Args:
            rooms: List of rooms to generate images for
        """
        import concurrent.futures
        from threading import Lock

        # Thread-safe counter for progress
        progress = {"completed": 0}
        lock = Lock()

        def generate_single_image(room: Room) -> None:
            """Generate image for a single room."""
            try:
                self._generate_room_scene_image(room)
                with lock:
                    progress["completed"] += 1
                    print(
                        f"   [{progress['completed']}/{len(rooms)}] Generated image for: {room.name}"
                    )
            except Exception as e:
                print(f"   ⚠️  Failed to generate image for {room.name}: {e}")

        # Use ThreadPoolExecutor for parallel image generation
        # Max 5 concurrent requests to avoid rate limiting
        max_workers = min(5, len(rooms))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all image generation tasks
            futures = [executor.submit(generate_single_image, room) for room in rooms]

            # Wait for all to complete
            concurrent.futures.wait(futures)

    def place_treasures(self, grid_size: int, session) -> None:
        """
        V3: Place treasures in random rooms by identifying objects in existing descriptions.
        Number of treasures = grid_size (3, 5, or 7)

        Does NOT modify room descriptions to preserve description/image match.

        Args:
            grid_size: Size of grid (determines number of treasures)
            session: Database session for adding items
        """
        import random
        import uuid

        from database.models import DBItem

        num_treasures = grid_size
        print(f"🎯 Hiding {num_treasures} treasures...")

        # Get all rooms except starting room
        rooms_dict = self.get_rooms_dict()
        available_rooms = [r for r in rooms_dict.values() if not r.is_starting_room]

        if len(available_rooms) < num_treasures:
            num_treasures = len(available_rooms)

        # Randomly select rooms for treasures
        treasure_rooms = random.sample(available_rooms, num_treasures)

        for i, room in enumerate(treasure_rooms):
            # Generate treasure name
            treasure_name = self._generate_treasure_name(i + 1)

            # Identify an object in the EXISTING description to hide treasure
            # WITHOUT modifying the description
            hint_object = self._identify_treasure_container(room, treasure_name)

            # Create item record with the hint object from LLM
            item = DBItem(
                id=str(uuid.uuid4()),
                world_id=self.world_id,
                room_id=room.id,
                name=treasure_name,
                description=f"A precious artifact radiating mysterious power",
                item_type="TREASURE",
                interaction_hint=hint_object,
            )
            session.add(item)

            # Mark room as having treasure (but don't modify description!)
            room.has_treasure = True
            self.room_repo.update(room)

            print(f"   ✓ '{treasure_name}' hidden in '{room.name}'")
            print(f"      Hint: {hint_object}")

        session.commit()
        print(f"✅ All treasures hidden!\n")

    def _generate_room_name_and_description(
        self,
        coords: tuple[int, int],
        from_room: Optional[Room],
        adjacent_rooms: dict[str, Optional[Room]],
        paths: dict[str, Optional[str]],
    ) -> tuple[str, str]:
        """
        Generate both room name and description in a single LLM call.

        Returns:
            (room_name, room_description)
        """
        import random

        # 30% chance for new biome
        should_introduce_new_biome = random.random() < 0.3

        # Gather context from adjacent rooms
        adjacent_hints = []
        for direction, aroom in adjacent_rooms.items():
            if aroom:
                if aroom.description:
                    desc_snippet = (
                        aroom.description[:150] + "..."
                        if len(aroom.description) > 150
                        else aroom.description
                    )
                    adjacent_hints.append(
                        f"{direction.upper()}: '{aroom.name}' - {desc_snippet}"
                    )
                else:
                    adjacent_hints.append(
                        f"{direction.upper()}: connects to {aroom.name}"
                    )

        if adjacent_hints:
            context = "Adjacent rooms:\n" + "\n".join(adjacent_hints)
            if should_introduce_new_biome:
                context += (
                    "\n\nSPECIAL: Introduce a surprising new discovery or biome shift!"
                )
        else:
            context = "This is the first room - create something memorable!"

        prompt = f"""Generate a dungeon room name and description.

CONTEXT:
{context}

INSTRUCTIONS:
1. Create an evocative 2-4 word room name
2. Write a {GameConstants.DEFAULT_DESCRIPTION_WORDS}-word atmospheric description
3. Match the theme and connect naturally with adjacent rooms

OUTPUT FORMAT (Python tuple):
("Room Name Here", "Description here with all the atmospheric details...")

Generate the room:"""

        response = self.dm_generator_module.get_response(
            prompt, temperature=1.0
        ).strip()

        # Parse tuple format
        try:
            # Try to evaluate as Python tuple
            result = eval(response)
            if isinstance(result, tuple) and len(result) == 2:
                name, description = result
                return str(name).strip(), str(description).strip()
        except:
            pass

        # Fallback parsing if tuple format fails
        if '"' in response or "'" in response:
            parts = response.split(",", 1)
            if len(parts) == 2:
                name = parts[0].strip("(\"'").strip()
                description = parts[1].strip(")\"'").strip()
                return name, description

        # Last resort fallback
        lines = response.strip().split("\n")
        name = lines[0].strip('"').strip("'").strip("()").strip()
        description = " ".join(lines[1:]) if len(lines) > 1 else "A mysterious chamber."
        return name, description

    def _generate_treasure_name(self, number: int) -> str:
        """Generate a themed treasure name using LLM."""
        theme_context = (
            f"in a {self.world_theme} themed dungeon" if self.world_theme else ""
        )

        prompt = f"""Generate a unique, evocative treasure name {theme_context}.

Examples:
- Crown of the Ancient Kings
- Orb of Eternal Light
- Shard of the Fallen Star
- Chalice of Endless Dreams

Generate ONE treasure name (2-5 words):"""

        name = self.dm_generator_module.get_response(prompt, temperature=1.0).strip()
        return name.strip('"').strip("'").strip()

    def _identify_treasure_container(self, room: Room, treasure_name: str) -> str:
        """
        Identify an object in the existing room description that could contain the treasure.
        Does NOT modify the description.

        Returns:
            Object name that contains the treasure
        """
        prompt = f"""Look at this room description and identify ONE object that could logically contain a hidden treasure.

ROOM:
Name: {room.name}
Description: {room.description}

TREASURE:
{treasure_name}

INSTRUCTIONS:
1. Choose an existing object mentioned in the description
2. It should be something that could realistically hide/contain a treasure
3. Examples: chest, box, altar, statue, pedestal, vase, urn, etc.
4. Return ONLY the object name (2-4 words maximum)
5. Make it something a player would naturally want to interact with

Object that contains the treasure:"""

        response = self.dm_generator_module.get_response(prompt, temperature=0.7)

        # Clean up the response
        hint_object = response.strip().lower()
        hint_object = hint_object.strip('"').strip("'").strip(".")

        # Fallback if LLM returns something weird
        if len(hint_object) > 50 or len(hint_object) < 3:
            hint_object = "mysterious object"

        return hint_object

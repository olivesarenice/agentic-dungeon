import random
from typing import Optional

from config import MAX_ROOM_PATHS, PAUSE, STARTING_ROOM_COORDS, GameConfigs
from constants import GameConstants
from controllers import AIController, HumanController
from enums import ActionType, DecisionType, Direction, PlayerType
from helpers import iso_ts
from llm import LLMModule, create_llm_module
from models import GameEvent, Player, PlayerEntry, Room, RoomEntry


class Game:
    """
    Main game orchestrator managing the dungeon exploration game.
    Handles world generation, player management, and turn execution.
    """

    def __init__(self):
        """
        Initialize the game with empty data structures.
        Uses regular dicts with explicit validation instead of defaultdict.
        """
        print("Initializing game...")

        # Use regular dicts to prevent accidental empty object creation
        self._rooms: dict[str, Room] = {}
        self._map: dict[tuple[int, int], str] = {}
        self._player_locations: dict[str, str] = {}
        self._players: dict[str, Player] = {}
        self._player_names: set[str] = set()

        # Keep track of room IDs for efficient random selection
        self._room_ids: list[str] = []

        self.dm_generator_module: LLMModule = create_llm_module(
            "You are the Dungeon Master overseeing a text-based exploration game. There are multiple players exploring a world made up of interconnected rooms. Your task is to generate descriptions for newly created rooms based on their connections and paths. Do not mention anything about the players themselves."
        )

        print("Game initialized.")

    def _translate(
        self,
        current_coords: tuple[int, int],
        move_direction: str,
    ) -> tuple[int, int]:
        """
        Time Complexity: O(1)
        Dictionary lookup and tuple arithmetic are constant time operations.
        """
        # print(f"Translating {current_coords} in direction {move_direction}...")
        translation = GameConfigs._moves[move_direction].translate
        new_coords = (
            current_coords[0] + translation[0],
            current_coords[1] + translation[1],
        )
        # print(f"New coordinates: {new_coords}")
        return new_coords

    def _room_from_id(self, room_id: str) -> Optional[Room]:
        """
        Safely get a room by ID with validation.

        Args:
            room_id: The room ID to look up

        Returns:
            Room if found, None otherwise

        Time Complexity: O(1)
        """
        room = self._rooms.get(room_id)
        if room is None:
            available_rooms = list(self._rooms.keys())[:5]
            print(
                f"Warning: Room {room_id} not found. Available rooms: {available_rooms}..."
            )
        return room

    def _get_adjacent_rooms(self, room: Room) -> dict[str, Room]:
        """
        Time Complexity: O(1)
        The function iterates over a fixed number of directions (4), performing
        constant time operations for each.
        """
        # returns {"N": Room, "S": Room...}

        adjacent_coords = {
            d: self._translate(room.coords, d) for d in GameConfigs._moves.keys()
        }
        rooms = {}
        for d, c in adjacent_coords.items():
            room_id = self._map.get(c)
            if room_id:
                rooms[d] = self._room_from_id(room_id)
            else:
                rooms[d] = None
        return rooms

    def _create_room(
        self,
        coords: tuple[int, int] = None,
        from_room: Room = None,  # A creation of room must always be from another room, unless starting room
        from_direction: str = None,  # direction of the from_room relative to the created_room
    ):
        """
        Time Complexity: O(1)
        The number of adjacent rooms and potential paths is constant (max 4).
        All operations are on small, fixed-size data structures.
        """
        print(
            f"Creating room at {coords} from room {from_room.id if from_room else 'None'}"
        )

        room = Room(
            coords,
        )

        paths = {}
        # This assumes that the room being created CAN open a path from the previous room already
        # TODO: This should be checked at the OPTIONS stage before the player even makes a move.

        # First check which directions in this new room can a path be placed
        # #that would not violate the MAX_PATHS rule on all other rooms next to it

        adjacent_rooms = self._get_adjacent_rooms(room)

        if from_room is not None and from_direction is not None:
            # Add the room that this room was created from
            paths[from_direction] = from_room.id

        # Prioritize connections to adjacent rooms that are already pointing here
        for d, aroom in adjacent_rooms.items():
            if len(paths) >= MAX_ROOM_PATHS:
                break
            if d in paths:
                continue
            if aroom:
                pole = GameConfigs._moves[d].pole
                if pole in aroom.paths and aroom.paths[pole] is None:
                    paths[d] = aroom.id

        # Fill remaining path slots randomly from other valid potential paths
        if len(paths) < MAX_ROOM_PATHS:
            potential_paths = {}
            for d, aroom in adjacent_rooms.items():
                if d in paths:
                    continue
                if aroom is None:
                    potential_paths[d] = None
                    continue
                if len(aroom.paths) < MAX_ROOM_PATHS:
                    potential_paths[d] = aroom.id
                    continue

            remaining_slots = MAX_ROOM_PATHS - len(paths)
            num_to_sample = min(len(potential_paths), remaining_slots)

            if num_to_sample > 0:
                new_path_directions = random.sample(
                    list(potential_paths.keys()), num_to_sample
                )
                new_paths = {d: potential_paths[d] for d in new_path_directions}
                paths.update(new_paths)
        print(f"New paths for room {room.id}: {paths}")

        # Update the room info

        path_descriptions = {
            d: desc if desc is not None else "unknown" for d, desc in paths.items()
        }
        description = (
            self.dm_generator_module.get_response(
                f"""Provide a 100-word description for the room that has just been created and the paths leading out of it.:
                room_name: {room.name}
                room_paths: {path_descriptions}
                
                If the path has a room_id, it means there is already a room there.
                If the path has `unknown`, it means the path is open to be explored.
                """
            ),
        )
        room.update_description(description)
        room.paths = paths

        # Update the items and maintain room ID list
        self._rooms[room.id] = room
        self._room_ids.append(room.id)  # Maintain list for O(1) random access
        self._map[room.coords] = room.id

        # And also update the paths of all rooms that we are now connected to:
        for d, room_id in room.paths.items():
            if room_id:
                aroom = self._room_from_id(room_id)
                aroom.paths[GameConfigs._moves[d].pole] = room.id

                new_description = self.dm_generator_module.get_response(
                    f"""The room {aroom.name} has just been connected to a new room {room.name} via the {GameConfigs._moves[d].pole} path.
                    Only update the room's path description to reflect this new connection. Current description: {aroom.description}.
                    Provide the new description.
                    """
                )

                print(
                    f"\033[92m"
                    f"""
                Adjacent room {aroom.name} updated:
                FROM = {aroom.description}.
                
                TO = {new_description}"""
                    f"\033[0m\n"
                )

                aroom.update_description(new_description)

        return room

    def create_world(self, starting_room_coords=STARTING_ROOM_COORDS):
        """
        Time Complexity: O(1)
        Calls `_create_room` once.
        """
        print("Creating world...")
        self._create_room(starting_room_coords)
        print("World created.")

    def create_player(
        self,
        player_name: str,
        player_type: PlayerType,
    ) -> Optional[Player]:
        """
        Create a new player with appropriate controller.

        Args:
            player_name: Name of the player
            player_type: Type of player (HUMAN or NPC)

        Returns:
            Created Player instance, or None if creation failed

        Time Complexity: O(1) now that we use _room_ids list
        """
        if not player_name:
            raise ValueError("Player name cannot be empty")

        print(f"Creating player: {player_name}")

        if player_name in self._player_names:
            print(f"Player with name {player_name} already exists.")
            return None

        if not self._room_ids:
            raise ValueError("Cannot create player: No rooms exist in the world")

        # O(1) random selection using pre-maintained list
        starting_room_id = random.choice(self._room_ids)
        starting_room = self._room_from_id(starting_room_id)

        if not starting_room:
            raise ValueError(f"Starting room {starting_room_id} not found")

        print(f"Player {player_name} starting in room {starting_room.name}")

        # Create appropriate controller based on player type
        if player_type == PlayerType.HUMAN:
            controller = HumanController()
        elif player_type == PlayerType.NPC:
            # Create LLM module for NPC
            npc_llm = create_llm_module(Player.DEFAULT_LLM_SYSTEM_PROMPT)
            controller = AIController(player_name, npc_llm)
        else:
            raise ValueError(f"Unknown player type: {player_type}")

        player = Player(
            name=player_name,
            room_id=starting_room.id,
            controller=controller,
            player_type=player_type,
        )

        print(f"Created player {player_name}, description: {player.description}")

        self._players[player.id] = player
        self._player_names.add(player_name)
        self._player_locations[player.id] = starting_room.id
        starting_room.players_inside.add(player.id)

        print(f"Player {player_name} created with ID {player.id}.")
        return player

    ### Turn management

    def process_player_move(
        self,
        player_id: str,
        player_input: str,
    ) -> bool:
        """
        Time Complexity: O(1)
        All operations inside are dictionary lookups, set operations, or calls
        to other O(1) functions.
        """
        print(f"Processing move for player {player_id}: {player_input}")
        # Load the player
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)
        print(f"Player {player.name} is in room {current_room.name}")

        # check if a room exists in the direction the player specified:
        next_coords = self._translate(
            current_room.coords,
            player_input,
        )
        next_room_id = self._map.get(next_coords)
        if not next_room_id:
            # Create a new room
            next_room = self._create_room(
                next_coords,
                current_room,
                from_direction=GameConfigs._moves[player_input].pole,  # the opposite
            )
        else:
            next_room = self._room_from_id(next_room_id)

        # Move the player to the next room.
        print(f"Moving player {player.name} to room {next_room.name}")
        self._player_locations[player.id] = next_room.id

        # Update room info
        current_room.players_inside.discard(player.id)
        next_room.players_inside.add(player.id)

        # Update the history
        player.move(
            current_room.id,
            player_input,
            next_room.id,
        )

        # All players in the current room update their memory about this player leaving
        for witness_id in current_room.players_inside:
            witness = self._players[witness_id]
            witness.witness(
                GameEvent(
                    timestamp=iso_ts,
                    room_id=current_room.id,
                    actor_id=player.id,
                    actor_name=player.name,
                    action_type="MOVE_OUT",
                    content=f"{player.name} has left the room.",
                    witness_ids=list(current_room.players_inside),
                ),
                self._players,
            )

        # TODO: Need to include the player_names inside the Room object, so that when observing, the player can see who is in the room.
        player.observe(next_room, self._players)
        # The player OBSERVEs the room after moving by default, no need for additional step

        # All other witnesses in the new room also update their memory about this player
        for witness_id in next_room.players_inside:
            if witness_id == player.id:
                continue
            witness = self._players[witness_id]
            witness.witness(
                GameEvent(
                    timestamp=iso_ts,
                    room_id=next_room.id,
                    actor_id=player.id,
                    actor_name=player.name,
                    action_type="MOVE_IN",
                    content=f"{player.name} has entered the room.",
                    witness_ids=list(next_room.players_inside),
                ),
                self._players,
            )

        return True

    def get_player_actions(self, player_id: str):
        options = list(GameConfigs._actions.keys())
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)
        if not current_room.players_inside - {player_id}:
            # No other players in the room, cannot TALK
            options.remove("TALK")

        return options

    def process_player_action(
        self,
        player_id: str,
        action_key: str,
    ) -> bool:
        """
        Process a player action using the controller pattern.

        Time Complexity: O(N-players in the room)
        Iterate through each player and update their memory.
        """
        print(f"Processing action for player {player_id}: {action_key}")
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)
        action = GameConfigs._actions[action_key]

        # Use controller to get action details
        action_prompt = player.controller.provide_action_details(action)

        # Create the game event
        event = GameEvent(
            timestamp=iso_ts(),
            room_id=current_room.id,
            actor_id=player.id,
            actor_name=player.name,
            action_type=action.name,
            content=action_prompt,
            witness_ids=list(current_room.players_inside),
        )

        if action.name == ActionType.TALK.value:
            print(
                f"Player {player.name} says: '{action_prompt}' to players in room {current_room.name}"
            )

        elif action.name == ActionType.INTERACT.value:
            print(
                f"Player {player.name} interacts with the room {current_room.name}: {action_prompt}"
            )

            # Update the room description to reflect the interaction (LLM)
            dm_prompt = f"""
            The player has just performed the following interaction in the room: 
            
            {action_prompt}.
            
            ---
            Update the description of the room to reflect this interaction. Do not mention the player or the event specifically.
            
            Current room description: {current_room.description}
            """
            dm_description = self.dm_generator_module.get_response(dm_prompt)
            print(
                f"\033[92mRoom {current_room.name} updated description:\nFROM = {current_room.description}\nTO = {dm_description}\033[0m\n"
            )
            current_room.update_description(dm_description)

        # Finally, update all players' memories who witnessed this event including the new changes to the room.
        for witness_id in event.witness_ids:
            witness = self._players[witness_id]
            witness.witness(event, self._players)

        # TODO: need to modify the room to also contain the player_names so that when observing, the player can see who is in the room.
        player.observe(current_room, self._players)  # Re-observe the room after action
        return True

    def get_player_moves(self, player_id: str):
        """
        Time Complexity: O(1)
        Consists of dictionary lookups to get player and room, then accessing
        the room's paths.
        """
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)
        return list(current_room.paths.keys())

    def draw_cli_map(self, current_player_id: str = None):
        """Draw the CLI map without using defaultdict."""
        if not self._map:
            print("The map is empty.")
            return

        coords = list(self._map.keys())
        min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
        min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)

        # Use dict with .get() instead of defaultdict
        grid: dict[tuple[int, int], str] = {}
        cell_h, cell_w = GameConstants.CLI_CELL_HEIGHT, GameConstants.CLI_CELL_WIDTH

        for (x, y), room_id in self._map.items():
            room = self._room_from_id(room_id)
            cx = (x - min_x) * (cell_w - 1)
            cy = (max_y - y) * (cell_h - 1)

            # Draw room box
            for i in range(cell_w):
                grid[cx + i, cy] = "-"
                grid[cx + i, cy + cell_h - 1] = "-"
            for i in range(cell_h):
                grid[cx, cy + i] = "|"
                grid[cx + cell_w - 1, cy + i] = "|"
            grid[cx, cy] = "+"
            grid[cx + cell_w - 1, cy] = "+"
            grid[cx, cy + cell_h - 1] = "+"
            grid[cx + cell_w - 1, cy + cell_h - 1] = "+"

            # Draw players
            player_chars = []
            for pid in sorted(list(room.players_inside)):
                if pid == current_player_id:
                    player_chars.append("X")
                else:
                    player_chars.append("O")

            player_str = "".join(player_chars)
            # Place player string in the middle of the room
            start_pos = (cell_w - len(player_str)) // 2
            for i, char in enumerate(player_str):
                grid[cx + start_pos + i, cy + (cell_h // 2)] = char

            # Draw connections
            if "N" in room.paths:
                grid[cx + cell_w // 2, cy] = " "
                grid[cx + cell_w // 2, cy - 1] = "|"
            if "S" in room.paths:
                grid[cx + cell_w // 2, cy + cell_h - 1] = " "
                grid[cx + cell_w // 2, cy + cell_h] = "|"
            if "W" in room.paths:
                grid[cx, cy + cell_h // 2] = " "
                grid[cx - 1, cy + cell_h // 2] = "-"
                grid[cx - 2, cy + cell_h // 2] = "-"
            if "E" in room.paths:
                grid[cx + cell_w - 1, cy + cell_h // 2] = " "
                grid[cx + cell_w, cy + cell_h // 2] = "-"
                grid[cx + cell_w + 1, cy + cell_h // 2] = "-"

        grid_w = (max_x - min_x + 1) * (cell_w - 1) + 1
        grid_h = (max_y - min_y + 1) * (cell_h - 1) + 1

        header = " MAP (X: You, O: Others) "
        print("\n" + f"{header:=^{grid_w}}")
        for r in range(grid_h):
            line = "".join([grid.get((c, r), " ") for c in range(grid_w)])
            print(line)
        print("=" * grid_w + "\n")

    def announce_turn_situation(self, player_id: str):
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)

        self.draw_cli_map(player_id)

        print(f"\033[93m\n--- Player {player.name}'s Turn ---\033[0m")
        print(f"\033[93mYou are in room: {current_room.name} \n \033[0m")
        print(f"\033[93mRoom description: {current_room.description} \n \033[0m")
        other_players = [
            self._players[pid].name
            for pid in current_room.players_inside
            if pid != player_id
        ]
        if other_players:
            print(f"\033[93mOther players in the room: {other_players}\033[0m")
        else:
            print("\033[93mYou are alone in this room.\033[0m")

    def run(self):
        """
        Main game loop using the controller pattern.

        Time Complexity: O(N_players * (1 + N_new_rooms_per_turn)) per round.
        The main game loop. For each player, it processes a move (O(1)),
        draws any new rooms created during the move (O(N_new_rooms)), and
        updates all player positions (O(N_players)). This provides real-time
        updates while remaining efficient.
        """
        while True:
            for player_id, player in self._players.items():

                # Announce the situation to the player
                self.announce_turn_situation(player_id)

                # Use controller to decide turn type
                decision = player.controller.decide_turn_type()

                if decision == DecisionType.ACT:
                    print(f"\nPlayer <{player.name}> chose to ACT.")
                    options = self.get_player_actions(player_id)
                    player_action = player.controller.decide_action(
                        options, GameConfigs._actions
                    )
                    self.process_player_action(player.id, player_action)

                elif decision == DecisionType.MOVE:
                    print(f"\nPlayer <{player.name}> chose to MOVE.")
                    options = self.get_player_moves(player_id)
                    player_move = player.controller.decide_move(options)
                    self.process_player_move(player.id, player_move)

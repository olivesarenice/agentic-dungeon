import random
from collections import defaultdict

import matplotlib.pyplot as plt

from config import MAX_ROOM_PATHS, PAUSE, STARTING_ROOM_COORDS, GameConfigs
from llm import LLMModule, create_llm_module
from models import Player, PlayerEntry, Room


class Game:

    def __init__(self):
        """
        Time Complexity: O(1)
        Initializes dictionaries and other data structures in constant time.
        """
        print("Initializing game...")
        self._rooms = defaultdict(Room)  # {room_id: Room}
        self._map = defaultdict(str)  # {(0,1):room_id}
        # self._connections = defaultdict(
        #     dict
        # )  # {from_room_id: {to_room_id: Connection}}

        self._player_locations = {}  # {player_id: room_id}
        self._players = defaultdict(Player)  # {player_id: Player}
        self._player_names = set()

        # Matplotlib setup
        plt.ion()  # Turn on interactive mode
        self.fig, self.ax = plt.subplots()
        self._player_artists = {}  # {player_id: (dot, text)}
        self._drawn_room_ids = set()
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

    def _room_from_id(self, room_id: str) -> Room:
        """
        Time Complexity: O(1)
        Dictionary lookup is a constant time operation.
        """
        return self._rooms.get(room_id)

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

        # Update the items.
        self._rooms[room.id] = room
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
        is_npc: bool,
    ):
        """
        Time Complexity: O(N_rooms)
        `random.choice(list(self._rooms.keys()))` is the bottleneck. Converting
        dict_keys to a list takes O(N_rooms) time.
        """
        print(f"Creating player: {player_name}")
        if player_name in self._player_names:
            print(f"Player with name {player_name} already exists.")
            return

        starting_room = self._room_from_id(
            random.choice(list(self._rooms.keys()))
        )  # Drop into a random room.
        print(f"Player {player_name} starting in room {starting_room.name}")
        player = Player(player_name, starting_room.id, is_npc)
        print(f"Created player {player_name}, description: {player.description}")
        self._players[player.id] = player
        self._player_names.add(player_name)
        self._player_locations[player.id] = starting_room.id
        starting_room.players_inside.add(player.id)
        print(f"Player {player_name} created with ID {player.id}.")

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
        action_prompt: str = None,  # A description of what the user wants to do.
    ) -> bool:
        """
        Time Complexity: O(1)
        All operations inside are dictionary lookups or set operations.
        """
        print(f"Processing action for player {player_id}: {action_key}")
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)
        action = GameConfigs._actions[action_key]

        if action.name == "OBSERVE":
            print(f"Player {player.name} observes the room: {current_room.description}")
            print(
                f"Players in the room: {[self._players[pid].name for pid in current_room.players_inside if pid != player_id]}"
            )
            # Update player's memory about the people in the room
            for pid in current_room.players_inside:
                if pid != player_id:
                    # if the player has not been met before:
                    if self._players[pid].name not in player.memory.known_players:
                        other_player = self._players[pid]
                        player.memory.known_players[other_player.name] = PlayerEntry(
                            name=other_player.name,
                            description=other_player.description,
                            last_seen_room_id=current_room.id,
                        )
        elif action.name == "TALK":
            talk_prompt = player.input_descriptive_prompt(action)
            print(
                f"Player {player.name} says: '{talk_prompt}' to players in room {current_room.name}"
            )

        elif action.name == "INTERACT":
            interact_prompt = player.input_descriptive_prompt(action)
            print(
                f"Player {player.name} interacts with the room {current_room.name}: {interact_prompt}"
            )

        player.history.append((current_room.id, action.description))
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

    def draw_map(self):
        """
        Time Complexity: O(N_new_rooms)
        Draws only the rooms and paths that have not been drawn yet. This is
        much more efficient than redrawing the entire map every time.
        """
        new_rooms = [
            room for room in self._rooms.values() if room.id not in self._drawn_room_ids
        ]

        if not new_rooms:
            return

        # Update plot limits if necessary
        all_coords = list(self._map.keys())
        min_x = min(c[0] for c in all_coords) - 2
        max_x = max(c[0] for c in all_coords) + 2
        min_y = min(c[1] for c in all_coords) - 2
        max_y = max(c[1] for c in all_coords) + 2
        self.ax.set_xlim(min_x, max_x)
        self.ax.set_ylim(min_y, max_y)
        self.ax.set_aspect("equal", adjustable="box")

        for room in new_rooms:
            x, y = room.coords
            # Draw room as a square
            self.ax.add_patch(
                plt.Rectangle(
                    (x - 0.2, y - 0.2),
                    0.4,
                    0.4,
                    fill=True,
                    color="lightblue",
                    ec="black",
                )
            )
            self.ax.text(
                x, y, room.name.split(" ")[1], ha="center", va="center", fontsize=8
            )
            # Draw paths as block lines
            for direction in room.paths.keys():
                dx, dy = GameConfigs._moves[direction].translate
                start_x, start_y = x + dx * 0.2, y + dy * 0.2
                end_x, end_y = x + dx * 0.4, y + dy * 0.4
                self.ax.plot(
                    [start_x, end_x],
                    [start_y, end_y],
                    color="lightblue",
                    linewidth=20,
                )
            self._drawn_room_ids.add(room.id)

    def update_player_positions(self):
        """
        Time Complexity: O(N_players)
        Updates the positions of player markers on the map. This is a very
        fast operation, as it only moves existing plot artists.
        """
        for player_id, player in self._players.items():
            room = self._room_from_id(player.room_id)
            x, y = room.coords

            if player_id in self._player_artists:
                # Update existing player artist
                dot, text = self._player_artists[player_id]
                dot.set_data([x], [y])
                text.set_position((x + 0.1, y + 0.1))
            else:
                # Create new player artist
                (dot,) = self.ax.plot(x, y, "ro")  # Red dot
                text = self.ax.text(
                    x + 0.1, y + 0.1, player.name, color="red", fontsize=10
                )
                self._player_artists[player_id] = (dot, text)

        plt.draw()
        plt.pause(PAUSE)

    def announce_turn_situation(self, player_id: str):
        player = self._players[player_id]
        current_room = self._room_from_id(player.room_id)

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
        Time Complexity: O(N_players * (1 + N_new_rooms_per_turn)) per round.
        The main game loop. For each player, it processes a move (O(1)),
        draws any new rooms created during the move (O(N_new_rooms)), and
        updates all player positions (O(N_players)). This provides real-time
        updates while remaining efficient.
        """
        # # Initial draw of the world
        self.draw_map()
        self.update_player_positions()

        while True:
            for player_id, player in self._players.items():

                # Announce the situation to the player
                self.announce_turn_situation(player_id)

                # Player now makes certain decisions:
                player_fn = player.move_or_act()
                if player_fn == "ACT":
                    print(f"\nPlayer <{player.name}> chose to ACT.")
                    options = self.get_player_actions(player_id)
                    player_action = player.decide_action(options, GameConfigs._actions)
                    self.process_player_action(player.id, player_action)
                elif player_fn == "MOVE":
                    print(f"\nPlayer <{player.name}> chose to MOVE.")
                    options = self.get_player_moves(player_id)
                    player_move = player.decide_move(options, GameConfigs._moves)
                    self.process_player_move(player.id, player_move)

            self.draw_map()
            self.update_player_positions()

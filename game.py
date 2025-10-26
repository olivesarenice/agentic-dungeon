"""
Time Complexity Analysis:

The game gets progressively slower each round because of the `update_grid` function.
This function is called after every player's move inside the `run` loop.

The time complexity of `update_grid` is O(N_rooms + N_players), where N_rooms is the
total number of rooms in the game world. As players explore and new rooms are
created, N_rooms increases.

Since `update_grid` redraws the entire map from scratch, its execution time grows
linearly with the number of rooms. This linear growth, repeated every turn,
causes the noticeable slowdown as the game progresses.

To optimize, `update_grid` could be called once per round (after all players have
moved) instead of after each individual move. For further optimization, one could
implement a dirty-flag system to only redraw the parts of the map that have changed.
"""

# Data model for Nodes, Relationships, Graphs
import random
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from uuid import uuid4

import fictional_names
import fictional_names.name_generator
import matplotlib.pyplot as plt
from faker import Faker
from FantasyNameGenerator.Stores import Town
from tqdm import tqdm

fake = Faker()

PAUSE = 0.5
STARTING_ROOM_COORDS = (0, 0)
MAX_ROOM_PATHS = 4  # can only be 2,3,4
N_NPCS = 0
# LLM IMPORTS
from llm import LLMModule, create_llm_module


@dataclass
class PlayerEntry:
    name: str
    description: str
    last_seen_room_id: str
    interaction_history: list = field(default_factory=list)


@dataclass
class RoomEntry:
    id: str
    name: str
    description: str


class Memory:  # The agent's mental model of the game world from their perspective
    def __init__(self):
        self.known_players = {}  # {player_name: PlayerEntry}
        self.known_rooms = {}  # {room_id: RoomEntry}
        self.preferences = {}


class Player:

    DEFAULT_LLM_SYSTEM_PROMPT = "You are an adventurer in a text-based exploration game. Make decisions based on your surroundings and history."

    def __init__(
        self,
        name: str,
        room_id: str,
        is_npc=False,
    ):
        self.id = str(uuid4())
        self.name = name
        self.is_npc = is_npc
        self.room_id = room_id
        self.history = (
            []
        )  # [(room_id, action_taken)] # actions can be `move` or `interact_with`

        self.agent_engine = None  # Placeholder for future AI integration
        self.memory = Memory()
        self.llm_module: LLMModule = create_llm_module(self.DEFAULT_LLM_SYSTEM_PROMPT)
        self.description: str = self.llm_module.get_response(
            f"Provide a 20-word brief description of your character named {self.name}."
        )

    def move_or_act(self) -> str:
        return random.choice(
            [
                "MOVE",
                "ACT",
            ]
        )

    def decide_action(self, options: list[str], actions: dict) -> str:
        # Placeholder for future action decision logic
        return "OBSERVE"

    def decide_move(self, options: list[str], moves: dict) -> str:

        if self.is_npc:
            if not self.history:
                return random.choice(options)

            last_direction = self.history[-1][1]
            opposite_direction = moves[last_direction].pole

            preferred_options = [opt for opt in options if opt != opposite_direction]

            if preferred_options:
                return random.choice(preferred_options)
            else:
                return random.choice(options)

        else:
            return input_user_move(options)

    def move(
        self,
        from_room_id: str,
        action_taken: str,
        to_room_id: str,
    ):
        self.history.append((from_room_id, action_taken))
        self.room_id = to_room_id


class Room:
    def __init__(self, coords: tuple[int, int], description=""):
        self.id, self.name = self.new_details()
        self.coords = coords
        self.paths = {}  # {"N":room_id, "S":room_id}
        self.players_inside = set()  # {player_id}
        self.description = description
        print(f"Room created: {self.name} at {self.coords}.")

    @staticmethod
    def new_details():

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

    def update_description(self, new_description: str):
        self.description = new_description
        print(f"Room {self.name} updated: {self.description}.")


@dataclass
class Move:
    direction: str
    translate: tuple[int, int]
    pole: str


@dataclass
class Action:
    # observe
    # talk
    # interact
    name: str
    description: str
    affects_room: bool  # modifies the state of the room
    affects_players: bool  # modifies the state of other players, hence requires checking who is in the room


@dataclass
class Connection:
    direction: str
    # Other attributes can be added here as needed


@dataclass
class GameConfigs:
    _moves = {
        "N": Move("N", (0, 1), "S"),
        "S": Move("S", (0, -1), "N"),
        "E": Move("E", (1, 0), "W"),
        "W": Move("W", (-1, 0), "E"),
    }
    _actions = {
        "1": Action(
            "OBSERVE",
            description="Take in the room around you, and the players in it.",
            affects_room=False,
            affects_players=False,
        ),
        "2": Action(
            "TALK",
            description="Make a comment about something that everyone in the room can hear.",
            affects_room=False,
            affects_players=True,
        ),
        "3": Action(
            "INTERACT",
            description="Modify something about the room. Other people can see you do this.",
            affects_room=True,
            affects_players=True,
        ),
    }


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
                    f"""
                Adjacent room {aroom.name} updated:
                FROM = {aroom.description}.
                
                TO = {new_description}"""
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
            options.remove("2")

        return options

    def process_player_action(
        self,
        player_id: str,
        action_key: str,
        action_prompt: None,  # A description of what the user wants to do.
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
            print(
                f"Player {player.name} says: '{action_prompt}' to players in room {current_room.name}"
            )

        elif action.name == "INTERACT":
            print(
                f"Player {player.name} interacts with the room {current_room.name}: {action_prompt}"
            )

            # Placeholder for future logic to modify room state
        # if action.affects_players:
        #     other_players = current_room.players_inside - {player_id}
        #     print(
        #         f"Player {player.name} is performing action {action.description} affecting players: {other_players}"
        #     )
        #     # Placeholder for future logic to affect other players

        # if action.affects_room:
        #     print(
        #         f"Player {player.name} is performing action {action.description} affecting room {current_room.name}"
        #     )
        #     # Placeholder for future logic to affect the room

        # Update history
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

                player_fn = player.move_or_act()
                if player_fn == "ACT":
                    print(f"\nPlayer <{player.name}> chose to ACT.")
                    continue
                    options = self.get_player_actions(player_id)
                    player_action = player.decide_action(options, GameConfigs._actions)
                    self.process_player_action(player.id, player_action)
                elif player_fn == "MOVE":
                    print(f"\nPlayer <{player.name}> chose to MOVE.")
                    options = self.get_player_moves(player_id)
                    player_move = player.decide_move(options, GameConfigs._moves)
                    self.process_player_move(player.id, player_move)

            # After each move, draw newly created rooms and update player positions
            # print("\n\n\n\n\n", len(self._rooms), end="\r")
            self.draw_map()
            self.update_player_positions()


###


# helpers
def checked_input(prompt: str) -> str:
    input_str = input(prompt + ": ")
    while input_str == "":
        print("No input found, please try again.")
        input_str = input(prompt)

    if input_str == "/q":
        print("Goodbye!")
        exit()
    else:
        return input_str


def input_user_move(options: list[str]) -> str:
    print("Available options:")
    for option in options:
        print(f"- {option}")
    i = checked_input("What do you want to do next?").upper()

    while i not in options:
        print("Invalid move")
        i = checked_input("What do you want to do next?").upper()
    return i


def main():
    print("Starting game...")
    game = Game()
    game.create_world()

    # # Only 1 player
    player_name = "OLIVER"
    game.create_player(player_name, is_npc=False)

    # All NPCs
    for _ in tqdm(range(N_NPCS), desc="Generating NPCs"):
        npc_name = fake.name_nonbinary()
        game.create_player(npc_name, is_npc=True)

    # Run
    print("Running game...")
    game.run()
    print("Game over.")


if __name__ == "__main__":
    main()

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

import matplotlib.pyplot as plt
from faker import Faker
from tqdm import tqdm

fake = Faker()

STARTING_ROOM_COORDS = (0, 0)
MAX_ROOM_PATHS = 3  # can only be 2,3,4


class Player:
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

    def auto_action(self, options: list[str], moves: dict) -> str:
        """
        Chooses an action for an NPC player.
        Avoids immediately going back to the previous room to encourage exploration.
        """
        if not self.history:
            return random.choice(options)

        last_direction = self.history[-1][1]
        opposite_direction = moves[last_direction].pole

        preferred_options = [opt for opt in options if opt != opposite_direction]

        if preferred_options:
            return random.choice(preferred_options)
        else:
            return random.choice(options)

    def move(
        self,
        from_room_id: str,
        action_taken: str,
        to_room_id: str,
    ):
        self.history.append((from_room_id, action_taken))
        self.room_id = to_room_id


class Room:
    def __init__(self, coords: tuple[int, int]):
        self.id, self.name, self.description = self.new_details()
        self.coords = coords
        self.paths = {}  # {"N":room_id, "S":room_id}
        self.players_inside = set()  # {player_id}
        print(f"Room created: {self.name} at {self.coords}")

    @staticmethod
    def new_details():
        prefix = "001"
        color = fake.color_name()
        location = fake.street_name()

        description = "Default description"
        name = f"{prefix} {color} {location}"
        id_slug = (
            f"{prefix.lower()}-{color.lower()}-{location.replace(" ", "-").lower()}"
        )
        return id_slug, name, description


@dataclass
class Move:
    direction: str
    translate: tuple[int, int]
    pole: str


@dataclass
class Connection:
    direction: str
    # Other attributes can be added here as needed


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
        self._moves = {
            "N": Move("N", (0, 1), "S"),
            "S": Move("S", (0, -1), "N"),
            "E": Move("E", (1, 0), "W"),
            "W": Move("W", (-1, 0), "E"),
        }
        self._player_locations = {}  # {player_id: room_id}
        self._players = defaultdict(Player)  # {player_id: Player}
        self._player_names = set()

        # Matplotlib setup
        plt.ion()  # Turn on interactive mode
        self.fig, self.ax = plt.subplots()
        self._player_artists = {}  # {player_id: (dot, text)}
        self._drawn_room_ids = set()

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
        print(f"Translating {current_coords} in direction {move_direction}...")
        translation = self._moves[move_direction].translate
        new_coords = (
            current_coords[0] + translation[0],
            current_coords[1] + translation[1],
        )
        print(f"New coordinates: {new_coords}")
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
            d: self._translate(room.coords, d) for d in self._moves.keys()
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
        room = Room(coords)
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
                pole = self._moves[d].pole
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

        # Create the room
        room.paths = paths

        # Update the items.
        self._rooms[room.id] = room
        self._map[room.coords] = room.id

        # And also update the paths of all rooms that we are now connected to:
        for d, room_id in room.paths.items():
            if room_id:
                aroom = self._room_from_id(room_id)
                aroom.paths[self._moves[d].pole] = room.id

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
        self._players[player.id] = player
        self._player_names.add(player_name)
        self._player_locations[player.id] = starting_room.id
        starting_room.players_inside.add(player.id)

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
                from_direction=self._moves[player_input].pole,  # the opposite
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

    def get_player_options(self, player_id: str):
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
                dx, dy = self._moves[direction].translate
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
        plt.pause(0.001)

    def run(self):
        """
        Time Complexity: O(N_players * (1 + N_new_rooms_per_turn)) per round.
        The main game loop. For each player, it processes a move (O(1)),
        draws any new rooms created during the move (O(N_new_rooms)), and
        updates all player positions (O(N_players)). This provides real-time
        updates while remaining efficient.
        """
        # # Initial draw of the world
        # self.draw_map()
        # self.update_player_positions()

        while True:
            for player_id, player in self._players.items():
                options = self.get_player_options(player_id)
                if player.is_npc:
                    player_input = player.auto_action(options, self._moves)
                else:
                    # Player can do stuff
                    player_input = input_user_move(options)
                success = False
                while not success:
                    success = self.process_player_move(player.id, player_input)

            # After each move, draw newly created rooms and update player positions
            print("\n\n\n\n\n", len(self._rooms), end="\r")
            # self.draw_map()
            # self.update_player_positions()


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
    # player_name = "OLIVER"
    # game.create_player(player_name, is_npc=False)

    # All NPCs
    for _ in tqdm(range(10_000), desc="Generating NPCs"):
        npc_name = fake.uuid4()
        game.create_player(npc_name, is_npc=True)

    # Run
    print("Running game...")
    game.run()
    print("Game over.")


if __name__ == "__main__":
    main()

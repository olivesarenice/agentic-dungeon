# Data model for Nodes, Relationships, Graphs
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum


@dataclass
class Node:
    node_id: int
    type: str  # options: Room, Player, NPC
    properties: dict = field(default_factory=defaultdict(str))


@dataclass
class Relation:
    start_node: int
    end_node: int
    type: str  # options
    properties: dict = field(default_factory=defaultdict(str))


@dataclass
class Graph:
    _current_node_id: int = 0  # incremental index, nodes cannot be destroyed.
    _nodes = {}  # stores node objects {node_id: Node}
    _graph: dict = field(
        default_factory=defaultdict(dict)
    )  # stores mapping {from_node:{to_node, Relation}}
    _directed = True  # completeness

    def add_node(self, node: Node):
        pass

    def get_node(self, node_id: int):
        pass


MOVEMENTS = [
    "N",
    "S",
    "E",
    "W",
]
NPC_ACTIONS = {
    "IDLE": 0.5,
    "MOVE": 0.3,
    "MODIFY": 0.2,
}


# Step 1: Build the data structures that can hold node information that i am going to input.
# game flow: user is presented with current room and adjacent location options - for already explored directions, return the room details.
# if user chooses an old room, just return the old room stuff
# if user chooses a new room, dungeon master creates a new room with some info
# at each turn, NPCs have X chance to move to an adjacent room or stay in the current room. In either case, they will modify the room details with some "action"

# Test case data:

# lets build the user movement first:


def checked_input(prompt: str):
    input_str = input(prompt + ": ")
    while input_str == "":
        print("No input found, please try again.")
        input_str = input(prompt)

    if input_str == "/q":
        print("Goodbye!")
        exit()
    else:
        return input_str


def input_user_move():
    i = checked_input("Where do you want to go next?")


print("Welcome to Agentic Dungeon - enter /q to quit anytime.")

# Generate some NPCs
# npcs = create_npcs()...

while True:
    # NPC move first
    for npc in npcs:
        # do stuff
        print("NPC {npc} did stuff...")

    user_move = checked_input("Where do you want to go next?")

    # Do stuff to move the user
    print("You have moved to {user_move}")

    # Do stuff with the action - create a new room or return an existing room
    # Check if any NPCs around to interact with
    if room.characters > 1:
        room_npcs = room.characters.remove(player)
        user_action = checked_input(
            "How do you want to interact with the NPCs {room_npcs}?"
        )
        print("You did {user_action}")

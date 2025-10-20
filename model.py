# Data model for Nodes, Relationships, Graphs
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

fake = Faker()

# Generate a list of adjectives and locations
ADJECTIVES = [
    fake.word(ext_word_list=["mysterious", "ancient", "dark", "hidden", "forbidden"])
    for _ in range(10000)
]
LOCATIONS = [fake.city() for _ in range(10000)]

CREATED_LOCATIONS = {
    f"{adj.upper()}_{loc.upper()}" for adj, loc in zip(ADJECTIVES, LOCATIONS)
}


def random_location():
    return CREATED_LOCATIONS.pop()


@dataclass
class Node:
    id: int
    name: str
    type: str  # options: Room, Player, NPC
    properties: dict = field(default_factory=defaultdict(str))


@dataclass
class Relation:
    type: str  # options
    properties: dict = field(default_factory=defaultdict(str))


from uuid import uuid4


def new_id():
    return str(uuid4())[-8:]


class Directions(Enum):
    N = auto()
    S = auto()
    E = auto()
    W = auto()


@dataclass
class Defaults:
    START_ROOM = "LOBBY"
    DIRECTIONS = {d.name for d in Directions}
    NPC_ACTIONS = {
        "IDLE": 0.5,
        "MOVE": 0.3,
        "MODIFY": 0.2,
    }


from copy import deepcopy
from enum import auto
from pprint import pprint

from faker import Faker


class Graph:
    def __init__(self):
        self._nodes = {}  # stores node objects {id: Node}
        self._node_idx = {}  # reverse index of the node name:id
        self._graph = defaultdict(
            dict
        )  # stores mapping {from_node:{to_node, Relation}}
        self._directed = True  # completeness

    def _checkadd_node_name(self, node: Node):
        if self._node_idx.get(node.name):
            print(f"node name {node.name} already exists")
        else:
            self._node_idx[node.name] = node.id

    def _node_from_name(self, node_name):
        nid = self._node_idx.get(node_name)
        if not nid:
            print(f"Node {node_name} cannot be found")
        return self._nodes.get(nid)

    def create_world(self, room=Defaults.START_ROOM):
        # First create a lone node which is the room.
        first_room = Node(
            id=new_id(),
            type="Room",
            name=room,
            properties={"description": "The starting room."},
        )
        self._nodes[first_room.id] = first_room  # first node doesnt need any mapping
        self._checkadd_node_name(first_room)
        self._graph[first_room.id] = {}
        print("World created")

    def create_room(self, name, description):
        room = Node(
            id=new_id(),
            type="Room",
            name=name,
            properties={"description": description},
        )
        self.upsert_node(room)
        return room

    def create_player(self, name="Protagonist"):
        # Then add the player
        player = Node(
            id=new_id(),
            type="Player",
            name=name,
            properties={"description": "The brave adventurer."},
        )
        # The player always spawns in the starting room
        self.upsert_node(player)
        self.update_character_location(
            player,
            self._node_from_name(Defaults.START_ROOM),
            {"description": "Spawned by default"},
        )

    def upsert_node(self, node: Node):
        self._nodes[node.id] = node
        self._checkadd_node_name(node)

    def upsert_rs(self, from_node, to_node, relation: Relation):
        self._graph[from_node.id] = {to_node.id: relation}

    def update_character_location(self, player, room, properties):
        self.upsert_rs(
            player,
            room,
            Relation(
                type="IS_IN",
                properties=properties,
            ),
        )

    def update_room_connections(self, new_room, old_room, adjacency: Directions):
        self.upsert_rs(
            old_room,
            new_room,
            Relation(
                type="CONNECTS_TO",
                properties={"adjacency": adjacency},
            ),
        )

    def _process_player_move(self, player_name: str, player_input: Directions):
        # get the player's current location
        pid = self._node_from_name(player_name)
        for node_id, rs in self._graph.get(pid).items():
            if rs.type == "IS_IN":
                current_room_id = node_id
                break

        # check if a room exists in the direction the player specified:
        next_room_id = None
        for room_id, rs in self._graph.get(current_room_id).items():
            if rs.type == "CONNECTS_TO" and rs.properties["adjacency"] == player_input:
                next_room_id = room_id
        # if yes, return the room details
        if next_room_id:
            print(f"Moving you to {next_room_id}")
            # TODO: # Move the guy over and update RS
        # if no, create the room
        else:
            print(f"Exploring a new room...")
            self.create_room(
                random_location(),
                description="Randomly generated location",
            )
            # TODO: Update the RS of room locations and the player IS_IN

    def visualise(self):
        cp = deepcopy(self._graph)
        readable_graph = {}
        for from_id, rs in cp.items():

            from_name = self._nodes[from_id].name
            readable_graph[from_name] = {}

            for to_id, relation in rs.items():
                to_name = self._nodes[to_id].name
                readable_graph[from_name][to_name] = relation
        pprint(readable_graph)


# Step 1: Build the data structures that can hold node information that i am going to input.
# game flow: user is presented with current room and adjacent location options - for already explored directions, return the room details.
# if user chooses an old room, just return the old room stuff
# if user chooses a new room, dungeon master creates a new room with some info
# at each turn, NPCs have X chance to move to an adjacent room or stay in the current room. In either case, they will modify the room details with some "action"

# Test case data:

# lets build the user movement first:


# helpers
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
    i = checked_input("Where do you want to go next?").upper()

    while i not in Defaults.MOVEMENTS:
        print("Invalid move")
        i = checked_input("Where do you want to go next?")
    return i


print("Welcome to Agentic Dungeon - enter /q to quit anytime.")

# Generate some NPCs
# npcs = create_npcs()...

# Initialise the world
graph = Graph()
graph.create_world()

# player_name = checked_input("What is your player name?: ")
player_name = "OLIVER"
graph.create_player(player_name)

graph.visualise()

while True:
    # NPC move first
    # for npc in npcs:
    #     # do stuff
    #     print("NPC {npc} did stuff...")

    user_move = input_user_move()

    # Do stuff to move the user
    print(f"You have moved to {user_move}")

    # Do stuff with the action - create a new room or return an existing room
    # Check if any NPCs around to interact with
    # if room.characters > 1:
    #     room_npcs = room.characters.remove(player)
    #     user_action = checked_input(
    #         "How do you want to interact with the NPCs {room_npcs}?"
    #     )
    #     print("You did {user_action}")

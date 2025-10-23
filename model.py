# Data model for Nodes, Relationships, Graphs
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto

from faker import Faker

fake = Faker()
CREATED_LOCATIONS = {fake.street_name() for _ in range(10000)}

from uuid import uuid4


def new_id():
    return str(uuid4())[-8:]


def random_location():
    return CREATED_LOCATIONS.pop()


@dataclass
class Node:
    name: str
    description: str = ""
    properties: dict = field(default_factory=lambda: defaultdict(str))
    id: str = field(default_factory=new_id)
    type: str = "NODE"


@dataclass
class Player(Node):
    is_npc: bool = True
    type: str = "PLAYER"


@dataclass
class Room(Node):
    explore_options: list[str] = field(default_factory=list)
    coords: tuple[str, str] = (None, None)
    type: str = "ROOM"


@dataclass
class Relation:
    description: str


@dataclass
class RoomConnection(Relation):
    adjacency: str
    type: str = "CONNECTS_TO"


@dataclass
class PlayerRoom(Relation):
    type: str = "IS_IN"


class Directions(Enum):
    N = auto()
    S = auto()
    E = auto()
    W = auto()


@dataclass
class Defaults:
    START_ROOM = "LOBBY"
    DIRECTIONS = {d.name for d in Directions}
    POLES = {
        "N": "S",
        "S": "N",
        "E": "W",
        "W": "E",
    }
    NPC_ACTIONS = {
        "IDLE": 0.5,
        "MOVE": 0.3,
        "MODIFY": 0.2,
    }


from copy import deepcopy
from enum import auto
from pprint import pprint

import matplotlib.pyplot as plt
import networkx as nx
from faker import Faker


class Graph:
    def __init__(self):
        self._nodes = {}  # stores node objects {id: Node}
        self._node_idx = {}  # reverse index of the node name:id
        self._graph = defaultdict(
            dict
        )  # stores mapping {from_node:{to_node, Relation}}
        self._directed = True  # completeness

        # --- NEW: Initialize the plot for live updates ---
        plt.ion()  # Turn on interactive mode
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        # --- END NEW ---

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
        first_room = Room(
            name=room,
            description="The starting room.",
            explore_options=list(Defaults.DIRECTIONS),
            coords=random_location(),
        )
        self._nodes[first_room.id] = first_room  # first node doesnt need any mapping
        self._checkadd_node_name(first_room)
        self._graph[first_room.id] = {}
        print("World created")

    def create_room(self, name, from_adjacency: Directions, description):
        # Select 2 random directions avaible
        import random

        reverse_dir = Defaults.POLES.get(from_adjacency)
        options = list(Defaults.DIRECTIONS)
        options.remove(reverse_dir)  # remove travelling backwards first
        explore_options = [reverse_dir]  # always an option

        explore_options.extend(random.sample(options, 1))
        print(explore_options)
        room = Room(
            name=name,
            description=description,
            explore_options=explore_options,
            coords=random_location(),
        )
        self.upsert_node(room)
        self._graph[room.id] = {}  # New rooms start as empty nodes on the graph
        return room

    def create_player(self, name="Protagonist", is_npc=False):
        # Then add the player
        player = Player(
            name=name,
            is_npc=is_npc,
            description="The brave adventurer.",
        )
        # The player always spawns in the starting room
        self.upsert_node(player)
        self.update_character_location(
            player,
            self._node_from_name(Defaults.START_ROOM),
            "Spawned by default",
        )

    def upsert_node(self, node: Node):
        self._nodes[node.id] = node
        self._checkadd_node_name(node)

    def upsert_rs(self, from_node, to_node, relation: Relation):
        if relation.type == "IS_IN":
            self._graph[from_node.id] = {to_node.id: relation}
        else:
            self._graph[from_node.id][to_node.id] = relation

    def update_character_location(self, player, room, description):
        self.upsert_rs(
            player,
            room,
            PlayerRoom(description=description),
        )

    def update_room_connections(
        self,
        new_room: Node,
        old_room: Node,
        adjacency: Directions,
    ):
        self.upsert_rs(
            old_room,
            new_room,
            RoomConnection(
                description=f"Connection from {old_room.name} to {new_room.name}",
                adjacency=adjacency,
            ),
        )

        # And we also need to map the reverse connection
        self.upsert_rs(
            new_room,
            old_room,
            RoomConnection(
                description=f"Connection from {new_room.name} to {old_room.name}",
                adjacency=Defaults.POLES[adjacency],
            ),
        )

    def _player_current_room(self, player_name: str) -> Node:
        player = self._node_from_name(player_name)
        for node_id, rs in self._graph.get(player.id).items():
            if rs.type == "IS_IN":
                current_room_id = node_id
                current_room = self._nodes[current_room_id]
                return current_room

    def get_navigation_details(self, player_name: str):
        current_room = self._player_current_room(player_name)
        if not current_room:
            return None, {}

        # Create a map of direction -> destination room name
        connections = self._graph.get(current_room.id, {})
        direction_to_room_name = {
            rs.adjacency: self._nodes[room_id].name
            for room_id, rs in connections.items()
            if isinstance(rs, RoomConnection)
        }

        dialogue_options = {}
        for direction in sorted(list(current_room.explore_options)):
            dest_room_name = direction_to_room_name.get(direction)
            if dest_room_name:
                dialogue_options[direction] = f"Back to {dest_room_name}"
            else:
                dialogue_options[direction] = "Explore new area"
        return current_room, dialogue_options

    def _process_player_move(
        self,
        player_name: str,
        player_input: Directions,
    ) -> str:
        # get the player's current location
        player = self._node_from_name(player_name)
        current_room = self._player_current_room(player_name)

        # check if a room exists in the direction the player specified:
        next_room_id = None
        for room_id, rs in self._graph.get(current_room.id).items():
            if isinstance(rs, RoomConnection) and rs.adjacency == player_input:
                next_room_id = room_id
        # if yes, return the room details
        if next_room_id:
            next_room = self._nodes[next_room_id]
            # print(f"Moving you to {next_room.name}")

        # if no, create the room
        else:
            print(f"Exploring a new room...")
            next_room = self.create_room(
                random_location(),
                player_input,
                description="Randomly generated location",
            )
            self.update_room_connections(
                next_room,
                current_room,
                player_input,
            )

        # Move the player over
        self.update_character_location(
            player,
            next_room,
            f"Moved from {current_room.name}",
        )

        return next_room.name, next_room.explore_options

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

    def visualise_graph(self):
        """
        Visualizes the graph using networkx and matplotlib.
        Shows room nodes and their edges with adjacency values.
        """
        G = nx.DiGraph()
        node_colors = []
        node_labels = {}

        # Add nodes
        for node_id, node in self._nodes.items():
            G.add_node(node.id, name=node.name, type=node.type)
            node_labels[node.id] = node.name
            if node.type == "Room":
                node_colors.append("skyblue")  # Color for rooms
            elif node.type == "Player":
                node_colors.append("lightgreen")  # Color for players
            else:
                node_colors.append("lightgray")  # Default color for other types

        # Add edges and edge labels
        edge_labels = {}
        for from_id, relations in self._graph.items():
            for to_id, relation in relations.items():
                if isinstance(relation, RoomConnection):
                    G.add_edge(from_id, to_id, adjacency=relation.adjacency)
                    edge_labels[(from_id, to_id)] = relation.adjacency
                elif isinstance(relation, PlayerRoom):
                    # IS_IN relations are typically between a player/NPC and a room.
                    # We don't draw these as explicit edges in the room graph visualization.
                    pass

        plt.clf()  # Clear the current figure
        pos = nx.spring_layout(G)  # Layout for the nodes

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700)

        # Draw edges
        nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=20, edge_color="gray")

        # Draw node labels
        nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=10)

        # Draw edge labels
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_color="red")

        plt.title("Game World Graph")
        plt.axis("off")  # Hide axes
        plt.show()

    def get_room_coords(self):
        """
        Calculates 2D (x, y) coordinates for all room nodes based on their
        CONNECTS_TO relations (N, S, E, W).
        Returns a dictionary: {room_id: (x, y)}.
        """
        # Start with the Lobby at (0, 0)
        lobby_node = self._node_from_name(Defaults.START_ROOM)
        if not lobby_node:
            return {}

        room_coords = {lobby_node.id: (0, 0)}
        queue = [lobby_node.id]
        visited = {lobby_node.id}
        occupied_coords = {
            (0, 0): [lobby_node.id]
        }  # Track occupied coordinates and the rooms there

        offset_step = 0.1  # Small offset to prevent direct overlap

        while queue:
            current_room_id = queue.pop(0)
            x, y = room_coords[current_room_id]

            # Iterate over outgoing edges from the current room
            for neighbour_id, relation in self._graph.get(current_room_id, {}).items():
                if isinstance(relation, RoomConnection):
                    direction = relation.adjacency

                    # Determine base new coordinates based on direction
                    base_new_coords = None
                    if direction == "N":
                        base_new_coords = (x, y + 1)
                    elif direction == "S":
                        base_new_coords = (x, y - 1)
                    elif direction == "E":
                        base_new_coords = (x + 1, y)
                    elif direction == "W":
                        base_new_coords = (x - 1, y)
                    else:
                        continue  # Skip non-directional or invalid relations

                    if neighbour_id not in visited:
                        visited.add(neighbour_id)

                        # Check for overlap and apply offset if necessary
                        new_coords = list(base_new_coords)
                        offset_count = 0
                        while tuple(new_coords) in occupied_coords:
                            offset_count += 1
                            # Apply a spiral-like offset
                            if offset_count % 4 == 1:  # East
                                new_coords[0] = (
                                    base_new_coords[0] + offset_count * offset_step
                                )
                            elif offset_count % 4 == 2:  # North
                                new_coords[1] = (
                                    base_new_coords[1] + offset_count * offset_step
                                )
                            elif offset_count % 4 == 3:  # West
                                new_coords[0] = (
                                    base_new_coords[0] - offset_count * offset_step
                                )
                            else:  # South
                                new_coords[1] = (
                                    base_new_coords[1] - offset_count * offset_step
                                )

                        new_coords = tuple(new_coords)
                        room_coords[neighbour_id] = new_coords
                        occupied_coords.setdefault(new_coords, []).append(neighbour_id)
                        queue.append(neighbour_id)

        return room_coords

    def update_grid_visualization(self):
        """
        Visualizes the game world as a 2D grid in a single, updating window.
        """
        # --- CHANGED: Clear the existing axes instead of creating a new figure ---
        self.ax.clear()

        room_coords = self.get_room_coords()
        if not room_coords:
            self.ax.text(0.5, 0.5, "No rooms to visualize.", ha="center")
            plt.pause(0.01)
            return

        all_x = [x for x, y in room_coords.values()]
        all_y = [y for x, y in room_coords.values()]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        room_size = 0.9

        # Draw Rooms
        for room_id, (x, y) in room_coords.items():
            room_node = self._nodes[room_id]
            room_rect = plt.Rectangle(
                (x - room_size / 2, y - room_size / 2),
                room_size,
                room_size,
                facecolor="skyblue",
                edgecolor="darkblue",
                alpha=0.6,
            )
            # --- CHANGED: Use self.ax to draw ---
            self.ax.add_patch(room_rect)
            self.ax.text(
                x,
                y + room_size / 2 + 0.1,
                room_node.name,
                ha="center",
                va="bottom",
                fontsize=8,
                color="darkblue",
            )

            # Find Players/NPCs in this room (your logic is already good)
            players_in_room = []
            for node_id, node in self._nodes.items():
                if node.type == "PLAYER":
                    player_relations = self._graph.get(node_id, {})
                    for target_id, relation in player_relations.items():
                        if isinstance(relation, PlayerRoom) and target_id == room_id:
                            players_in_room.append(node.name)
                            break

            # Place Player/NPC labels
            if players_in_room:
                player_text = "\n".join(players_in_room)
                self.ax.text(
                    x,
                    y,
                    player_text,
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="black",
                    bbox=dict(
                        facecolor="gold",
                        alpha=0.9,
                        edgecolor="none",
                        boxstyle="round,pad=0.2",
                    ),
                )

        # --- CHANGED: Configure the existing self.ax ---
        self.ax.set_xlim(min_x - 1.5, max_x + 1.5)
        self.ax.set_ylim(min_y - 1.5, max_y + 1.5)
        self.ax.grid(True, linestyle="--", color="gray", alpha=0.5)
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.set_title("Game World Map (Live)")
        self.ax.set_xlabel("West <--> East")
        self.ax.set_ylabel("South <--> North")

        # --- CHANGED: Use pause() to redraw the canvas ---
        plt.pause(0.01)  # A short pause is necessary to allow the GUI to update

    def update_graph_visualization(self):
        """
        Visualizes the world using a dynamic NetworkX graph layout.
        """
        # 1. Clear the axes for the new frame
        self.ax.clear()

        G = nx.DiGraph()
        node_labels = {}
        node_colors = {}
        players_locations = {}  # To draw players on top of rooms

        # First, add all rooms to the graph to ensure they are all included
        for node_id, node in self._nodes.items():
            if node.type == "Room":
                G.add_node(node_id)
                node_labels[node_id] = node.name
                node_colors[node_id] = "skyblue"
            elif node.type in ["Player", "NPC"]:
                # Find where the player is
                player_relations = self._graph.get(node_id, {})
                for target_id, relation in player_relations.items():
                    if isinstance(relation, PlayerRoom):
                        # Store player name and the room_id they are in
                        players_locations[node.name] = target_id
                        break

        # Add edges for room connections
        edge_labels = {}
        for from_id, relations in self._graph.items():
            if self._nodes[from_id].type != "Room":
                continue  # Only draw connections between rooms
            for to_id, relation in relations.items():
                if isinstance(relation, RoomConnection):
                    G.add_edge(from_id, to_id)
                    edge_labels[(from_id, to_id)] = relation.adjacency

        # 2. Use a force-directed layout to position nodes
        # This is the key step that moves away from a rigid grid.
        # It arranges nodes based on their connections.
        pos = nx.spring_layout(G, seed=42, iterations=100)

        # 3. Draw the graph components on the class's axes object
        nx.draw_networkx_nodes(
            G,
            pos,
            ax=self.ax,
            node_color=list(node_colors.values()),
            node_size=3000,
            alpha=0.9,
        )
        nx.draw_networkx_edges(
            G,
            pos,
            ax=self.ax,
            arrowstyle="->",
            arrowsize=20,
            edge_color="gray",
            node_size=3000,
        )
        nx.draw_networkx_labels(
            G, pos, ax=self.ax, labels=node_labels, font_size=10, font_weight="bold"
        )
        nx.draw_networkx_edge_labels(
            G, pos, ax=self.ax, edge_labels=edge_labels, font_color="red"
        )

        # Overlay player names on their current room
        for player_name, room_id in players_locations.items():
            if room_id in pos:  # Ensure the room exists in the layout
                x, y = pos[room_id]
                self.ax.text(
                    x,
                    y,
                    f"\n\n{player_name}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="darkgreen",
                    weight="bold",
                )

        self.ax.set_title("Game World (Force-Directed Graph)")
        self.ax.margins(0.1)
        plt.pause(0.01)

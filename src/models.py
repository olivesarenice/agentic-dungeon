import random
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import uuid4

import fictional_names
import fictional_names.name_generator
from FantasyNameGenerator.Stores import Town

from helpers import iso_ts, prompt_user_choice, prompt_user_text
from llm import LLMModule, create_llm_module


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
    player_prompt: str  # prompt to ask player for more details
    affects_room: bool  # modifies the state of the room
    affects_players: bool  # modifies the state of other players, hence requires checking who is in the room


from datetime import datetime


@dataclass
class GameEvent:
    """A structured log of an event that occurred in the game."""

    timestamp: datetime
    room_id: str
    actor_id: str  # these can only be players
    actor_name: str
    action_type: str  # e.g., "TALK", "INTERACT", "MOVE_IN", "MOVE_OUT"
    content: str  # e.g., "Hello, anyone here?", "Pulls a lever"
    # The list of players who were in the room to witness this event
    witness_ids: list[str]


@dataclass
class PlayerEntry:
    name: str
    description: str  # description of the player as remembered by the agent
    last_seen_room_id: str  # the room where the player was last encountered
    # This will store all direct interactions (e.g., TALK)
    interaction_history: list[GameEvent] = field(default_factory=list)

    def update_description(self, new_description: str):
        self.description = new_description


@dataclass
class RoomEntry:
    id: str
    name: str  # from the room itself
    description: str  # description of the room as remembered by the player
    # This will store all events the player witnessed in this room
    observed_events: list[GameEvent] = field(default_factory=list)

    def update_description(self, new_description: str):
        self.description = new_description


class Memory:  # The agent's mental model of the game world from their perspective
    def __init__(self):
        self.known_players = defaultdict(PlayerEntry)  # {player_name: PlayerEntry}
        self.known_rooms = defaultdict(RoomEntry)  # {room_id: RoomEntry}
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

        # Load up the LLM memory with base prompt
        self.llm_module: LLMModule = create_llm_module(self.DEFAULT_LLM_SYSTEM_PROMPT)

        self.description: str = self.llm_module.get_response(
            f"Provide a 20-word brief description of your character named {self.name}."
        )

        # Update the LLM module with self-description
        self.update_llm_module()

    def describe_self(self) -> str:
        return f"""
                These are details about yourself.
                Name: {self.name}
                Description: {self.description}
                        """

    def update_llm_module(self):
        self.llm_module = create_llm_module(
            self.DEFAULT_LLM_SYSTEM_PROMPT + self.describe_self()
        )

    def move_or_act(self) -> str:

        decisions = {
            "1": "MOVE",
            "2": "ACT",
        }

        return prompt_user_choice(list(decisions.values()))
        return random.choice(
            [
                "MOVE",
                "ACT",
            ]
        )

    def decide_action(self, options: list[str], actions: dict) -> str:
        # Placeholder for future action decision logic
        if self.is_npc:
            return random.choice(options)
        else:
            choice = prompt_user_choice(options)
        return choice

    def input_descriptive_prompt(self, action: Action) -> str:
        if self.is_npc:
            prompt = f"As an NPC named {self.name}, you have decided to <{action.name}>: {action.description}.{action.player_prompt}. "
            return self.llm_module.get_response(prompt)
        else:
            return prompt_user_text(
                f"You decided to <{action.name}>. {action.player_prompt} "
            )

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

            return prompt_user_choice(options)

    def move(
        self,
        from_room_id: str,
        action_taken: str,
        to_room_id: str,
    ):
        self.history.append((from_room_id, action_taken))
        self.room_id = to_room_id

    def observe(self, current_room, players_map):
        print(
            f"Other players in the room: {[players_map[pid].name for pid in current_room.players_inside if pid != self.id]}"
        )
        # Update player's memory about the people in the room
        for pid in current_room.players_inside:
            if pid == self.id:
                continue
            # if the player has not been met before:
            if players_map[pid].name not in self.memory.known_players:
                other_player = players_map[pid]
                self.memory.known_players[other_player.name] = PlayerEntry(
                    name=other_player.name,
                    description=other_player.description,
                    last_seen_room_id=current_room.id,
                )

        # Also update the player's memory about the room
        self.memory.known_rooms[current_room.id] = RoomEntry(
            id=current_room.id,
            name=current_room.name,
            description=current_room.description,
        )

    def witness(self, event: GameEvent, players_map: dict):
        # Update memory based on witnessed event
        # Ensure the actor of the event is in memory
        if event.actor_name not in self.memory.known_players:
            actor = players_map[event.actor_id]
            self.memory.known_players[event.actor_name] = PlayerEntry(
                name=actor.name,
                description=actor.description,
                last_seen_room_id=event.room_id,
            )

        # Record the event in the room's memory
        if event.room_id not in self.memory.known_rooms:
            # This case should ideally be handled by prior observation,
            # but as a fallback:
            self.memory.known_rooms[event.room_id] = RoomEntry(
                id=event.room_id,
                name="An unfamiliar room",  # Placeholder name
                description="A room you've heard about but not seen.",
            )
        self.memory.known_rooms[event.room_id].observed_events.append(event)

        # Record the event in the actor's memory entry
        self.memory.known_players[event.actor_name].interaction_history.append(event)

        # Memory updates
        self.synthesize_player_memory(event.actor_name)
        self.synthesize_room_memory(event.room_id)

    # TODO: Merge player and room memories into a single class?
    def synthesize_player_memory(self, player_name: str):
        # Placeholder for future memory synthesis logic
        recent_interaction_event = (
            self.memory.known_players[player_name].interaction_history[-1]
            if self.memory.known_players[player_name].interaction_history
            else None
        )
        synthesize_prompt = f"""Update your mental description of {player_name} based on your most recent interaction with them.
        Current Description: 
        {self.memory.known_players[player_name].description if self.memory.known_players[player_name].description else 'No prior description.'}
        ---
        Recent Interaction: 
        {recent_interaction_event.content if recent_interaction_event else 'No recent interactions.'}"""
        new_description = self.llm_module.get_response(synthesize_prompt)
        self.memory.known_players[player_name].update_description(new_description)
        print(f"Player {self.name} updated memory of player {player_name}.")
        print(f"New description: {new_description}")

    # TODO: Merge player and room memories into a single class?
    def synthesize_room_memory(self, room_id: str):
        # Placeholder for future memory synthesis logic
        recent_obs_event = (
            self.memory.known_rooms[room_id].observed_events[-1]
            if self.memory.known_rooms[room_id].observed_events
            else None
        )

        if not recent_obs_event:
            return

        synthesize_prompt = f"""Update your mental description of {room_id} based on your most recent observations.
        Current Description:
        {self.memory.known_rooms[room_id].description if self.memory.known_rooms[room_id].description else 'No prior description.'}
        ---
        Recent Observation:
        {recent_obs_event.actor_name} {recent_obs_event.action_type} in {recent_obs_event.room_id}"""
        new_description = self.llm_module.get_response(synthesize_prompt)
        self.memory.known_rooms[room_id].update_description(new_description)
        print(f"Player {self.name} updated memory of room {room_id}.")
        print(f"New description: {new_description}")


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
class Connection:
    direction: str
    # Other attributes can be added here as needed

import random
from dataclasses import dataclass, field
from uuid import uuid4

import fictional_names
import fictional_names.name_generator
from FantasyNameGenerator.Stores import Town

from helpers import prompt_user_choice, prompt_user_text
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

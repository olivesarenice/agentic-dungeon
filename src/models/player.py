"""
Player class for game entities.
"""

from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from config.constants import GameConstants
from config.enums import PlayerType
from llm import LLMModule, create_llm_module

from .events import GameEvent
from .memory import Memory, PlayerEntry, RoomEntry
from .npc_personality import NPCPersonality, PersonalityType

if TYPE_CHECKING:
    from controllers import PlayerController


class Player:
    """
    Represents a player in the game (human or NPC).
    Uses the Strategy Pattern via PlayerController for decision-making.
    """

    DEFAULT_LLM_SYSTEM_PROMPT = "You are an adventurer in a text-based exploration game. Make decisions based on your surroundings and history."

    def __init__(
        self,
        name: str,
        room_id: str,
        controller: "PlayerController",
        player_type: PlayerType = PlayerType.HUMAN,
        llm_module: Optional[LLMModule] = None,
        personality: Optional[NPCPersonality] = None,
    ):
        """
        Initialize a player.

        Args:
            name: Player's name
            room_id: Starting room ID
            controller: Controller for decision-making
            player_type: Type of player (HUMAN or NPC)
            llm_module: Optional LLM module for testing
            personality: Optional NPC personality (auto-generated if NPC and not provided)
        """
        if not name:
            raise ValueError("Player name cannot be empty")
        if not room_id:
            raise ValueError("Player must start in a valid room")

        self.id: str = str(uuid4())
        self.name: str = name
        self.player_type: PlayerType = player_type
        self.room_id: str = room_id
        self.history: list[tuple[str, str]] = []
        self.memory: Memory = Memory()
        self.controller = controller

        # NPC personality system
        if player_type == PlayerType.NPC:
            self.personality: Optional[NPCPersonality] = (
                personality or self._generate_random_personality()
            )
        else:
            self.personality: Optional[NPCPersonality] = None

        # Load up the LLM memory with base prompt
        self.llm_module: LLMModule = llm_module or create_llm_module(
            self.DEFAULT_LLM_SYSTEM_PROMPT
        )

        self.description: str = self.llm_module.get_response(
            f"Provide a {GameConstants.DEFAULT_DESCRIPTION_WORDS}-word brief description of your character named {self.name}."
        )

        # Update the LLM module with self-description
        self.update_llm_module()

    def _generate_random_personality(self) -> NPCPersonality:
        """Generate a random personality for an NPC."""
        import random

        personality_type = random.choice(list(PersonalityType))
        return NPCPersonality(personality_type=personality_type)

    def describe_self(self) -> str:
        """Get a description of this player for LLM context."""
        return f"""
                These are details about yourself.
                Name: {self.name}
                Description: {self.description}
                        """

    def update_llm_module(self) -> None:
        """Update the LLM module with current self-description."""
        self.llm_module = create_llm_module(
            self.DEFAULT_LLM_SYSTEM_PROMPT + self.describe_self()
        )

    def move(self, from_room_id: str, action_taken: str, to_room_id: str) -> None:
        """
        Move the player to a new room.

        Args:
            from_room_id: The room ID the player is leaving
            action_taken: The action/direction taken
            to_room_id: The room ID the player is entering

        Raises:
            ValueError: If any room ID is empty or action is invalid
        """
        if not from_room_id:
            raise ValueError("from_room_id cannot be empty")
        if not to_room_id:
            raise ValueError("to_room_id cannot be empty")
        if not action_taken:
            raise ValueError("action_taken cannot be empty")

        self.history.append((from_room_id, action_taken))
        self.room_id = to_room_id

    def observe(self, current_room, players_map):
        """Update player's memory about the current room and players in it."""
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
        """Update memory based on witnessed event."""
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

    def synthesize_player_memory(self, player_name: str):
        """Update mental description of another player based on recent interactions."""
        from llm import PromptBuilder

        recent_interaction_event = (
            self.memory.known_players[player_name].interaction_history[-1]
            if self.memory.known_players[player_name].interaction_history
            else None
        )

        current_description = (
            self.memory.known_players[player_name].description
            if self.memory.known_players[player_name].description
            else "No prior description."
        )

        # Build detailed interaction content including action type, content, and room
        if recent_interaction_event:
            # Get room name if we know it
            room_name = "Unknown room"
            if recent_interaction_event.room_id in self.memory.known_rooms:
                room_name = self.memory.known_rooms[
                    recent_interaction_event.room_id
                ].name

            interaction_content = (
                f"{player_name} performed action: {recent_interaction_event.action_type}\n"
                f"Details: {recent_interaction_event.content}\n"
                f"Location: {room_name}"
            )
        else:
            interaction_content = "No recent interactions."

        # Use PromptBuilder to get structured format
        synthesize_prompt = PromptBuilder.build_memory_update_prompt(
            player_name=player_name,
            current_description=current_description,
            interaction_content=interaction_content,
        )

        new_description = self.llm_module.get_response(synthesize_prompt)
        self.memory.known_players[player_name].update_description(new_description)
        print(f"Player {self.name} updated memory of player {player_name}.")
        print(f"New description: {new_description}")

    def synthesize_room_memory(self, room_id: str):
        """Update mental description of a room based on recent observations."""
        from llm import PromptBuilder

        recent_obs_event = (
            self.memory.known_rooms[room_id].observed_events[-1]
            if self.memory.known_rooms[room_id].observed_events
            else None
        )

        if not recent_obs_event:
            return

        current_description = (
            self.memory.known_rooms[room_id].description
            if self.memory.known_rooms[room_id].description
            else "No prior description."
        )

        # Build observation string from event with additional context
        # Include information about players who have been seen in this room
        all_players_seen = set()
        for event in self.memory.known_rooms[room_id].observed_events:
            if event.actor_name:
                all_players_seen.add(event.actor_name)

        observation = (
            f"{recent_obs_event.actor_name} {recent_obs_event.action_type} in {recent_obs_event.room_id}\n"
            f"All players previously seen in this room: {', '.join(all_players_seen) if all_players_seen else 'None'}"
        )

        # Use PromptBuilder to get structured format
        synthesize_prompt = PromptBuilder.build_room_memory_update_prompt(
            room_id=room_id,
            current_description=current_description,
            observation=observation,
        )

        new_description = self.llm_module.get_response(synthesize_prompt)
        self.memory.known_rooms[room_id].update_description(new_description)
        print(f"Player {self.name} updated memory of room {room_id}.")
        print(f"New description: {new_description}")

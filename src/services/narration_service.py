"""
Narration service for generating contextual voiceover narrations.
Tracks context and generates unique narrations for each player action.
"""

from typing import Optional

from llm import PromptTemplates, create_fast_llm
from models import Player, Room


class NarrationService:
    """
    Service for generating contextual voiceover narrations.
    Ensures each narration is unique and contextually aware.
    """

    def __init__(self):
        """Initialize the narration service."""
        # System prompt for punchy, impactful narrations
        system_prompt = (
            "You are a voiceover narrator for a dungeon crawler game. "
            "CRITICAL: ONE SHORT SENTENCE ONLY. NO EXCEPTIONS. "
            "Lead with the strongest sensory hit - what hits you first: sight, sound, smell, touch. "
            "Be immediate and visceral. Second person ('You'). "
            "Examples: 'The stench hits you.' 'Cold steel under your fingers.' 'Darkness swallows the light.'"
        )
        # Use FAST model for quick, punchy one-sentence narrations
        self.llm = create_fast_llm(system_prompt)
        self.last_narrations = {}  # player_id -> list of recent narrations

    def _get_context_key(self, player_id: str, room_id: str, action_type: str) -> str:
        """Generate a unique key for this context."""
        return f"{player_id}:{room_id}:{action_type}"

    def _track_narration(self, player_id: str, narration: str) -> None:
        """Track narration to avoid repetition."""
        if player_id not in self.last_narrations:
            self.last_narrations[player_id] = []

        self.last_narrations[player_id].append(narration)

        # Keep only last 5 narrations to check for repetition
        if len(self.last_narrations[player_id]) > 5:
            self.last_narrations[player_id].pop(0)

    def _get_recent_narrations(self, player_id: str) -> str:
        """Get recent narrations for context."""
        if player_id not in self.last_narrations:
            return "None"
        return "\n".join([f"- {n}" for n in self.last_narrations[player_id]])

    def generate_move_narration(
        self,
        player: Player,
        from_room: Room,
        to_room: Room,
        direction: str,
        is_first_visit: bool,
    ) -> str:
        """
        Generate narration for player movement.

        Args:
            player: The player moving
            from_room: The room the player is leaving
            to_room: The room the player is entering
            direction: Direction of movement (N, S, E, W)
            is_first_visit: Whether this is the first time visiting this room

        Returns:
            Narration text
        """
        direction_names = {"N": "north", "S": "south", "E": "east", "W": "west"}
        dir_name = direction_names.get(direction, direction)

        # Build context for LLM
        recent = self._get_recent_narrations(player.id)

        prompt = PromptTemplates.VOICEOVER_MOVE_NARRATION.substitute(
            player_name=player.name,
            from_room_name=from_room.name,
            from_room_description=from_room.description,
            to_room_name=to_room.name,
            to_room_description=to_room.description,
            direction=dir_name,
            is_first_visit="Yes" if is_first_visit else "No",
            recent_narrations=recent,
        )

        narration = self.llm.get_response(prompt).strip()

        # Clean up any quotes or extra formatting
        narration = narration.strip('"').strip("'").strip()

        self._track_narration(player.id, narration)

        return narration

    def generate_action_narration(
        self,
        player: Player,
        room: Room,
        action_type: str,
        action_content: str,
        npcs_present: list[str],
    ) -> str:
        """
        Generate narration for player actions (TALK, INTERACT, OBSERVE).

        Args:
            player: The player performing the action
            room: The current room
            action_type: Type of action (TALK, INTERACT, OBSERVE)
            action_content: The specific action content
            npcs_present: List of NPC names present

        Returns:
            Narration text
        """
        recent = self._get_recent_narrations(player.id)
        npcs_text = ", ".join(npcs_present) if npcs_present else "no one"

        prompt = PromptTemplates.VOICEOVER_ACTION_NARRATION.substitute(
            player_name=player.name,
            room_name=room.name,
            room_description=room.description,
            action_type=action_type,
            action_content=action_content,
            npcs_present=npcs_text,
            recent_narrations=recent,
        )

        narration = self.llm.get_response(prompt).strip()

        # Clean up any quotes or extra formatting
        narration = narration.strip('"').strip("'").strip()

        self._track_narration(player.id, narration)

        return narration

    def generate_room_entry_narration(
        self,
        player: Player,
        room: Room,
        is_returning: bool,
        time_since_last_visit: Optional[str] = None,
    ) -> str:
        """
        Generate narration for entering a room (different from move narration).
        This focuses on sensory details and atmosphere.

        Args:
            player: The player entering
            room: The room being entered
            is_returning: Whether the player has been here before
            time_since_last_visit: Optional description of time passed

        Returns:
            Narration text
        """
        recent = self._get_recent_narrations(player.id)

        if is_returning:
            prompt = PromptTemplates.VOICEOVER_RETURN_NARRATION.substitute(
                player_name=player.name,
                room_name=room.name,
                room_description=room.description,
                time_info=time_since_last_visit or "recently",
                recent_narrations=recent,
            )
        else:
            prompt = PromptTemplates.VOICEOVER_FIRST_VISIT_NARRATION.substitute(
                player_name=player.name,
                room_name=room.name,
                room_description=room.description,
                recent_narrations=recent,
            )

        narration = self.llm.get_response(prompt).strip()
        narration = narration.strip('"').strip("'").strip()

        self._track_narration(player.id, narration)

        return narration

    def generate_room_change_narration(
        self,
        player: Player,
        action_description: str,
        before_description: str,
        after_description: str,
    ) -> str:
        """
        Generate narration describing how the room changed after a player's interaction.

        Args:
            player: The player who performed the action
            action_description: What the player did
            before_description: Room description before the action
            after_description: Room description after the action

        Returns:
            Narration text describing the change
        """
        recent = self._get_recent_narrations(player.id)

        prompt = PromptTemplates.VOICEOVER_ROOM_CHANGE_NARRATION.substitute(
            action_description=action_description,
            before_description=before_description,
            after_description=after_description,
            recent_narrations=recent,
        )

        narration = self.llm.get_response(prompt).strip()
        narration = narration.strip('"').strip("'").strip()

        self._track_narration(player.id, narration)

        return narration

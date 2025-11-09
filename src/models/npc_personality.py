"""
Simplified NPC personality system with 4 core personality types.
"""

from dataclasses import dataclass, field
from enum import Enum


class PersonalityType(Enum):
    """Core personality types for NPCs."""

    EXPLORER = "explorer"  # Keeps moving to new places, doesn't talk
    HOMEBODY = "homebody"  # Moves around same rooms, doesn't interact or talk
    HOSTILE = "hostile"  # Interacts with players/rooms to destroy/steal
    HELPFUL = "helpful"  # Talks to players, socializes, doesn't interact


@dataclass
class NPCPersonality:
    """Defines an NPC's personality and behavior preferences."""

    personality_type: PersonalityType

    def should_move(self, has_other_players: bool) -> float:
        """
        Get probability of choosing MOVE action (0.0 to 1.0).

        Args:
            has_other_players: Whether other players are present

        Returns:
            Probability weight for MOVE action
        """
        if self.personality_type == PersonalityType.EXPLORER:
            # Always wants to move to new places
            return 0.85

        elif self.personality_type == PersonalityType.HOMEBODY:
            # Prefers staying in place
            return 0.3  # Low chance to move

        elif self.personality_type == PersonalityType.HOSTILE:
            # Moves to find targets, stays if players present
            if has_other_players:
                return 0.2  # Stay to interact hostilely
            else:
                return 0.6  # Move to find players

        elif self.personality_type == PersonalityType.HELPFUL:
            # Moves to find players to help
            if has_other_players:
                return 0.1  # Stay to socialize
            else:
                return 0.7  # Move to find players

        return 0.5  # Default

    def should_talk(self, has_other_players: bool) -> float:
        """
        Get probability of choosing TALK action (0.0 to 1.0).

        Args:
            has_other_players: Whether other players are present

        Returns:
            Probability weight for TALK action
        """
        if not has_other_players:
            return 0.0  # Can't talk if alone

        if self.personality_type == PersonalityType.EXPLORER:
            return 0.1  # Rarely talks

        elif self.personality_type == PersonalityType.HOMEBODY:
            return 0.0  # Never talks

        elif self.personality_type == PersonalityType.HOSTILE:
            return 0.3  # Sometimes talks (threats, demands)

        elif self.personality_type == PersonalityType.HELPFUL:
            return 0.8  # Loves to talk

        return 0.3  # Default

    def should_interact(self, has_other_players: bool) -> float:
        """
        Get probability of choosing INTERACT action (0.0 to 1.0).

        Args:
            has_other_players: Whether other players are present

        Returns:
            Probability weight for INTERACT action
        """
        if self.personality_type == PersonalityType.EXPLORER:
            return 0.4  # Sometimes interacts with environment

        elif self.personality_type == PersonalityType.HOMEBODY:
            return 0.0  # Never interacts

        elif self.personality_type == PersonalityType.HOSTILE:
            return 0.7  # Often interacts (destroy, steal)

        elif self.personality_type == PersonalityType.HELPFUL:
            return 0.1  # Rarely interacts (focused on talking)

        return 0.3  # Default

    def get_action_weights(self, has_other_players: bool) -> dict[str, float]:
        """
        Get action weights for decision making.

        Args:
            has_other_players: Whether other players are present

        Returns:
            Dictionary of action -> weight
        """
        return {
            "MOVE": self.should_move(has_other_players),
            "TALK": self.should_talk(has_other_players),
            "INTERACT": self.should_interact(has_other_players),
        }

    def get_personality_description(self) -> str:
        """Get a description of this personality for LLM context."""
        descriptions = {
            PersonalityType.EXPLORER: "You are an explorer who loves discovering new places. You prefer to keep moving and don't like small talk.",
            PersonalityType.HOMEBODY: "You are a homebody who likes familiar places. You stay in your comfort zone and prefer solitude.",
            PersonalityType.HOSTILE: "You are hostile and aggressive. You interact with people and objects to cause trouble, steal, or destroy.",
            PersonalityType.HELPFUL: "You are helpful and friendly. You love talking to people and helping them out.",
        }
        return descriptions.get(
            self.personality_type, "You are an adventurer in this world."
        )

    def get_talk_tone(self) -> str:
        """Get the tone for TALK actions."""
        tones = {
            PersonalityType.EXPLORER: "brief and distracted",
            PersonalityType.HOMEBODY: "quiet and withdrawn",  # Shouldn't happen
            PersonalityType.HOSTILE: "threatening and aggressive",
            PersonalityType.HELPFUL: "friendly and warm",
        }
        return tones.get(self.personality_type, "neutral")

    def get_interact_intent(self) -> str:
        """Get the intent for INTERACT actions."""
        intents = {
            PersonalityType.EXPLORER: "curious examination",
            PersonalityType.HOMEBODY: "cautious observation",  # Shouldn't happen
            PersonalityType.HOSTILE: "destructive or thieving",
            PersonalityType.HELPFUL: "trying to help or fix",
        }
        return intents.get(self.personality_type, "investigation")

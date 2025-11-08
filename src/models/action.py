"""
Action and Move dataclasses for game mechanics.
"""

from dataclasses import dataclass


@dataclass
class Move:
    """Represents a movement direction in the game."""

    direction: str
    translate: tuple[int, int]
    pole: str


@dataclass
class Action:
    """Represents an action a player can perform."""

    name: str
    description: str
    player_prompt: str  # prompt to ask player for more details
    affects_room: bool  # modifies the state of the room
    affects_players: bool  # modifies the state of other players

"""
Event bus for distributing events to witnesses using database persistence.
"""

from sqlalchemy.orm import Session

from models import GameEvent, Player
from repositories import EventRepository


class EventBus:
    """
    Manages event distribution to witnessing players.
    Persists events to database.
    """

    def __init__(self, session: Session, world_id: str):
        """
        Initialize event bus with database session.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this event bus operates on
        """
        self.session = session
        self.world_id = world_id
        self.event_repo = EventRepository(session, world_id)

    def distribute_event(
        self, event: GameEvent, witness_ids: list[str], players_map: dict[str, Player]
    ) -> None:
        """
        Distribute an event to all witnessing players.

        Args:
            event: The game event
            witness_ids: List of player IDs who witnessed the event
            players_map: Dictionary of all players
        """
        # Persist event to database
        self.event_repo.add(event, witness_ids)

        # Distribute to witnesses in memory
        for witness_id in witness_ids:
            if witness_id in players_map:
                witness = players_map[witness_id]
                witness.witness(event, players_map)

    def notify_player_left_room(
        self,
        actor: Player,
        room_id: str,
        witness_ids: list[str],
        players_map: dict[str, Player],
    ) -> None:
        """
        Notify witnesses that a player left a room.

        Args:
            actor: Player who left
            room_id: Room ID
            witness_ids: List of witness player IDs
            players_map: Dictionary of all players
        """
        event = GameEvent.create_move_out_event(
            room_id=room_id, actor_id=actor.id, actor_name=actor.name
        )
        self.distribute_event(event, witness_ids, players_map)

    def notify_player_entered_room(
        self,
        actor: Player,
        room_id: str,
        witness_ids: list[str],
        players_map: dict[str, Player],
    ) -> None:
        """
        Notify witnesses that a player entered a room.

        Args:
            actor: Player who entered
            room_id: Room ID
            witness_ids: List of witness player IDs
            players_map: Dictionary of all players
        """
        event = GameEvent.create_move_in_event(
            room_id=room_id, actor_id=actor.id, actor_name=actor.name
        )
        self.distribute_event(event, witness_ids, players_map)

    def notify_player_action(
        self,
        actor: Player,
        room_id: str,
        action_type: str,
        content: str,
        witness_ids: list[str],
        players_map: dict[str, Player],
    ) -> None:
        """
        Notify witnesses about a player action.

        Args:
            actor: Player who performed the action
            room_id: Room ID where action occurred
            action_type: Type of action
            content: Action content/details
            witness_ids: List of witness player IDs
            players_map: Dictionary of all players
        """
        event = GameEvent.create_action_event(
            room_id=room_id,
            actor_id=actor.id,
            actor_name=actor.name,
            action_type=action_type,
            content=content,
        )
        self.distribute_event(event, witness_ids, players_map)

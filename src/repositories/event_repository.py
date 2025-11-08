"""
Repository for GameEvent persistence.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from database.models import DBEventWitness, DBGameEvent
from models import GameEvent


class EventRepository:
    """Repository for managing game event persistence."""

    def __init__(self, session: Session, world_id: str):
        """
        Initialize repository with database session and world ID.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this repository operates on
        """
        self.session = session
        self.world_id = world_id

    def add(self, event: GameEvent, witness_ids: list[str]) -> None:
        """
        Add a new event to the database.

        Args:
            event: GameEvent domain model to persist
            witness_ids: List of player IDs who witnessed the event
        """
        db_event = DBGameEvent(
            world_id=self.world_id,
            room_id=event.room_id,
            actor_id=event.actor_id,
            actor_name=event.actor_name,
            action_type=event.action_type,
            content=event.content,
            timestamp=datetime.fromisoformat(event.timestamp),
        )
        self.session.add(db_event)
        self.session.flush()  # Get the event ID

        # Add witnesses
        for witness_id in witness_ids:
            witness = DBEventWitness(event_id=db_event.id, player_id=witness_id)
            self.session.add(witness)

        self.session.commit()

    def get_events_by_room(self, room_id: str, limit: int = 50) -> list[DBGameEvent]:
        """
        Get recent events in a room.

        Args:
            room_id: Room ID
            limit: Maximum number of events to return

        Returns:
            List of database event models
        """
        return (
            self.session.query(DBGameEvent)
            .filter_by(world_id=self.world_id, room_id=room_id)
            .order_by(DBGameEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_events_by_player(
        self, player_id: str, limit: int = 50
    ) -> list[DBGameEvent]:
        """
        Get recent events involving a player.

        Args:
            player_id: Player ID
            limit: Maximum number of events to return

        Returns:
            List of database event models
        """
        return (
            self.session.query(DBGameEvent)
            .filter_by(world_id=self.world_id, actor_id=player_id)
            .order_by(DBGameEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_witnessed_events(
        self, player_id: str, limit: int = 50
    ) -> list[DBGameEvent]:
        """
        Get events witnessed by a player.

        Args:
            player_id: Player ID
            limit: Maximum number of events to return

        Returns:
            List of database event models
        """
        return (
            self.session.query(DBGameEvent)
            .join(DBEventWitness)
            .filter(
                DBGameEvent.world_id == self.world_id,
                DBEventWitness.player_id == player_id,
            )
            .order_by(DBGameEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

    def get_all_events(self, limit: int = 100) -> list[DBGameEvent]:
        """
        Get all events in this world.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of database event models
        """
        return (
            self.session.query(DBGameEvent)
            .filter_by(world_id=self.world_id)
            .order_by(DBGameEvent.timestamp.desc())
            .limit(limit)
            .all()
        )

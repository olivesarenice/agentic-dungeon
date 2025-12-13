"""
Repository for managing items (treasures) in V3.
"""

from typing import Optional

from sqlalchemy.orm import Session

from database.models import DBItem


class ItemRepository:
    """Repository for item operations."""

    def __init__(self, session: Session, world_id: str):
        """
        Initialize repository.

        Args:
            session: Database session
            world_id: World ID for filtering
        """
        self.session = session
        self.world_id = world_id

    def add(self, item: DBItem) -> None:
        """Add a new item to the database."""
        self.session.add(item)
        self.session.flush()

    def get(self, item_id: str) -> Optional[DBItem]:
        """Get item by ID."""
        return (
            self.session.query(DBItem)
            .filter(DBItem.id == item_id, DBItem.world_id == self.world_id)
            .first()
        )

    def get_by_room(self, room_id: str) -> list[DBItem]:
        """Get all items in a specific room."""
        return (
            self.session.query(DBItem)
            .filter(DBItem.room_id == room_id, DBItem.world_id == self.world_id)
            .all()
        )

    def get_uncollected_in_room(self, room_id: str) -> list[DBItem]:
        """Get uncollected items in a room."""
        return (
            self.session.query(DBItem)
            .filter(
                DBItem.room_id == room_id,
                DBItem.world_id == self.world_id,
                DBItem.is_collected == False,
            )
            .all()
        )

    def get_all_treasures(self) -> list[DBItem]:
        """Get all treasure items in the world."""
        return (
            self.session.query(DBItem)
            .filter(DBItem.world_id == self.world_id, DBItem.item_type == "TREASURE")
            .all()
        )

    def get_collected_by_player(self, player_id: str) -> list[DBItem]:
        """Get all items collected by a player."""
        return (
            self.session.query(DBItem)
            .filter(
                DBItem.world_id == self.world_id,
                DBItem.collected_by_player_id == player_id,
            )
            .all()
        )

    def count_treasures(self) -> int:
        """Count total treasures in world."""
        return (
            self.session.query(DBItem)
            .filter(DBItem.world_id == self.world_id, DBItem.item_type == "TREASURE")
            .count()
        )

    def count_collected_treasures(self, player_id: str) -> int:
        """Count treasures collected by player."""
        return (
            self.session.query(DBItem)
            .filter(
                DBItem.world_id == self.world_id,
                DBItem.item_type == "TREASURE",
                DBItem.collected_by_player_id == player_id,
                DBItem.is_collected == True,
            )
            .count()
        )

    def update(self, item: DBItem) -> None:
        """Update item in database."""
        self.session.flush()

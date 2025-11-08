"""
Repository for World persistence.
"""

from typing import Optional

from sqlalchemy.orm import Session

from database.models import DBWorld


class WorldRepository:
    """Repository for managing world persistence."""

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    def get(self, world_id: str) -> Optional[DBWorld]:
        """Get a world by ID."""
        return self.session.query(DBWorld).filter_by(id=world_id).first()

    def get_all(self) -> list[DBWorld]:
        """Get all worlds."""
        return self.session.query(DBWorld).all()

    def add(self, world: DBWorld) -> None:
        """Add a new world."""
        self.session.add(world)
        self.session.commit()

    def update(self, world: DBWorld) -> None:
        """Update an existing world."""
        self.session.add(world)
        self.session.commit()

    def delete(self, world_id: str) -> None:
        """Delete a world by ID."""
        world = self.get(world_id)
        if world:
            self.session.delete(world)
            self.session.commit()

    def exists(self, world_id: str) -> bool:
        """Check if a world exists."""
        return self.session.query(DBWorld).filter_by(id=world_id).count() > 0

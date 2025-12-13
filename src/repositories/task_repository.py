"""
Repository for managing world generation tasks in V3.
"""

from typing import Optional

from sqlalchemy.orm import Session

from database.models import DBWorldGenerationTask


class TaskRepository:
    """Repository for world generation task operations."""

    def __init__(self, session: Session):
        """
        Initialize repository.

        Args:
            session: Database session
        """
        self.session = session

    def add(self, task: DBWorldGenerationTask) -> None:
        """Add a new task to the database."""
        self.session.add(task)
        self.session.flush()

    def get(self, world_id: str) -> Optional[DBWorldGenerationTask]:
        """Get task by world ID."""
        return (
            self.session.query(DBWorldGenerationTask)
            .filter(DBWorldGenerationTask.world_id == world_id)
            .first()
        )

    def update(self, task: DBWorldGenerationTask) -> None:
        """Update task in database."""
        self.session.flush()

    def delete(self, world_id: str) -> None:
        """Delete task by world ID."""
        task = self.get(world_id)
        if task:
            self.session.delete(task)
            self.session.flush()

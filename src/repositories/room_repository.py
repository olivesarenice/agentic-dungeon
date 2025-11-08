"""
Repository for Room persistence with domain model conversion.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from database.models import DBRoom, DBRoomPath
from models import Room


class RoomRepository:
    """Repository for managing room persistence."""

    def __init__(self, session: Session, world_id: str):
        """
        Initialize repository with database session and world ID.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this repository operates on
        """
        self.session = session
        self.world_id = world_id

    def get(self, room_id: str) -> Optional[Room]:
        """
        Get a room by ID, converted to domain model.

        Args:
            room_id: The room ID

        Returns:
            Room domain model or None
        """
        db_room = (
            self.session.query(DBRoom)
            .options(joinedload(DBRoom.paths))
            .filter_by(id=room_id, world_id=self.world_id)
            .first()
        )

        if not db_room:
            return None

        return self._to_domain(db_room)

    def get_by_coords(self, x: int, y: int) -> Optional[Room]:
        """
        Get a room by coordinates.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Room domain model or None
        """
        db_room = (
            self.session.query(DBRoom)
            .options(joinedload(DBRoom.paths))
            .filter_by(world_id=self.world_id, coords_x=x, coords_y=y)
            .first()
        )

        if not db_room:
            return None

        return self._to_domain(db_room)

    def add(self, room: Room) -> None:
        """
        Add a new room to the database.

        Args:
            room: Room domain model to persist
        """
        db_room = self._to_db(room)
        self.session.add(db_room)

        # Add paths
        for direction, connected_room_id in room.paths.items():
            db_path = DBRoomPath(
                room_id=room.id,
                direction=direction,
                connected_room_id=connected_room_id,
            )
            self.session.add(db_path)

        self.session.commit()

    def update(self, room: Room) -> None:
        """
        Update an existing room in the database.

        Args:
            room: Room domain model with updated data
        """
        db_room = (
            self.session.query(DBRoom)
            .filter_by(id=room.id, world_id=self.world_id)
            .first()
        )

        if db_room:
            db_room.name = room.name
            db_room.description = room.description
            db_room.coords_x = room.coords[0]
            db_room.coords_y = room.coords[1]

            # Update paths - delete old, add new
            self.session.query(DBRoomPath).filter_by(room_id=room.id).delete()
            for direction, connected_room_id in room.paths.items():
                db_path = DBRoomPath(
                    room_id=room.id,
                    direction=direction,
                    connected_room_id=connected_room_id,
                )
                self.session.add(db_path)

            self.session.commit()

    def exists(self, room_id: str) -> bool:
        """Check if a room exists."""
        return (
            self.session.query(DBRoom)
            .filter_by(id=room_id, world_id=self.world_id)
            .count()
            > 0
        )

    def get_all_ids(self) -> list[str]:
        """Get list of all room IDs in this world."""
        rooms = self.session.query(DBRoom.id).filter_by(world_id=self.world_id).all()
        return [room.id for room in rooms]

    def get_all(self) -> list[Room]:
        """Get all rooms in this world as domain models."""
        db_rooms = (
            self.session.query(DBRoom)
            .options(joinedload(DBRoom.paths))
            .filter_by(world_id=self.world_id)
            .all()
        )
        return [self._to_domain(db_room) for db_room in db_rooms]

    def get_map(self) -> dict[tuple[int, int], str]:
        """Get coordinate to room_id mapping."""
        rooms = (
            self.session.query(DBRoom.coords_x, DBRoom.coords_y, DBRoom.id)
            .filter_by(world_id=self.world_id)
            .all()
        )
        return {(room.coords_x, room.coords_y): room.id for room in rooms}

    def _to_domain(self, db_room: DBRoom) -> Room:
        """
        Convert database model to domain model.

        Args:
            db_room: Database room model

        Returns:
            Domain room model
        """
        room = Room(coords=(db_room.coords_x, db_room.coords_y))
        room.id = db_room.id
        room.name = db_room.name
        room.description = db_room.description

        # Convert paths
        room.paths = {path.direction: path.connected_room_id for path in db_room.paths}

        # Note: players_inside will be populated separately when needed
        room.players_inside = set()

        return room

    def _to_db(self, room: Room) -> DBRoom:
        """
        Convert domain model to database model.

        Args:
            room: Domain room model

        Returns:
            Database room model
        """
        return DBRoom(
            id=room.id,
            world_id=self.world_id,
            name=room.name,
            coords_x=room.coords[0],
            coords_y=room.coords[1],
            description=room.description,
            created_at=datetime.now(),
        )

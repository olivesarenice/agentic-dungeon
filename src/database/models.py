"""
SQLAlchemy database models for persistence.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import Base


class DBWorld(Base):
    """Database model for game worlds/sessions."""

    __tablename__ = "worlds"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_played_at = Column(DateTime, nullable=False, default=datetime.now)
    starting_coords_x = Column(Integer, nullable=False, default=0)
    starting_coords_y = Column(Integer, nullable=False, default=0)
    settings_json = Column(Text)

    # Relationships
    rooms = relationship("DBRoom", back_populates="world", cascade="all, delete-orphan")
    players = relationship(
        "DBPlayer", back_populates="world", cascade="all, delete-orphan"
    )
    events = relationship(
        "DBGameEvent", back_populates="world", cascade="all, delete-orphan"
    )


class DBRoom(Base):
    """Database model for rooms."""

    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("world_id", "coords_x", "coords_y"),)

    id = Column(String, primary_key=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False)
    name = Column(String, nullable=False)
    coords_x = Column(Integer, nullable=False)
    coords_y = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    world = relationship("DBWorld", back_populates="rooms")
    players = relationship("DBPlayer", back_populates="current_room")
    paths = relationship(
        "DBRoomPath",
        foreign_keys="DBRoomPath.room_id",
        back_populates="from_room",
        cascade="all, delete-orphan",
    )


class DBRoomPath(Base):
    """Database model for room connections/paths."""

    __tablename__ = "room_paths"
    __table_args__ = (UniqueConstraint("room_id", "direction"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    direction = Column(String, nullable=False)  # 'N', 'S', 'E', 'W'
    connected_room_id = Column(String, ForeignKey("rooms.id"))

    # Relationships
    from_room = relationship("DBRoom", foreign_keys=[room_id], back_populates="paths")
    to_room = relationship("DBRoom", foreign_keys=[connected_room_id])


class DBPlayer(Base):
    """Database model for players."""

    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("world_id", "name"),)

    id = Column(String, primary_key=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False)
    name = Column(String, nullable=False)
    current_room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    player_type = Column(String, nullable=False)  # 'HUMAN' or 'NPC'
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    world = relationship("DBWorld", back_populates="players")
    current_room = relationship("DBRoom", back_populates="players")
    history = relationship(
        "DBPlayerHistory", back_populates="player", cascade="all, delete-orphan"
    )
    known_players = relationship(
        "DBPlayerKnownPlayer",
        foreign_keys="DBPlayerKnownPlayer.observer_id",
        back_populates="observer",
        cascade="all, delete-orphan",
    )
    known_rooms = relationship(
        "DBPlayerKnownRoom", back_populates="player", cascade="all, delete-orphan"
    )


class DBPlayerHistory(Base):
    """Database model for player movement history."""

    __tablename__ = "player_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    from_room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    action = Column(String, nullable=False)
    to_room_id = Column(String, ForeignKey("rooms.id"))
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    player = relationship("DBPlayer", back_populates="history")
    from_room = relationship("DBRoom", foreign_keys=[from_room_id])
    to_room = relationship("DBRoom", foreign_keys=[to_room_id])


class DBGameEvent(Base):
    """Database model for game events."""

    __tablename__ = "game_events"
    __table_args__ = (
        Index("idx_events_room", "room_id", "timestamp"),
        Index("idx_events_actor", "actor_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    actor_id = Column(String, ForeignKey("players.id"), nullable=False)
    actor_name = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    world = relationship("DBWorld", back_populates="events")
    room = relationship("DBRoom")
    actor = relationship("DBPlayer")
    witnesses = relationship(
        "DBPlayer",
        secondary="event_witnesses",
        backref="witnessed_events",
    )


class DBEventWitness(Base):
    """Database model for event witnesses (many-to-many)."""

    __tablename__ = "event_witnesses"

    event_id = Column(Integer, ForeignKey("game_events.id"), primary_key=True)
    player_id = Column(String, ForeignKey("players.id"), primary_key=True)


class DBPlayerKnownPlayer(Base):
    """Database model for player memory about other players."""

    __tablename__ = "player_known_players"
    __table_args__ = (UniqueConstraint("observer_id", "known_player_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    observer_id = Column(String, ForeignKey("players.id"), nullable=False)
    known_player_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    last_seen_room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    observer = relationship("DBPlayer", back_populates="known_players")
    last_seen_room = relationship("DBRoom")


class DBPlayerKnownRoom(Base):
    """Database model for player memory about rooms."""

    __tablename__ = "player_known_rooms"
    __table_args__ = (UniqueConstraint("player_id", "room_id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    description = Column(Text, nullable=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    player = relationship("DBPlayer", back_populates="known_rooms")
    room = relationship("DBRoom")

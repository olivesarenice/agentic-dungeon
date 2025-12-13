"""
SQLAlchemy database models for V3.
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
    theme = Column(String, nullable=True)
    art_style = Column(String, nullable=True, default="retro_anime")

    # V3: Grid-based generation
    grid_size = Column(Integer, nullable=False, default=3)  # 3, 5, or 7
    total_treasures = Column(Integer, default=0)
    generation_status = Column(
        String, default="PENDING"
    )  # PENDING, GENERATING, COMPLETE, FAILED

    # Completion tracking
    is_complete = Column(Boolean, default=False)
    completed_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_played_at = Column(DateTime, nullable=False, default=datetime.now)

    # Starting position
    starting_coords_x = Column(Integer, nullable=False, default=0)
    starting_coords_y = Column(Integer, nullable=False, default=0)

    # Relationships
    rooms = relationship("DBRoom", back_populates="world", cascade="all, delete-orphan")
    players = relationship(
        "DBPlayer", back_populates="world", cascade="all, delete-orphan"
    )
    events = relationship(
        "DBGameEvent", back_populates="world", cascade="all, delete-orphan"
    )
    items = relationship("DBItem", back_populates="world", cascade="all, delete-orphan")


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

    # V3: Room metadata
    image_filepath = Column(String, nullable=True)
    has_treasure = Column(Boolean, default=False)
    is_starting_room = Column(Boolean, default=False)

    # Relationships
    world = relationship("DBWorld", back_populates="rooms")
    players = relationship("DBPlayer", back_populates="current_room")
    items = relationship("DBItem", back_populates="room", cascade="all, delete-orphan")
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

    # NPC Personality (only for NPCs)
    personality_type = Column(String)  # 'explorer', 'homebody', 'hostile', 'helpful'

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


class DBItem(Base):
    """V3: Items that can be collected in the game."""

    __tablename__ = "items"

    id = Column(String, primary_key=True)
    world_id = Column(String, ForeignKey("worlds.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)

    # Item details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    item_type = Column(String, nullable=False, default="TREASURE")
    interaction_hint = Column(
        String, nullable=False
    )  # What player should INTERACT with

    # Collection state
    is_collected = Column(Boolean, default=False)
    collected_by_player_id = Column(String, ForeignKey("players.id"))
    collected_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    world = relationship("DBWorld", back_populates="items")
    room = relationship("DBRoom", back_populates="items")
    collected_by = relationship("DBPlayer", foreign_keys=[collected_by_player_id])


class DBWorldGenerationTask(Base):
    """V3: Track async world generation progress."""

    __tablename__ = "world_generation_tasks"

    world_id = Column(String, ForeignKey("worlds.id"), primary_key=True)
    status = Column(String, nullable=False)  # GENERATING, COMPLETE, FAILED
    progress_percent = Column(Integer, default=0)
    current_step = Column(String)
    total_rooms = Column(Integer, nullable=False)
    generated_rooms = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)

    # Relationship
    world = relationship("DBWorld")


class DBUserSession(Base):
    """V3: Track user sessions via cookies."""

    __tablename__ = "user_sessions"

    session_id = Column(String, primary_key=True)
    current_world_id = Column(String, ForeignKey("worlds.id"))
    current_player_id = Column(String, ForeignKey("players.id"))
    created_at = Column(DateTime, default=datetime.now)
    last_active_at = Column(DateTime, default=datetime.now)

    # Relationships
    world = relationship("DBWorld")
    player = relationship("DBPlayer")


class DBNarration(Base):
    """Database model for voiceover narrations."""

    __tablename__ = "narrations"
    __table_args__ = (Index("idx_narrations_player", "player_id", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.id"), nullable=False)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False)
    narration_text = Column(Text, nullable=False)
    narration_type = Column(String, nullable=False)  # MOVE, ACTION, ENTRY
    audio_filepath = Column(String, nullable=True)  # Path to generated audio file
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    # Relationships
    player = relationship("DBPlayer")
    room = relationship("DBRoom")

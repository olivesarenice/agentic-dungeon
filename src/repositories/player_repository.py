"""
Repository for Player persistence with domain model conversion.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from config.enums import PlayerType
from controllers import AIController, HumanController
from database.models import (
    DBPlayer,
    DBPlayerHistory,
    DBPlayerKnownPlayer,
    DBPlayerKnownRoom,
)
from llm import create_llm_module
from models import Memory, Player, PlayerEntry, RoomEntry


class PlayerRepository:
    """Repository for managing player persistence."""

    def __init__(self, session: Session, world_id: str):
        """
        Initialize repository with database session and world ID.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this repository operates on
        """
        self.session = session
        self.world_id = world_id

    def get(self, player_id: str) -> Optional[Player]:
        """
        Get a player by ID, converted to domain model.

        Args:
            player_id: The player ID

        Returns:
            Player domain model or None
        """
        db_player = (
            self.session.query(DBPlayer)
            .options(
                joinedload(DBPlayer.known_players),
                joinedload(DBPlayer.known_rooms),
                joinedload(DBPlayer.history),
            )
            .filter_by(id=player_id, world_id=self.world_id)
            .first()
        )

        if not db_player:
            return None

        return self._to_domain(db_player)

    def get_by_name(self, name: str) -> Optional[Player]:
        """
        Get a player by name.

        Args:
            name: Player name

        Returns:
            Player domain model or None
        """
        db_player = (
            self.session.query(DBPlayer)
            .options(
                joinedload(DBPlayer.known_players),
                joinedload(DBPlayer.known_rooms),
                joinedload(DBPlayer.history),
            )
            .filter_by(name=name, world_id=self.world_id)
            .first()
        )

        if not db_player:
            return None

        return self._to_domain(db_player)

    def add(self, player: Player) -> None:
        """
        Add a new player to the database.

        Args:
            player: Player domain model to persist
        """
        db_player = self._to_db(player)
        self.session.add(db_player)
        self.session.commit()

    def update(self, player: Player) -> None:
        """
        Update an existing player in the database.

        Args:
            player: Player domain model with updated data
        """
        db_player = (
            self.session.query(DBPlayer)
            .filter_by(id=player.id, world_id=self.world_id)
            .first()
        )

        if db_player:
            db_player.name = player.name
            db_player.current_room_id = player.room_id
            db_player.description = player.description
            db_player.player_type = player.player_type.value

            # Update personality if NPC
            if player.personality:
                db_player.personality_type = player.personality.personality_type.value
            else:
                db_player.personality_type = None

            # Update memory - known players
            self.session.query(DBPlayerKnownPlayer).filter_by(
                observer_id=player.id
            ).delete()
            for player_id, entry in player.memory.known_players.items():
                db_known = DBPlayerKnownPlayer(
                    observer_id=player.id,
                    known_player_name=entry.name,
                    description=entry.description,
                    last_seen_room_id=player.room_id,  # Current room as fallback
                    last_updated=datetime.now(),
                )
                self.session.add(db_known)

            # Update memory - known rooms
            self.session.query(DBPlayerKnownRoom).filter_by(
                player_id=player.id
            ).delete()
            for room_id, entry in player.memory.known_rooms.items():
                db_known_room = DBPlayerKnownRoom(
                    player_id=player.id,
                    room_id=room_id,
                    description=entry.description,
                    last_updated=datetime.now(),
                )
                self.session.add(db_known_room)

            self.session.commit()

    def add_history_entry(
        self, player_id: str, from_room_id: str, action: str, to_room_id: str = None
    ) -> None:
        """
        Add a history entry for a player.

        Args:
            player_id: Player ID
            from_room_id: Starting room ID
            action: Action taken (direction or action name)
            to_room_id: Destination room ID (for moves)
        """
        history_entry = DBPlayerHistory(
            player_id=player_id,
            from_room_id=from_room_id,
            action=action,
            to_room_id=to_room_id,
            timestamp=datetime.now(),
        )
        self.session.add(history_entry)
        self.session.commit()

    def exists(self, player_id: str) -> bool:
        """Check if a player exists."""
        return (
            self.session.query(DBPlayer)
            .filter_by(id=player_id, world_id=self.world_id)
            .count()
            > 0
        )

    def name_exists(self, name: str) -> bool:
        """Check if a player name exists in this world."""
        return (
            self.session.query(DBPlayer)
            .filter_by(name=name, world_id=self.world_id)
            .count()
            > 0
        )

    def get_location(self, player_id: str) -> Optional[str]:
        """Get player's current room ID."""
        result = (
            self.session.query(DBPlayer.current_room_id)
            .filter_by(id=player_id, world_id=self.world_id)
            .first()
        )
        return result.current_room_id if result else None

    def update_location(self, player_id: str, room_id: str) -> None:
        """
        Update player's current room.

        Args:
            player_id: Player ID
            room_id: New room ID
        """
        db_player = (
            self.session.query(DBPlayer)
            .filter_by(id=player_id, world_id=self.world_id)
            .first()
        )
        if db_player:
            db_player.current_room_id = room_id
            self.session.commit()

    def get_all(self) -> dict[str, Player]:
        """Get all players in this world as domain models."""
        db_players = (
            self.session.query(DBPlayer)
            .options(
                joinedload(DBPlayer.known_players),
                joinedload(DBPlayer.known_rooms),
            )
            .filter_by(world_id=self.world_id)
            .all()
        )
        return {db_player.id: self._to_domain(db_player) for db_player in db_players}

    def get_all_ids(self) -> list[str]:
        """Get list of all player IDs in this world."""
        players = (
            self.session.query(DBPlayer.id).filter_by(world_id=self.world_id).all()
        )
        return [player.id for player in players]

    def count(self) -> int:
        """Get count of players in this world."""
        return self.session.query(DBPlayer).filter_by(world_id=self.world_id).count()

    def _to_domain(self, db_player: DBPlayer) -> Player:
        """
        Convert database model to domain model.

        Args:
            db_player: Database player model

        Returns:
            Domain player model
        """
        from models import NPCPersonality, PersonalityType

        # Determine player type
        player_type = PlayerType(db_player.player_type)

        # Restore personality for NPCs
        personality = None
        if player_type == PlayerType.NPC and db_player.personality_type:
            try:
                personality_type = PersonalityType(db_player.personality_type)
                personality = NPCPersonality(personality_type=personality_type)
            except ValueError:
                # Invalid personality type, will generate random one
                pass

        # Create player with personality
        player = Player(
            name=db_player.name,
            room_id=db_player.current_room_id,
            controller=None,  # Set below
            player_type=player_type,
            personality=personality,
        )
        player.id = db_player.id
        player.description = db_player.description

        # Create appropriate controller with player reference
        if player_type == PlayerType.HUMAN:
            controller = HumanController()
        elif player_type == PlayerType.NPC:
            llm_module = create_llm_module(Player.DEFAULT_LLM_SYSTEM_PROMPT)
            controller = AIController(llm_module, player=player)
        else:
            raise ValueError(f"Unknown player type: {player_type}")

        player.controller = controller

        # Restore memory - known players
        for db_known in db_player.known_players:
            player_entry = PlayerEntry(
                name=db_known.known_player_name,
                description=db_known.description,
                last_seen_room_id=db_known.last_seen_room_id,
            )
            # Use the known_player_name as the key
            player.memory.known_players[db_known.known_player_name] = player_entry

        # Restore memory - known rooms
        for db_known_room in db_player.known_rooms:
            room_entry = RoomEntry(
                id=db_known_room.room_id,
                name=db_known_room.room_id,  # Use room_id as fallback for name
                description=db_known_room.description,
            )
            player.memory.known_rooms[db_known_room.room_id] = room_entry

        # Restore history (limited to recent entries to avoid memory issues)
        recent_history = (
            self.session.query(DBPlayerHistory)
            .filter_by(player_id=db_player.id)
            .order_by(DBPlayerHistory.timestamp.desc())
            .limit(50)
            .all()
        )
        player.history = [
            f"{h.action} from {h.from_room_id}"
            + (f" to {h.to_room_id}" if h.to_room_id else "")
            for h in reversed(recent_history)
        ]

        return player

    def _to_db(self, player: Player) -> DBPlayer:
        """
        Convert domain model to database model.

        Args:
            player: Domain player model

        Returns:
            Database player model
        """
        # Get personality type value if NPC has personality
        personality_type_value = None
        if player.personality:
            personality_type_value = player.personality.personality_type.value

        return DBPlayer(
            id=player.id,
            world_id=self.world_id,
            name=player.name,
            current_room_id=player.room_id,
            player_type=player.player_type.value,
            description=player.description,
            personality_type=personality_type_value,
            created_at=datetime.now(),
        )

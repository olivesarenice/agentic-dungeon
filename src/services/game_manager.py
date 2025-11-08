"""
Game manager - orchestrates all game services and manages players using database persistence.
"""

import random
from typing import Optional

from sqlalchemy.orm import Session

from config.enums import PlayerType
from controllers import AIController, HumanController
from llm import create_llm_module
from models import Player
from rendering import CLIRenderer
from repositories import PlayerRepository
from services.event_bus import EventBus
from services.turn_system import TurnSystem
from services.world_generator import WorldGenerator


class GameManager:
    """
    High-level game orchestrator.
    Coordinates all services and manages player state using database.
    """

    def __init__(self, session: Session, world_id: str):
        """
        Initialize game manager with database session.

        Args:
            session: SQLAlchemy session
            world_id: ID of the world this manager operates on
        """
        print("Initializing game...")

        self.session = session
        self.world_id = world_id

        # Initialize repositories
        self.player_repo = PlayerRepository(session, world_id)

        # Initialize services
        self.world_generator = WorldGenerator(session, world_id)
        self.event_bus = EventBus(session, world_id)
        self.renderer = CLIRenderer()
        self.turn_system = TurnSystem(
            self.world_generator, self.event_bus, self.renderer, self.player_repo
        )

        print("Game initialized.")

    def create_world(self, starting_coords: tuple[int, int] = (0, 0)) -> None:
        """
        Create the game world.

        Args:
            starting_coords: Starting room coordinates

        Time Complexity: O(1)
        """
        # Check if world already has rooms
        if self.world_generator.get_all_room_ids():
            print("World already exists, skipping creation.")
            return

        self.world_generator.create_world(starting_coords)

    def create_player(
        self, player_name: str, player_type: PlayerType
    ) -> Optional[Player]:
        """
        Create a new player with appropriate controller.

        Args:
            player_name: Name of the player
            player_type: Type of player (HUMAN or NPC)

        Returns:
            Created Player instance, or None if creation failed

        Time Complexity: O(1)
        """
        if not player_name:
            raise ValueError("Player name cannot be empty")

        print(f"Creating player: {player_name}")

        # Check if player already exists
        if self.player_repo.name_exists(player_name):
            print(f"Player with name {player_name} already exists.")
            return None

        # Get available room IDs
        room_ids = self.world_generator.get_all_room_ids()
        if not room_ids:
            raise ValueError("Cannot create player: No rooms exist in the world")

        # Random starting room
        starting_room_id = random.choice(room_ids)
        starting_room = self.world_generator.get_room(starting_room_id)

        if not starting_room:
            raise ValueError(f"Starting room {starting_room_id} not found")

        print(f"Player {player_name} starting in room {starting_room.name}")

        # Create appropriate controller
        if player_type == PlayerType.HUMAN:
            controller = HumanController()
        elif player_type == PlayerType.NPC:
            npc_llm = create_llm_module(Player.DEFAULT_LLM_SYSTEM_PROMPT)
            controller = AIController(npc_llm)
        else:
            raise ValueError(f"Unknown player type: {player_type}")

        # Create player
        player = Player(
            name=player_name,
            room_id=starting_room.id,
            controller=controller,
            player_type=player_type,
        )

        print(f"Created player {player_name}, description: {player.description}")

        # Save player to database
        self.player_repo.add(player)

        # Update room occupancy (in memory only for now)
        starting_room.players_inside.add(player.id)

        print(f"Player {player_name} created with ID {player.id}.")
        return player

    def run(self) -> None:
        """
        Start the main game loop.

        Time Complexity: O(N_players * (1 + N_new_rooms_per_turn)) per round
        """
        # Load all players from database
        players_map = self.player_repo.get_all()

        # Run game loop (room occupancy populated dynamically each turn)
        self.turn_system.run_game_loop(players_map)

    def get_players(self) -> dict[str, Player]:
        """Get all players from database."""
        return self.player_repo.get_all()

    def get_player(self, player_id: str) -> Optional[Player]:
        """Get a specific player by ID from database."""
        return self.player_repo.get(player_id)

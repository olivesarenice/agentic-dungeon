"""
Main entry point for the Agentic Dungeon game with database persistence.
"""

import uuid
from datetime import datetime

from faker import Faker
from tqdm import tqdm

from config.constants import GameConstants
from config.enums import PlayerType
from database.base import init_database
from database.models import DBWorld
from repositories import WorldRepository
from services import GameManager

fake = Faker()


def main():
    """Initialize and run the game with database persistence."""
    print("Starting game with database persistence...")

    # Initialize database
    session = init_database("game.db")
    print("Database initialized.")

    # World management
    world_repo = WorldRepository(session)
    worlds = world_repo.get_all()

    if not worlds:
        # Create new world
        print("\nNo existing worlds found. Creating new world...")
        world_id = str(uuid.uuid4())
        world_name = input("Enter world name (or press Enter for default): ").strip()
        if not world_name:
            world_name = "Default World"

        db_world = DBWorld(
            id=world_id,
            name=world_name,
            created_at=datetime.now(),
            last_played_at=datetime.now(),
            starting_coords_x=0,
            starting_coords_y=0,
        )
        world_repo.add(db_world)
        print(f"Created world: {world_name} (ID: {world_id})")
    else:
        # Show existing worlds
        print("\nExisting worlds:")
        for i, world in enumerate(worlds, 1):
            print(f"{i}. {world.name} (ID: {world.id})")
            print(f"   Created: {world.created_at}")
            print(f"   Last played: {world.last_played_at}")

        choice = input(
            f"\nSelect world (1-{len(worlds)}) or 'new' for new world: "
        ).strip()

        if choice.lower() == "new":
            # Create new world
            world_id = str(uuid.uuid4())
            world_name = input("Enter world name: ").strip()
            if not world_name:
                world_name = f"World {len(worlds) + 1}"

            db_world = DBWorld(
                id=world_id,
                name=world_name,
                created_at=datetime.now(),
                last_played_at=datetime.now(),
                starting_coords_x=0,
                starting_coords_y=0,
            )
            world_repo.add(db_world)
            print(f"Created world: {world_name}")
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(worlds):
                    db_world = worlds[idx]
                    print(f"Loading world: {db_world.name}")
                else:
                    print("Invalid choice, loading first world.")
                    db_world = worlds[0]
            except ValueError:
                print("Invalid input, loading first world.")
                db_world = worlds[0]

        # Update last played time
        db_world.last_played_at = datetime.now()
        world_repo.update(db_world)

    # Initialize game with selected world
    print(f"\nInitializing game for world: {db_world.name}")
    game = GameManager(session, db_world.id)

    # Check if world has rooms
    room_ids = game.world_generator.get_all_room_ids()
    if not room_ids:
        print("Creating new world...")
        game.create_world()
    else:
        print(f"World already has {len(room_ids)} rooms.")

    # Check if world has players
    player_count = game.player_repo.count()
    if player_count == 0:
        print("\nCreating players...")

        n_humans = getattr(GameConstants, "N_HUMANS", 1)
        if n_humans == 1:
            print(
                f"Note: Configured for {n_humans} human players, but only one can play at a time."
            )
            # Create human player
            player_name = input(
                "Enter your character name (or press Enter for OLIVER): "
            ).strip()
            if not player_name:
                player_name = "OLIVER"
            game.create_player(player_name, PlayerType.HUMAN)
        else:
            print(
                f"Note: Configured for {n_humans} human players, but only one can play at a time."
            )
        # Create NPCs
        n_npcs = getattr(GameConstants, "N_NPCS", 3)
        for _ in tqdm(range(n_npcs), desc="Generating NPCs"):
            npc_name = fake.user_name() + "_" + str(fake.random_number(digits=3))
            game.create_player(npc_name, PlayerType.NPC)
    else:
        print(f"World already has {player_count} players.")
        players = game.get_players()
        print("Players:")
        for player_id, player in players.items():
            print(f"  - {player.name} ({player.player_type.value})")

    # Run the game loop
    print("\nStarting game...")
    print("=" * 50)
    game.run()
    print("Game over.")


if __name__ == "__main__":
    main()

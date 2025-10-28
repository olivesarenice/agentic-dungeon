import random

from faker import Faker
from tqdm import tqdm

from config import N_NPCS
from game import Game

fake = Faker()


def main():
    print("Starting game...")
    game = Game()
    game.create_world()

    # # Only 1 player
    player_name = "OLIVER"
    game.create_player(player_name, is_npc=False)

    # All NPCs
    for _ in tqdm(range(N_NPCS), desc="Generating NPCs"):
        npc_name = fake.name_nonbinary()
        game.create_player(npc_name, is_npc=True)

    # Run
    print("Running game...")
    game.run()
    print("Game over.")


if __name__ == "__main__":
    main()

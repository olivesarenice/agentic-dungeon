import random
import time
import traceback

import matplotlib.pyplot as plt
from faker import Faker

from model import Defaults, Graph


# helpers
def checked_input(prompt: str):
    input_str = input(prompt + ": ")
    while input_str == "":
        print("No input found, please try again.")
        input_str = input(prompt)

    if input_str == "/q":
        print("Goodbye!")
        exit()
    else:
        return input_str


def input_user_move(options):
    i = checked_input("Where do you want to go next?").upper()

    while i not in options:
        print("Invalid move")
        i = checked_input("Where do you want to go next?").upper()
    return i


def player_action(player_name, graph, is_npc=False):
    if is_npc:
        current_room = graph._player_current_room(player_name)
        options = current_room.explore_options
        user_move = random.choice(list(options))
    else:
        current_room, dialogue_options = graph.get_navigation_details(player_name)
        print(f"\nYou are in <{current_room.name}>. Where do you want to go now?")
        for direction, description in dialogue_options.items():
            print(f"- {direction} ({description})")
        user_move = input_user_move(dialogue_options.keys())

    new_room_name, _ = graph._process_player_move(player_name, user_move)
    print(f"{player_name} has moved to {new_room_name}")
    return new_room_name


def main():
    print("Welcome to Agentic Dungeon - enter /q to quit anytime.")

    # 1. Initialise the world (this now also creates the plot window)
    graph = Graph()
    graph.create_world()

    # 2. Create player and NPCs
    player_name = "OLIVER"
    graph.create_player(player_name)

    N_NPCS = 5
    fake = Faker()
    npcs = [fake.first_name() for _ in range(N_NPCS)]
    # A small correction to your list comprehension for clarity
    for npc_name in npcs:
        graph.create_player(
            npc_name, is_npc=True
        )  # Assuming create_player is for any character

    print("Starting simulation... Close the plot window to exit.")

    # 3. Main game loop
    try:
        while True:
            # --- Move all characters FIRST ---

            # Move NPCs
            for npc in npcs:
                player_action(npc, graph, is_npc=True)
                graph.update_grid_visualization()
                plt.pause(0.1)

            # Move the player
            player_action(player_name, graph, is_npc=False)
            # --- Now, draw the NEW state of the world ---
            graph.update_grid_visualization()  # Use the corrected method name

            # Pause to control speed and allow the window to redraw
            plt.pause(0.1)  # Increased pause to make movement easier to see

    except Exception as e:
        # This will catch the error that happens when you close the plot window
        print(f"\nSimulation ended. Goodbye! ({e})")
        traceback.print_exc()


if __name__ == "__main__":
    main()

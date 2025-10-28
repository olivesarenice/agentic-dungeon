from dataclasses import dataclass

from models import Action, Move

PAUSE = 0.5
STARTING_ROOM_COORDS = (0, 0)
MAX_ROOM_PATHS = 2  # can only be 2,3,4
N_NPCS = 1


@dataclass
class GameConfigs:
    _moves = {
        "N": Move("N", (0, 1), "S"),
        "S": Move("S", (0, -1), "N"),
        "E": Move("E", (1, 0), "W"),
        "W": Move("W", (-1, 0), "E"),
    }
    _actions = {
        "OBSERVE": Action(
            "OBSERVE",
            description="Take in the room around you, and the players in it.",
            player_prompt="What do you notice?",
            affects_room=False,
            affects_players=False,
        ),
        "TALK": Action(
            "TALK",
            description="Make a comment about something that everyone in the room can hear.",
            player_prompt="What do you say?",
            affects_room=False,
            affects_players=True,
        ),
        "INTERACT": Action(
            "INTERACT",
            description="Modify something about the room. Other people can see you do this. You can only do 1 exact action, nothing more to follow up.",
            player_prompt="What do you do?",
            affects_room=True,
            affects_players=True,
        ),
    }

"""
CLI rendering for the game map.
"""

from typing import Optional

from config.constants import GameConstants
from models import Room


class CLIRenderer:
    """Handles CLI-based rendering of the game map."""

    def __init__(self):
        self.cell_height = GameConstants.CLI_CELL_HEIGHT
        self.cell_width = GameConstants.CLI_CELL_WIDTH

    def draw_map(
        self,
        rooms: dict[str, Room],
        room_map: dict[tuple[int, int], str],
        current_player_id: Optional[str] = None,
        players_map: Optional[dict] = None,
    ) -> None:
        """
        Draw the CLI map.

        Args:
            rooms: Dictionary of room_id -> Room
            room_map: Dictionary of coords -> room_id
            current_player_id: Optional ID of the current player to highlight
            players_map: Optional dictionary of player_id -> Player for showing names
        """
        if not room_map:
            print("The map is empty.")
            return

        coords = list(room_map.keys())
        min_x, max_x = min(c[0] for c in coords), max(c[0] for c in coords)
        min_y, max_y = min(c[1] for c in coords), max(c[1] for c in coords)

        # Use dict with .get() instead of defaultdict
        grid: dict[tuple[int, int], str] = {}

        for (x, y), room_id in room_map.items():
            room = rooms.get(room_id)
            if not room:
                continue

            cx = (x - min_x) * (self.cell_width - 1)
            cy = (max_y - y) * (self.cell_height - 1)

            # Draw room box
            for i in range(self.cell_width):
                grid[cx + i, cy] = "-"
                grid[cx + i, cy + self.cell_height - 1] = "-"
            for i in range(self.cell_height):
                grid[cx, cy + i] = "|"
                grid[cx + self.cell_width - 1, cy + i] = "|"
            grid[cx, cy] = "+"
            grid[cx + self.cell_width - 1, cy] = "+"
            grid[cx, cy + self.cell_height - 1] = "+"
            grid[cx + self.cell_width - 1, cy + self.cell_height - 1] = "+"

            # Draw connections (just gaps, no | or -)
            if "N" in room.paths:
                grid[cx + self.cell_width // 2, cy] = " "
            if "S" in room.paths:
                grid[cx + self.cell_width // 2, cy + self.cell_height - 1] = " "
            if "W" in room.paths:
                grid[cx, cy + self.cell_height // 2] = " "
            if "E" in room.paths:
                grid[cx + self.cell_width - 1, cy + self.cell_height // 2] = " "

            # Draw players (AFTER connections so they don't get overwritten)
            player_chars = []
            for pid in sorted(list(room.players_inside)):
                if pid == current_player_id:
                    player_chars.append("@")  # Current player
                else:
                    # Get first letter of player name
                    if players_map and pid in players_map:
                        player_name = players_map[pid].name
                        player_chars.append(player_name[0].upper())
                    else:
                        player_chars.append("?")  # Unknown player

            player_str = "".join(player_chars)
            # Place player string in the middle of the room
            start_pos = (self.cell_width - len(player_str)) // 2
            for i, char in enumerate(player_str):
                grid[cx + start_pos + i, cy + (self.cell_height // 2)] = char

        grid_w = (max_x - min_x + 1) * (self.cell_width - 1) + 1
        grid_h = (max_y - min_y + 1) * (self.cell_height - 1) + 1

        header = " MAP (@: You, Letters: NPCs) "
        print("\n" + f"{header:=^{grid_w}}")
        for r in range(grid_h):
            line = "".join([grid.get((c, r), " ") for c in range(grid_w)])
            print(line)
        print("=" * grid_w + "\n")

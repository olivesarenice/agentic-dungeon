"""
Turn system for managing player turns and actions.
"""

from typing import Optional

from config import GameConfigs
from config.enums import ActionType, DecisionType
from llm import PromptTemplates
from models import Player, Room
from rendering import CLIRenderer
from repositories import PlayerRepository
from services.event_bus import EventBus
from services.world_generator import WorldGenerator


class TurnSystem:
    """
    Manages turn execution including player moves and actions.
    Uses database for persistence.
    """

    def __init__(
        self,
        world_generator: WorldGenerator,
        event_bus: EventBus,
        renderer: CLIRenderer,
        player_repo: PlayerRepository,
    ):
        """
        Initialize turn system.

        Args:
            world_generator: World generator for room operations
            event_bus: Event bus for distributing events
            renderer: Renderer for displaying the map
            player_repo: Player repository for persistence
        """
        self.world_generator = world_generator
        self.event_bus = event_bus
        self.renderer = renderer
        self.player_repo = player_repo

    def _populate_room_occupancy(
        self, rooms_dict: dict[str, Room], players_map: dict[str, Player]
    ) -> None:
        """
        Populate players_inside for all rooms based on current player locations.

        Args:
            rooms_dict: Dictionary of room_id -> Room
            players_map: Dictionary of player_id -> Player
        """
        # Clear all occupancies
        for room in rooms_dict.values():
            room.players_inside = set()

        # Populate from player locations
        for player_id, player in players_map.items():
            if player.room_id in rooms_dict:
                rooms_dict[player.room_id].players_inside.add(player_id)

    def get_player_moves(self, player: Player) -> list[str]:
        """
        Get available moves for a player.

        Args:
            player: The player

        Returns:
            List of available direction strings

        Time Complexity: O(1)
        """
        current_room = self.world_generator.get_room(player.room_id)
        if not current_room:
            return []
        return list(current_room.paths.keys())

    def get_player_actions(
        self, player: Player, other_players_in_room: bool
    ) -> list[str]:
        """
        Get available actions for a player.

        Args:
            player: The player
            other_players_in_room: Whether there are other players in the room

        Returns:
            List of available action keys
        """
        options = list(GameConfigs._actions.keys())
        if not other_players_in_room:
            # No other players in the room, cannot TALK
            if ActionType.TALK.value in options:
                options.remove(ActionType.TALK.value)
        return options

    def process_player_move(
        self,
        player: Player,
        direction: str,
        players_map: dict[str, Player],
    ) -> bool:
        """
        Process a player's movement.

        Args:
            player: The player moving
            direction: Direction to move
            players_map: Dictionary of all players

        Returns:
            True if successful

        Time Complexity: O(1)
        """
        print(f"Processing move for player {player.id}: {direction}")

        current_room = self.world_generator.get_room(player.room_id)
        if not current_room:
            print(f"Error: Current room {player.room_id} not found")
            return False

        print(f"Player {player.name} is in room {current_room.name}")

        # Calculate next coordinates
        next_coords = self.world_generator._translate(current_room.coords, direction)

        # Check if room exists, create if not
        next_room = self.world_generator.get_room_at_coords(next_coords)
        if not next_room:
            # Create new room
            from_direction = GameConfigs._moves[direction].pole
            next_room = self.world_generator.create_room(
                next_coords, current_room, from_direction
            )
        else:
            print(f"Moving to existing room {next_room.name}")

        # Get witnesses BEFORE player moves (from current player locations)
        witnesses_before = [
            pid
            for pid, p in players_map.items()
            if p.room_id == current_room.id and pid != player.id
        ]

        # Notify witnesses player is leaving
        self.event_bus.notify_player_left_room(
            actor=player,
            room_id=current_room.id,
            witness_ids=witnesses_before,
            players_map=players_map,
        )

        # Update player location
        player.move(current_room.id, direction, next_room.id)

        # Player observes new room
        player.observe(next_room, players_map)

        # **CRITICAL**: Persist player state to database after move
        self.player_repo.update(player)
        self.player_repo.add_history_entry(
            player.id, current_room.id, direction, next_room.id
        )

        # Get witnesses AFTER player moves (from updated player locations)
        witnesses_after = [
            pid
            for pid, p in players_map.items()
            if p.room_id == next_room.id and pid != player.id
        ]

        # Notify witnesses player has entered
        self.event_bus.notify_player_entered_room(
            actor=player,
            room_id=next_room.id,
            witness_ids=witnesses_after,
            players_map=players_map,
        )

        return True

    def process_player_action(
        self,
        player: Player,
        action_key: str,
        players_map: dict[str, Player],
    ) -> bool:
        """
        Process a player's action.

        Args:
            player: The player performing the action
            action_key: The action key (e.g., "TALK", "INTERACT")
            players_map: Dictionary of all players

        Returns:
            True if successful

        Time Complexity: O(N) where N is players in room
        """
        print(f"Processing action for player {player.id}: {action_key}")

        current_room = self.world_generator.get_room(player.room_id)
        if not current_room:
            print(f"Error: Current room {player.room_id} not found")
            return False

        action = GameConfigs._actions[action_key]

        # Use controller to get action details
        action_prompt = player.controller.provide_action_details(action)

        if action.name == ActionType.TALK.value:
            print(
                f"Player {player.name} says: '{action_prompt}' to players in room {current_room.name}"
            )

        elif action.name == ActionType.INTERACT.value:
            print(
                f"Player {player.name} interacts with the room {current_room.name}: {action_prompt}"
            )

            # Update room description to reflect interaction
            prompt = PromptTemplates.ROOM_INTERACTION_UPDATE.substitute(
                interaction=action_prompt, current_description=current_room.description
            )
            dm_description = self.world_generator.dm_generator_module.get_response(
                prompt
            )
            print(
                f"\033[92mRoom {current_room.name} updated description:\nFROM = {current_room.description}\nTO = {dm_description}\033[0m\n"
            )
            current_room.update_description(dm_description)
            # **CRITICAL**: Persist updated room description to database
            self.world_generator.room_repo.update(current_room)

        # Get witnesses (from current player locations)
        witnesses = [
            pid
            for pid, p in players_map.items()
            if p.room_id == current_room.id and pid != player.id
        ]

        # Notify all witnesses
        self.event_bus.notify_player_action(
            actor=player,
            room_id=current_room.id,
            action_type=action.name,
            content=action_prompt,
            witness_ids=witnesses,
            players_map=players_map,
        )

        # Player re-observes the room
        player.observe(current_room, players_map)

        # **CRITICAL**: Persist player state to database after action
        # (player memory may have changed from observing)
        self.player_repo.update(player)

        return True

    def announce_turn_situation(
        self,
        player: Player,
        players_map: dict[str, Player],
        map_dict: dict[tuple[int, int], str],
        rooms_dict: dict[str, Room],
    ) -> None:
        """
        Announce the current situation for a player's turn.

        Args:
            player: The player whose turn it is
            players_map: Dictionary of all players
            map_dict: Coordinate to room_id mapping
            rooms_dict: Dictionary of all rooms (with populated players_inside)
        """
        # Use room from rooms_dict which has populated players_inside
        current_room = rooms_dict.get(player.room_id)
        if not current_room:
            print(f"Error: Current room {player.room_id} not found")
            return

        # Draw map
        self.renderer.draw_map(rooms_dict, map_dict, player.id, players_map)

        # Announce turn
        print(f"\033[93m\n--- Player {player.name}'s Turn ---\033[0m")
        print(f"\033[93mYou are in room: {current_room.name} \n \033[0m")
        print(f"\033[93mRoom description: {current_room.description} \n \033[0m")

        other_players = [
            players_map[pid].name
            for pid in current_room.players_inside
            if pid != player.id
        ]
        if other_players:
            print(f"\033[93mOther players in the room: {other_players}\033[0m")
        else:
            print("\033[93mYou are alone in this room.\033[0m")

    def run_game_loop(
        self,
        players_map: dict[str, Player],
    ) -> None:
        """
        Main game loop.

        Args:
            players_map: Dictionary of player_id -> Player

        Time Complexity: O(N_players * (1 + N_new_rooms_per_turn)) per round
        """
        while True:
            for player_id, player in players_map.items():
                # Get fresh rooms dict and populate occupancy
                rooms_dict = self.world_generator.get_rooms_dict()
                self._populate_room_occupancy(rooms_dict, players_map)

                # Announce situation
                self.announce_turn_situation(
                    player,
                    players_map,
                    self.world_generator.get_map_dict(),
                    rooms_dict,  # Pass the populated rooms_dict
                )

                # Use populated current_room from rooms_dict
                current_room = rooms_dict.get(player.room_id)
                if not current_room:
                    print(f"Error: Player room {player.room_id} not found")
                    continue

                # Get moves and actions available
                available_moves = self.get_player_moves(player)
                has_others = len(current_room.players_inside) > 1
                available_action_keys = self.get_player_actions(player, has_others)

                # Get decision from controller
                context = {
                    "available_directions": available_moves,
                    "available_actions": [
                        GameConfigs._actions[key] for key in available_action_keys
                    ],
                    "current_room": current_room,
                    "player_memory": player.memory,
                }

                # Update context with both options
                full_context = {
                    **context,
                    "available_directions": available_moves,
                    "available_actions": [
                        GameConfigs._actions[key] for key in available_action_keys
                    ],
                }

                # Ask controller: do you want to MOVE or perform an ACTION?
                # Controller should return "MOVE" or an action name like "TALK", "INTERACT", etc.
                decision = player.controller.decide(DecisionType.ACT, full_context)

                if decision in available_moves:
                    # Player chose to MOVE
                    print(f"\nPlayer <{player.name}> chose to MOVE {decision}.")
                    self.process_player_move(player, decision, players_map)
                elif decision in available_action_keys:
                    # Player chose an ACTION
                    print(f"\nPlayer <{player.name}> chose to {decision}.")
                    self.process_player_action(player, decision, players_map)
                else:
                    # Invalid decision, default to first available move
                    print(f"\nInvalid decision '{decision}', defaulting to move.")
                    if available_moves:
                        self.process_player_move(
                            player, available_moves[0], players_map
                        )
                    elif available_action_keys:
                        self.process_player_action(
                            player, available_action_keys[0], players_map
                        )

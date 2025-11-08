"""
Player controller implementations using Strategy Pattern.
Controllers handle decision-making for different player types.
"""

from abc import ABC, abstractmethod
from typing import Optional

from config.constants import GameConstants
from config.enums import ActionType, DecisionType, Direction
from models import Action, Move
from utils import Colors, safe_input


class PlayerController(ABC):
    """
    Abstract base class for player controllers.
    Implements the Strategy Pattern for player decision-making.
    """

    @abstractmethod
    def decide(self, decision_type: DecisionType, context: dict) -> str:
        """
        Make a decision based on the decision type and context.

        Args:
            decision_type: Type of decision (MOVE or ACT)
            context: Context information for the decision

        Returns:
            The decision as a string
        """
        pass

    @abstractmethod
    def provide_action_details(self, action: Action) -> str:
        """
        Provide additional details for an action.

        Args:
            action: The action being performed

        Returns:
            Details string for the action
        """
        pass


class HumanController(PlayerController):
    """Controller for human players using console input."""

    def decide(self, decision_type: DecisionType, context: dict) -> str:
        """Get decision from human player via console input."""
        if decision_type == DecisionType.MOVE:
            return self._decide_move(context)
        elif decision_type == DecisionType.ACT:
            return self._decide_action(context)
        else:
            raise ValueError(f"Unknown decision type: {decision_type}")

    def _decide_move(self, context: dict) -> str:
        """Prompt human player for movement direction."""
        available_directions = context.get("available_directions", [])
        print(
            Colors.player_info(
                f"\nAvailable directions: {', '.join(available_directions)}"
            )
        )
        direction = safe_input(
            "Choose a direction to move (or /q to quit): ", Colors.input_prompt
        ).upper()

        if direction not in available_directions:
            print(
                Colors.player_info(
                    f"Invalid direction. Defaulting to {available_directions[0]}"
                )
            )
            return available_directions[0]

        return direction

    def _decide_action(self, context: dict) -> str:
        """Prompt human player for action choice (MOVE, TALK, or INTERACT)."""
        available_actions = context.get("available_actions", [])
        available_directions = context.get("available_directions", [])

        print(Colors.player_info("\nWhat would you like to do?"))

        options = []
        # Add MOVE option if directions available
        if available_directions:
            options.append(
                ("MOVE", f"Move to another room ({', '.join(available_directions)})")
            )

        # Add other actions
        for action in available_actions:
            options.append((action.name, action.description))

        for i, (name, desc) in enumerate(options, 1):
            print(Colors.player_info(f"{i}. {name}: {desc}"))

        choice = safe_input(
            "Choose an option (number, or /q to quit): ", Colors.input_prompt
        )

        try:
            index = int(choice) - 1
            if 0 <= index < len(options):
                chosen = options[index][0]

                # If MOVE was chosen, ask for direction
                if chosen == "MOVE":
                    return self._decide_move(context)
                else:
                    return chosen
        except ValueError:
            pass

        # Default to first option
        print(Colors.player_info(f"Invalid choice. Defaulting to {options[0][0]}"))
        if options[0][0] == "MOVE":
            return self._decide_move(context)
        return options[0][0]

    def provide_action_details(self, action: Action) -> str:
        """Prompt human player for action details."""
        return safe_input(
            f"{action.player_prompt} (or /q to quit): ", Colors.input_prompt
        )


class AIController(PlayerController):
    """Controller for AI players using LLM."""

    def __init__(self, llm_module):
        """Initialize with LLM module."""
        self.llm_module = llm_module
        self.last_direction: Optional[str] = None

    def _should_move(self) -> bool:
        """
        Randomly decide if NPC should move based on configured probability.

        Returns:
            True if NPC should move, False if should perform action
        """
        import random

        return random.random() < GameConstants.NPC_MOVE_PROBABILITY

    def decide(self, decision_type: DecisionType, context: dict) -> str:
        """Get decision from AI using LLM."""
        if decision_type == DecisionType.MOVE:
            return self._decide_move(context)
        elif decision_type == DecisionType.ACT:
            # Use probability to decide between MOVE and ACTION
            available_directions = context.get("available_directions", [])

            # If no directions available, must choose an action
            if not available_directions:
                return self._decide_action(context)

            # Randomly decide based on NPC_MOVE_PROBABILITY
            if self._should_move():
                # Choose to MOVE - return a direction
                return self._decide_move(context)
            else:
                # Choose an ACTION - return action name
                return self._decide_action(context)
        else:
            raise ValueError(f"Unknown decision type: {decision_type}")

    def _decide_move(self, context: dict) -> str:
        """Use LLM to decide movement direction with backtracking avoidance."""
        available_directions = context.get("available_directions", [])
        current_room = context.get("current_room")
        player_memory = context.get("player_memory")

        # Build context for LLM
        room_info = f"Current room: {current_room.name}\n"
        room_info += f"Description: {current_room.description}\n"
        room_info += f"Available directions: {', '.join(available_directions)}\n"

        # Add memory context if available
        if player_memory and hasattr(player_memory, "known_rooms"):
            visited_rooms = len(player_memory.known_rooms)
            room_info += f"You have visited {visited_rooms} rooms so far.\n"

        # Discourage backtracking
        if self.last_direction:
            try:
                # Look up direction by value (N, S, E, W)
                current_dir = Direction(self.last_direction)
                opposite = current_dir.opposite.value  # Get opposite value (N, S, E, W)
                if opposite in available_directions:
                    room_info += f"\nNote: Going {opposite} would take you back where you came from. Consider exploring new directions when possible.\n"
            except ValueError:
                # Invalid direction, skip backtracking logic
                pass

        prompt = f"{room_info}\nChoose one direction to move: {', '.join(available_directions)}"

        # Get LLM decision
        response = self.llm_module.get_response(prompt).strip().upper()

        # Parse response
        for direction in available_directions:
            if direction in response:
                self.last_direction = direction
                return direction

        # Fallback: prefer non-backtracking direction
        if self.last_direction:
            try:
                current_dir = Direction(self.last_direction)
                opposite_value = current_dir.opposite.value
                non_backtrack = [d for d in available_directions if d != opposite_value]
                if non_backtrack:
                    self.last_direction = non_backtrack[0]
                    return non_backtrack[0]
            except ValueError:
                pass

        # Ultimate fallback
        self.last_direction = available_directions[0]
        return available_directions[0]

    def _decide_action(self, context: dict) -> str:
        """Use LLM to decide action."""
        available_actions = context.get("available_actions", [])
        current_room = context.get("current_room")

        actions_desc = "\n".join(
            [f"- {a.name}: {a.description}" for a in available_actions]
        )

        prompt = f"""You are in {current_room.name}.
{current_room.description}

Available actions:
{actions_desc}

Choose one action by name."""

        response = self.llm_module.get_response(prompt).strip().upper()

        # Parse response
        for action in available_actions:
            if action.name.upper() in response:
                return action.name

        # Fallback
        return available_actions[0].name

    def provide_action_details(self, action: Action) -> str:
        """Use LLM to provide action details."""
        prompt = f"{action.player_prompt}"
        response = self.llm_module.get_response(prompt)
        return response.strip()[: GameConstants.MAX_ACTION_DETAIL_LENGTH]


class MockController(PlayerController):
    """Mock controller for testing purposes."""

    def __init__(self, move_sequence=None, action_sequence=None):
        """
        Initialize with predetermined sequences.

        Args:
            move_sequence: List of moves to return
            action_sequence: List of actions to return
        """
        self.move_sequence = move_sequence or ["N"]
        self.action_sequence = action_sequence or ["OBSERVE"]
        self.move_index = 0
        self.action_index = 0

    def decide(self, decision_type: DecisionType, context: dict) -> str:
        """Return predetermined decision."""
        if decision_type == DecisionType.MOVE:
            move = self.move_sequence[self.move_index % len(self.move_sequence)]
            self.move_index += 1
            return move
        elif decision_type == DecisionType.ACT:
            action = self.action_sequence[self.action_index % len(self.action_sequence)]
            self.action_index += 1
            return action
        else:
            raise ValueError(f"Unknown decision type: {decision_type}")

    def provide_action_details(self, action: Action) -> str:
        """Return mock action details."""
        return f"Mock details for {action.name}"

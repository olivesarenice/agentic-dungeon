# Agentic Dungeon - V2 Improvement TODO List

This document outlines best practices improvements identified during the code review. Items are prioritized by impact and implementation difficulty.

---

## 1. Object Structure & Responsibility Issues

### 🔴 CRITICAL: Circular Dependencies
**Problem**: 
- `models.py` imports from `helpers.py` and `llm.py`
- `config.py` imports `Move` and `Action` from `models.py`
- Creates tight coupling and makes testing difficult

**Solution**: Separate into layers
```
models/       # Pure data classes only
services/     # Game logic, LLM logic
config/       # Configuration only
```

**Priority**: HIGH
**Estimated Effort**: Medium (4-6 hours)

---

### 🔴 CRITICAL: God Object - Game Class
**Problem**: 
- Single class handles world generation, player management, turn logic, rendering, AND event processing
- 400+ lines with mixed responsibilities
- Violates Single Responsibility Principle

**Solution**: Split into specialized classes
```python
class WorldManager:      # Room creation & map management
class PlayerManager:     # Player CRUD operations  
class TurnManager:       # Turn sequencing logic
class EventBus:          # Event handling & distribution
class Renderer:          # CLI visualization
```

**Priority**: HIGH
**Estimated Effort**: Large (8-12 hours)

---

### 🔴 CRITICAL: Player Class - Mixed Concerns
**Problem**:
- UI interaction (`prompt_user_choice`)
- AI decision-making
- Memory management
- State tracking
- All in one class

**Solution**: Use Strategy Pattern
```python
class PlayerController(ABC):
    @abstractmethod
    def decide_action(self, options): pass
    @abstractmethod
    def decide_move(self, options): pass

class HumanController(PlayerController): 
    """Handles input() calls"""
    pass

class AIController(PlayerController): 
    """Handles LLM calls"""
    pass

class Player:
    def __init__(self, controller: PlayerController):
        self.controller = controller
    # Player just manages state, delegates decisions
```

**Priority**: HIGH
**Estimated Effort**: Medium (6-8 hours)

---

## 2. Data Storage Architecture Problems

### 🟡 IMPORTANT: Inconsistent Data Structures
**Problem**:
```python
self._rooms = defaultdict(Room)        # Creates empty rooms on missing keys!
self._map = defaultdict(str)           
self._player_locations = {}            
self._players = defaultdict(Player)    # Creates empty players on missing keys!
```
- `defaultdict(Room)` and `defaultdict(Player)` will create empty instances (dangerous!)
- Mixed use of `defaultdict` and regular `dict`
- No validation on data insertion

**Solution**: Use regular dicts with explicit checks
```python
# Option 1: Regular dicts
self._rooms: dict[str, Room] = {}
self._map: dict[tuple[int, int], str] = {}

# Option 2: Repository pattern (better)
class RoomRepository:
    def get(self, room_id: str) -> Room | None:
        return self._rooms.get(room_id)
    
    def add(self, room: Room) -> None:
        if room.id in self._rooms:
            raise ValueError(f"Room {room.id} already exists")
        self._rooms[room.id] = room
    
    def exists(self, room_id: str) -> bool:
        return room_id in self._rooms
```

**Priority**: HIGH
**Estimated Effort**: Small (2-3 hours)

---

### 🟡 IMPORTANT: Memory as Nested Structures
**Problem**:
- `Memory` class uses nested `defaultdict` and lists
- No query interface
- Hard to search/filter events
- No indexing for performance
- Memory grows unbounded

**Solution**: Add query interface and limits
```python
from collections import deque

class Memory:
    def __init__(self, max_events: int = 100):
        self.known_players: dict[str, PlayerEntry] = {}
        self.known_rooms: dict[str, RoomEntry] = {}
        self.recent_events: deque[GameEvent] = deque(maxlen=max_events)
    
    def query_events(self, 
                    room_id: str = None, 
                    actor_id: str = None,
                    action_type: str = None,
                    limit: int = 10) -> list[GameEvent]:
        """Efficient querying with filters"""
        results = []
        for event in reversed(self.recent_events):
            if room_id and event.room_id != room_id:
                continue
            if actor_id and event.actor_id != actor_id:
                continue
            if action_type and event.action_type != action_type:
                continue
            results.append(event)
            if len(results) >= limit:
                break
        return results
    
    def get_recent_interactions_with(self, player_name: str, limit: int = 5):
        """Get recent interactions with a specific player"""
        pass
```

**Priority**: MEDIUM
**Estimated Effort**: Medium (4-5 hours)

---

### 🟡 IMPORTANT: No Persistence Layer
**Problem**: Cannot save/load game state

**Solution**: Add serialization
```python
from dataclasses import asdict
import json
from datetime import datetime

class GameState:
    def save(self, filepath: str):
        state = {
            'version': '1.0',
            'timestamp': datetime.now().isoformat(),
            'rooms': {rid: asdict(room) for rid, room in self._rooms.items()},
            'players': {pid: self._serialize_player(p) for pid, p in self._players.items()},
            'map': {f"{k[0]},{k[1]}": v for k, v in self._map.items()},
        }
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'GameState':
        with open(filepath, 'r') as f:
            state = json.load(f)
        # Reconstruct game from saved state
        game = cls()
        # ... reconstruction logic
        return game
```

**Priority**: LOW (nice to have)
**Estimated Effort**: Medium (5-6 hours)

---

## 3. Function Design Issues

### 🔴 CRITICAL: Long Parameter Lists
**Problem**: `_create_room(coords, from_room, from_direction)` - growing parameters

**Solution**: Use context objects
```python
@dataclass
class RoomCreationContext:
    coords: tuple[int, int]
    from_room: Room | None = None
    from_direction: str | None = None
    description_override: str | None = None

def _create_room(self, context: RoomCreationContext) -> Room:
    # Much cleaner and extensible
    if context.from_room is not None:
        # ... logic
    pass
```

**Priority**: MEDIUM
**Estimated Effort**: Small (2-3 hours)

---

### 🔴 CRITICAL: Side Effects Everywhere
**Problem**:
- `move()` modifies player history AND room_id
- `process_player_move()` creates rooms, updates locations, notifies witnesses
- `witness()` updates multiple memory structures
- Hard to test, debug, and reason about

**Solution**: Separate queries from commands (CQRS pattern)
```python
# Query (no side effects)
def calculate_next_position(current: tuple, direction: str) -> tuple:
    translation = GameConfigs._moves[direction].translate
    return (current[0] + translation[0], current[1] + translation[1])

def would_create_room(self, coords: tuple) -> bool:
    return coords not in self._map

# Command (explicit side effects grouped together)
def apply_player_move(self, player: Player, from_room: Room, to_room: Room):
    """All mutations in one clearly named method"""
    player.room_id = to_room.id
    player.history.append((from_room.id, "MOVE", to_room.id))
    from_room.players_inside.discard(player.id)
    to_room.players_inside.add(player.id)
    self._player_locations[player.id] = to_room.id
```

**Priority**: HIGH
**Estimated Effort**: Large (8-10 hours)

---

### 🟡 IMPORTANT: Boolean Flag Parameters
**Problem**: `create_player(name, is_npc)` - unclear what True/False means at call site

**Solution**: Use enums
```python
from enum import Enum

class PlayerType(Enum):
    HUMAN = "human"
    NPC = "npc"

def create_player(self, name: str, player_type: PlayerType):
    # Clear usage: 
    # create_player("Alice", PlayerType.HUMAN)
    # create_player("Bob", PlayerType.NPC)
    pass
```

**Priority**: MEDIUM
**Estimated Effort**: Small (1-2 hours)

---

## 4. Type Safety Issues

### 🔴 CRITICAL: Missing Type Hints
**Problem**: Many functions lack return type hints

**Solution**: Add complete type hints
```python
from typing import Optional, Dict, Set, List

def get_player_moves(self, player_id: str) -> List[str]:
    player: Player = self._players[player_id]
    current_room: Room = self._room_from_id(player.room_id)
    return list(current_room.paths.keys())

def _room_from_id(self, room_id: str) -> Room:
    return self._rooms.get(room_id)

def _get_adjacent_rooms(self, room: Room) -> Dict[str, Optional[Room]]:
    pass
```

**Priority**: HIGH
**Estimated Effort**: Medium (3-4 hours to add throughout codebase)

---

### 🟡 IMPORTANT: String-Based Enums
**Problem**: `"MOVE"`, `"ACT"`, `"TALK"`, `"INTERACT"` as strings cause typo bugs

**Solution**: Use Python enums
```python
from enum import Enum

class ActionType(Enum):
    MOVE = "move"
    ACT = "act"
    TALK = "talk"
    INTERACT = "interact"
    OBSERVE = "observe"

class Direction(Enum):
    NORTH = "N"
    SOUTH = "S"
    EAST = "E"
    WEST = "W"
    
    @property
    def opposite(self) -> 'Direction':
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
        }
        return opposites[self]

# Usage:
if action_type == ActionType.MOVE:  # Type-safe!
    direction = Direction.NORTH
    opposite = direction.opposite
```

**Priority**: HIGH
**Estimated Effort**: Medium (3-4 hours)

---

## 5. Error Handling & Validation

### 🔴 CRITICAL: No Validation
**Problem**: Methods don't validate inputs
```python
def move(self, from_room_id: str, action_taken: str, to_room_id: str):
    # No check if rooms exist!
    self.history.append((from_room_id, action_taken))
    self.room_id = to_room_id
```

**Solution**: Add validation
```python
def move(self, from_room: Room, action: str, to_room: Room):
    if not isinstance(from_room, Room):
        raise TypeError("from_room must be a Room instance")
    if not isinstance(to_room, Room):
        raise TypeError("to_room must be a Room instance")
    if not action:
        raise ValueError("action cannot be empty")
    
    self.history.append((from_room.id, action))
    self.room_id = to_room.id

# Or use validation library like pydantic:
from pydantic import BaseModel, validator

class MoveCommand(BaseModel):
    player_id: str
    from_room_id: str
    to_room_id: str
    action: str
    
    @validator('action')
    def action_not_empty(cls, v):
        if not v:
            raise ValueError('action cannot be empty')
        return v
```

**Priority**: HIGH
**Estimated Effort**: Medium (4-6 hours)

---

### 🔴 CRITICAL: Silent Failures
**Problem**: `defaultdict(Room)` creates empty rooms on missing keys - bugs go unnoticed

**Solution**: Fail fast with exceptions
```python
def _room_from_id(self, room_id: str) -> Room:
    room = self._rooms.get(room_id)
    if room is None:
        raise ValueError(f"Room {room_id} not found. Available rooms: {list(self._rooms.keys())[:5]}...")
    return room

def get_player(self, player_id: str) -> Player:
    if player_id not in self._players:
        raise ValueError(f"Player {player_id} not found")
    return self._players[player_id]
```

**Priority**: HIGH
**Estimated Effort**: Small (2-3 hours)

---

## 6. Performance Issues

### 🟡 IMPORTANT: Random Choice on Dict Keys
**Problem**: `random.choice(list(self._rooms.keys()))` - O(N) conversion every time

**Solution**: Keep separate list
```python
class Game:
    def __init__(self):
        self._rooms: dict[str, Room] = {}
        self._room_ids: list[str] = []  # Maintain this list
    
    def _create_room(self, ...):
        room = Room(...)
        self._rooms[room.id] = room
        self._room_ids.append(room.id)  # Update list
        return room
    
    def get_random_room_id(self) -> str:
        return random.choice(self._room_ids)  # O(1)
```

**Priority**: MEDIUM
**Estimated Effort**: Small (1 hour)

---

### 🟡 IMPORTANT: Unbounded Memory Growth
**Problem**: `GameEvent` history grows forever, will cause memory issues

**Solution**: Use deque with maxlen
```python
from collections import deque

@dataclass
class RoomEntry:
    id: str
    name: str
    description: str
    observed_events: deque[GameEvent] = field(
        default_factory=lambda: deque(maxlen=50)  # Only keep last 50
    )

@dataclass
class PlayerEntry:
    name: str
    description: str
    last_seen_room_id: str
    interaction_history: deque[GameEvent] = field(
        default_factory=lambda: deque(maxlen=100)  # Only keep last 100
    )
```

**Priority**: MEDIUM
**Estimated Effort**: Small (1 hour)

---

## 7. Code Organization Issues

### 🔴 CRITICAL: File Structure
**Current Problem**:
```
src/
  models.py      # 300+ lines, multiple classes
  game.py        # 400+ lines, Game class
  config.py
  helpers.py
```

**Solution**: Organize into packages
```
src/
  models/
    __init__.py
    player.py           # Player class
    room.py             # Room class
    memory.py           # Memory, PlayerEntry, RoomEntry
    events.py           # GameEvent
    actions.py          # Move, Action dataclasses
  
  services/
    game_manager.py     # High-level game orchestration
    world_generator.py  # Room creation logic
    turn_system.py      # Turn management
    event_bus.py        # Event distribution
  
  controllers/
    player_controller.py  # PlayerController ABC, implementations
  
  repositories/
    room_repository.py    # Room data access
    player_repository.py  # Player data access
  
  config/
    game_config.py      # GameConfigs
    constants.py        # Magic numbers
  
  rendering/
    cli_renderer.py     # CLI map drawing
  
  utils/
    helpers.py          # Helper functions
  
  llm/
    llm_module.py       # LLM integration
    prompts.py          # Prompt templates
```

**Priority**: HIGH
**Estimated Effort**: Large (6-8 hours)

---

### 🟡 IMPORTANT: Magic Numbers
**Problem**: Hardcoded values scattered throughout
- `MAX_ROOM_PATHS = 2`
- `20` words for descriptions
- Cell dimensions `5, 9` for CLI rendering

**Solution**: Centralize constants
```python
class GameConstants:
    # World generation
    MAX_ROOM_PATHS = 2
    STARTING_ROOM_COORDS = (0, 0)
    
    # Player
    DEFAULT_DESCRIPTION_WORDS = 20
    MAX_MEMORY_EVENTS = 100
    
    # Rendering
    CLI_CELL_HEIGHT = 5
    CLI_CELL_WIDTH = 9
    
    # Performance
    MAX_ROOM_EVENTS = 50
    MAX_PLAYER_INTERACTIONS = 100

class LLMConstants:
    DEFAULT_TEMPERATURE = 0.7
    MAX_TOKENS = 150
    RETRY_ATTEMPTS = 5
```

**Priority**: MEDIUM
**Estimated Effort**: Small (1-2 hours)

---

## 8. LLM Integration Issues

### 🟡 IMPORTANT: No Prompt Templates
**Problem**: String concatenation everywhere
```python
prompt = f"Provide a 20-word brief description of your character named {self.name}."
```

**Solution**: Use template system
```python
from string import Template

class PromptTemplates:
    CHARACTER_DESCRIPTION = Template("""
    Provide a ${word_count}-word brief description of your character.
    Name: ${name}
    Context: ${context}
    Style: ${style}
    """)
    
    ROOM_DESCRIPTION = Template("""
    Provide a ${word_count}-word description for the room:
    Name: ${room_name}
    Paths: ${path_descriptions}
    
    If a path has a room_id, there is already a room there.
    If a path has 'unknown', it is open to be explored.
    """)
    
    UPDATE_PLAYER_MEMORY = Template("""
    Update your mental description of ${player_name} based on this interaction.
    
    Current Description: 
    ${current_description}
    
    Recent Interaction:
    ${interaction_content}
    
    Provide only the updated description, no preamble.
    """)

# Usage:
prompt = PromptTemplates.CHARACTER_DESCRIPTION.substitute(
    word_count=20,
    name=self.name,
    context="exploring a dungeon",
    style="adventurous"
)
```

**Priority**: MEDIUM
**Estimated Effort**: Small (2-3 hours)

---

### 🟡 IMPORTANT: No LLM Response Validation
**Problem**: Assumes LLM always returns valid text

**Solution**: Add validation
```python
class LLMModule:
    def get_validated_response(
        self, 
        prompt: str, 
        max_words: int = None,
        min_words: int = 1
    ) -> str:
        response = self.get_response(prompt)
        
        if not response or len(response.strip()) == 0:
            raise ValueError("Empty LLM response")
        
        words = response.split()
        
        if min_words and len(words) < min_words:
            raise ValueError(f"Response too short: {len(words)} words (min: {min_words})")
        
        if max_words and len(words) > max_words:
            response = ' '.join(words[:max_words])
        
        return response.strip()
    
    def get_response_with_fallback(
        self, 
        prompt: str, 
        fallback: str = "Unable to generate response"
    ) -> str:
        try:
            return self.get_validated_response(prompt)
        except Exception as e:
            print(f"LLM error: {e}, using fallback")
            return fallback
```

**Priority**: MEDIUM
**Estimated Effort**: Small (2 hours)

---

## 9. Testing Concerns

### 🔴 CRITICAL: Untestable Code
**Problem**:
- Direct `input()` calls in player methods
- LLM calls in constructors
- Tight coupling to external dependencies

**Solution**: Dependency injection
```python
# Abstract interfaces
class InputProvider(ABC):
    @abstractmethod
    def get_input(self, prompt: str) -> str:
        pass

class ConsoleInput(InputProvider):
    def get_input(self, prompt: str) -> str:
        return input(prompt)

class MockInput(InputProvider):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
    
    def get_input(self, prompt: str) -> str:
        response = self.responses[self.index]
        self.index += 1
        return response

# Player class
class Player:
    def __init__(
        self, 
        name: str,
        room_id: str,
        controller: PlayerController,
        llm_client: LLMModule | None = None,
        input_provider: InputProvider | None = None
    ):
        self.name = name
        self.room_id = room_id
        self.controller = controller
        self.llm_client = llm_client or create_llm_module()
        self.input_provider = input_provider or ConsoleInput()

# Testing
def test_player_movement():
    mock_input = MockInput(["N", "E", "S"])
    player = Player(
        "Test", 
        "room1", 
        HumanController(mock_input),
        llm_client=MockLLM()
    )
    # Now testable!
```

**Priority**: HIGH
**Estimated Effort**: Large (10-12 hours)

---

### 🟡 IMPORTANT: Add Unit Tests
**Solution**: Set up testing framework
```python
# tests/test_player.py
import pytest
from src.models.player import Player, PlayerType
from src.controllers.player_controller import MockController

def test_player_creation():
    controller = MockController()
    player = Player("Alice", "room1", controller)
    assert player.name == "Alice"
    assert player.room_id == "room1"

def test_player_move():
    controller = MockController()
    player = Player("Bob", "room1", controller)
    player.move("room1", "N", "room2")
    assert player.room_id == "room2"
    assert len(player.history) == 1

# tests/test_game.py
def test_room_creation():
    game = Game()
    room = game._create_room((0, 0))
    assert room.coords == (0, 0)
    assert room.id in game._rooms

# Run with: pytest tests/
```

**Priority**: MEDIUM
**Estimated Effort**: Large (ongoing effort)

---

## 10. Additional Improvements

### 🟢 NICE TO HAVE: Add Logging
**Solution**: Replace print statements
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class Game:
    def __init__(self):
        logger.info("Initializing game...")
        # ...
    
    def _create_room(self, coords):
        logger.debug(f"Creating room at {coords}")
        # ...
        logger.info(f"Room created: {room.name} at {room.coords}")
```

**Priority**: LOW
**Estimated Effort**: Small (2-3 hours)

---

### 🟢 NICE TO HAVE: Add Configuration Validation
**Solution**: Validate config at startup
```python
from pydantic import BaseModel, Field, validator

class GameConfig(BaseModel):
    max_room_paths: int = Field(ge=2, le=4)  # Must be 2-4
    starting_coords: tuple[int, int] = (0, 0)
    n_npcs: int = Field(ge=0, le=100)
    
    @validator('max_room_paths')
    def validate_paths(cls, v):
        if v not in [2, 3, 4]:
            raise ValueError('max_room_paths must be 2, 3, or 4')
        return v

# Load and validate
config = GameConfig(
    max_room_paths=MAX_ROOM_PATHS,
    n_npcs=N_NPCS
)
```

**Priority**: LOW
**Estimated Effort**: Small (2 hours)

---

### 🟢 NICE TO HAVE: Add Documentation
**Solution**: Add docstrings
```python
class Game:
    """
    Main game orchestrator managing the dungeon exploration game.
    
    This class coordinates between the world generation, player management,
    turn system, and event handling components.
    
    Attributes:
        _rooms: Dictionary mapping room IDs to Room instances
        _map: Dictionary mapping coordinates to room IDs
        _players: Dictionary mapping player IDs to Player instances
        _player_locations: Dictionary mapping player IDs to room IDs
    
    Example:
        >>> game = Game()
        >>> game.create_world()
        >>> game.create_player("Alice", PlayerType.HUMAN)
        >>> game.run()
    """
    
    def _create_room(
        self, 
        coords: tuple[int, int],
        from_room: Room | None = None,
        from_direction: str | None = None
    ) -> Room:
        """
        Creates a new room at the specified coordinates.
        
        Args:
            coords: The (x, y) coordinates for the new room
            from_room: The room from which this room is being created
            from_direction: The direction of from_room relative to the new room
        
        Returns:
            The newly created Room instance
        
        Raises:
            ValueError: If a room already exists at the coordinates
        """
        pass
```

**Priority**: LOW
**Estimated Effort**: Large (ongoing)

---

## Priority Summary

### Phase 1: Critical Fixes (Weeks 1-2)
1. Fix defaultdict usage → regular dicts with validation
2. Add type hints throughout
3. Use enums for string constants
4. Add error handling and validation
5. Extract PlayerController strategy pattern

### Phase 2: Architectural Improvements (Weeks 3-4)
6. Split Game class into managers
7. Reorganize file structure into packages
8. Separate queries from commands (CQRS)
9. Implement repository pattern

### Phase 3: Quality Improvements (Week 5)
10. Add prompt templates for LLM
11. Fix performance issues
12. Add dependency injection for testing
13. Centralize magic numbers

### Phase 4: Polish (Week 6+)
14. Add unit tests
15. Add logging
16. Add persistence layer
17. Add documentation

---

## Estimated Total Effort
- **Phase 1**: 20-25 hours
- **Phase 2**: 25-30 hours  
- **Phase 3**: 15-20 hours
- **Phase 4**: 20-30 hours
- **Total**: 80-105 hours (10-13 working days)

## Recommended Approach
1. Start with Phase 1 fixes (high impact, lower effort)
2. Get code working well with new patterns
3. Move to Phase 2 (larger refactoring)
4. Add Phase 3 quality improvements
5. Phase 4 is ongoing maintenance

---

## References
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Design Patterns: Gang of Four](https://en.wikipedia.org/wiki/Design_Patterns)
- [Clean Code by Robert Martin](https://www.oreilly.com/library/view/clean-code-a/9780136083238/)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)

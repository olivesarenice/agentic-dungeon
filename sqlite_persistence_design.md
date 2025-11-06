# SQLite Persistence Layer - Architectural Design

This document outlines how implementing SQLite persistence will dramatically change the architecture of the Agentic Dungeon project.

---

## Executive Summary

**Impact Level**: 🔴 **MAJOR ARCHITECTURAL CHANGE**

Adding SQLite persistence is not just about saving data—it fundamentally changes how the entire application is structured. This will affect:
- Data access patterns (Repository pattern becomes **mandatory**)
- Object lifecycle management
- Memory management strategies
- Initialization and loading procedures
- Transaction handling
- Performance considerations

**Estimated Effort**: 30-40 hours (additional to the v2_todo.md improvements)

**Recommendation**: Implement this **after** Phase 1-2 of v2_todo.md (after extracting repositories and splitting Game class)

---

## Why SQLAlchemy ORM?

This document uses **SQLAlchemy ORM** throughout because it's the ideal choice for this project:

### Key Benefits

1. **Well-Defined Domain Models** - Your Player, Room, GameEvent objects map cleanly to database tables
2. **Complex Relationships** - ORMs handle one-to-many and many-to-many relationships elegantly
3. **Type Safety** - Catches errors at Python level before hitting the database
4. **Less Boilerplate** - Dramatically reduces code compared to manual SQL
5. **Built-in Transaction Management** - Cleaner error handling and rollbacks
6. **Alembic Migrations** - Automatic schema migration generation
7. **Industry Standard** - Well-tested, well-documented, large community

### Installation

```bash
pip install sqlalchemy alembic
```

---

## 1. Database Schema Design

### Proposed Schema

```sql
-- Worlds table: Each game session/save
CREATE TABLE worlds (
    id TEXT PRIMARY KEY,                    -- UUID
    name TEXT NOT NULL,                     -- "My Adventure"
    created_at TIMESTAMP NOT NULL,
    last_played_at TIMESTAMP NOT NULL,
    starting_coords_x INTEGER NOT NULL,
    starting_coords_y INTEGER NOT NULL,
    settings_json TEXT                      -- JSON blob for game settings
);

-- Rooms table
CREATE TABLE rooms (
    id TEXT PRIMARY KEY,                    -- slug-id from name
    world_id TEXT NOT NULL,
    name TEXT NOT NULL,
    coords_x INTEGER NOT NULL,
    coords_y INTEGER NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE CASCADE,
    UNIQUE(world_id, coords_x, coords_y)    -- One room per coordinate per world
);

-- Room paths/connections
CREATE TABLE room_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id TEXT NOT NULL,
    direction TEXT NOT NULL,                -- 'N', 'S', 'E', 'W'
    connected_room_id TEXT,                 -- NULL if unexplored path
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (connected_room_id) REFERENCES rooms(id) ON DELETE SET NULL,
    UNIQUE(room_id, direction)              -- Each direction only once per room
);

-- Players table
CREATE TABLE players (
    id TEXT PRIMARY KEY,                    -- UUID
    world_id TEXT NOT NULL,
    name TEXT NOT NULL,
    current_room_id TEXT NOT NULL,
    is_npc BOOLEAN NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE CASCADE,
    FOREIGN KEY (current_room_id) REFERENCES rooms(id),
    UNIQUE(world_id, name)                  -- Unique names per world
);

-- Player history (movement log)
CREATE TABLE player_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    from_room_id TEXT NOT NULL,
    action TEXT NOT NULL,                   -- Direction or action taken
    to_room_id TEXT,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (from_room_id) REFERENCES rooms(id),
    FOREIGN KEY (to_room_id) REFERENCES rooms(id)
);

-- Game events (for witnessing system)
CREATE TABLE game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    action_type TEXT NOT NULL,              -- 'TALK', 'INTERACT', 'MOVE_IN', 'MOVE_OUT'
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (actor_id) REFERENCES players(id),
    INDEX idx_events_room (room_id, timestamp),
    INDEX idx_events_actor (actor_id, timestamp)
);

-- Event witnesses (many-to-many relationship)
CREATE TABLE event_witnesses (
    event_id INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    FOREIGN KEY (event_id) REFERENCES game_events(id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, player_id)
);

-- Player memory about other players
CREATE TABLE player_known_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    observer_id TEXT NOT NULL,              -- The player doing the remembering
    known_player_name TEXT NOT NULL,        -- Name of player being remembered
    description TEXT NOT NULL,              -- LLM-generated description
    last_seen_room_id TEXT NOT NULL,
    last_updated TIMESTAMP NOT NULL,
    FOREIGN KEY (observer_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (last_seen_room_id) REFERENCES rooms(id),
    UNIQUE(observer_id, known_player_name)
);

-- Player memory about rooms
CREATE TABLE player_known_rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id TEXT NOT NULL,
    room_id TEXT NOT NULL,
    description TEXT NOT NULL,              -- Player's memory of the room
    last_updated TIMESTAMP NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    UNIQUE(player_id, room_id)
);
```

### Key Design Decisions

1. **World-scoped data**: All game data is scoped to a `world_id`, allowing multiple save games
2. **Normalized structure**: Proper foreign keys and constraints maintain referential integrity
3. **Indexes**: Added for common query patterns (events by room, events by actor)
4. **Cascading deletes**: When a world is deleted, all related data is cleaned up
5. **Timestamps**: Track creation and updates for all entities

---

## 2. How This Changes the Architecture

### 2.1 Current Architecture (In-Memory)

```python
# Current: Everything in memory, dictionaries
class Game:
    def __init__(self):
        self._rooms = defaultdict(Room)      # All rooms in memory
        self._players = defaultdict(Player)   # All players in memory
        self._map = defaultdict(str)         # All mappings in memory
```

**Problems**:
- Lost on exit
- No multi-session support
- Expensive LLM calls repeated every time
- No concurrency (single process only)

### 2.2 New Architecture (Database-Backed)

```python
# New: Repository pattern with lazy loading
class Game:
    def __init__(self, world_id: str, db_connection: DatabaseConnection):
        self.world_id = world_id
        self.db = db_connection
        
        # Repositories handle all data access
        self.room_repo = RoomRepository(db_connection, world_id)
        self.player_repo = PlayerRepository(db_connection, world_id)
        self.event_repo = EventRepository(db_connection, world_id)
        
        # Caches (optional, for performance)
        self._room_cache: dict[str, Room] = {}
        self._player_cache: dict[str, Player] = {}
```

**Benefits**:
- Persistent across sessions
- Multi-world support
- LLM results cached forever
- Potential for multi-process/multiplayer
- Can query historical data

---

## 3. Major Architectural Changes Required

### 3.1 Repository Pattern (NOW MANDATORY)

**Before** (Direct Access):
```python
def _room_from_id(self, room_id: str) -> Room:
    return self._rooms.get(room_id)
```

**After** (SQLAlchemy Repository):
```python
from sqlalchemy.orm import Session, joinedload

class RoomRepository:
    def __init__(self, session: Session, world_id: str):
        self.session = session
        self.world_id = world_id
    
    def get(self, room_id: str) -> Room | None:
        """Get room from DB, with relationships loaded"""
        return self.session.query(Room).options(
            joinedload(Room.paths),  # Eagerly load paths
            joinedload(Room.players)  # Eagerly load players
        ).filter_by(
            id=room_id,
            world_id=self.world_id
        ).first()
    
    def get_by_coords(self, x: int, y: int) -> Room | None:
        """Find room at specific coordinates"""
        return self.session.query(Room).filter_by(
            world_id=self.world_id,
            coords_x=x,
            coords_y=y
        ).first()
    
    def save(self, room: Room) -> None:
        """Save or update room"""
        self.session.add(room)
        self.session.commit()
    
    def get_all(self) -> list[Room]:
        """Get all rooms in this world"""
        return self.session.query(Room).filter_by(
            world_id=self.world_id
        ).all()
```

### 3.2 Lazy Loading vs Eager Loading

**Critical Decision**: Do we load everything on startup or load on-demand?

**Option A: Eager Loading** (Load all at startup)
```python
from sqlalchemy.orm import Session

class Game:
    def __init__(self, world_id: str, session: Session):
        self.session = session
        self.world_id = world_id
        
        # Load EVERYTHING into memory at startup
        self.rooms = self.room_repo.get_all()  # Could be thousands
        self.players = self.player_repo.get_all()
        
        # Keep in memory for fast access
        self._room_dict = {r.id: r for r in self.rooms}
```

**Pros**: Fast access once loaded, simple code
**Cons**: Slow startup, high memory usage, doesn't scale

**Option B: Lazy Loading with SQLAlchemy** ⭐ **RECOMMENDED**
```python
from sqlalchemy.orm import Session

class Game:
    def __init__(self, world_id: str, session: Session):
        self.session = session
        self.world_id = world_id
        
        # Repositories handle lazy loading automatically
        self.room_repo = RoomRepository(session, world_id)
        self.player_repo = PlayerRepository(session, world_id)
        
        # Optional: Light cache for frequently accessed items
        self._room_cache: dict[str, Room] = {}
    
    def get_room(self, room_id: str) -> Room | None:
        # Check cache first
        if room_id not in self._room_cache:
            # Load from DB via repository
            self._room_cache[room_id] = self.room_repo.get(room_id)
        return self._room_cache[room_id]
```

**Pros**: Fast startup, low memory, scales to huge worlds
**Cons**: Need cache management, slightly more complex

**Option C: Hybrid Approach** (Best of both)
```python
class Game:
    def __init__(self, world_id: str, session: Session):
        self.session = session
        self.world_id = world_id
        
        # Eager load small, frequently accessed data
        self.active_players = self.player_repo.get_all()  # Usually < 10 players
        
        # Lazy load rooms (can be thousands)
        self._room_cache = {}
```

**Pros**: Optimal for your use case
**Cons**: Need to identify what to eager vs lazy load

---

## 4. Initialization Flow Changes

### 4.1 Current Flow

```python
def main():
    game = Game()           # Empty game
    game.create_world()     # Create starting room
    game.create_player()    # Create players (expensive LLM calls)
    game.run()              # Start game loop
```

### 4.2 New Flow (with persistence)

```python
def main():
    # 1. Connect to database
    db = DatabaseConnection("game.db")
    db.initialize_schema()  # Create tables if not exist
    
    # 2. World selection
    worlds = WorldRepository(db).get_all()
    
    if not worlds:
        # New game
        world = create_new_world(db)
    else:
        # Load existing world
        print("Existing worlds:")
        for w in worlds:
            print(f"{w.id}: {w.name} (last played: {w.last_played_at})")
        
        choice = input("Enter world ID or 'new': ")
        if choice == 'new':
            world = create_new_world(db)
        else:
            world = WorldRepository(db).get(choice)
    
    # 3. Initialize game with existing world
    game = Game(world.id, db)
    
    # 4. Load or create starting room
    if not game.room_repo.has_rooms():
        starting_room = Room.create_new(world.id, (0, 0), game.llm_module)
        game.room_repo.save(starting_room)
    
    # 5. Load or create players
    existing_players = game.player_repo.get_all()
    if not existing_players:
        # Create new players (expensive, but only once!)
        player = Player.create_new(world.id, "OLIVER", starting_room.id, False, game.llm_module)
        game.player_repo.save(player)
    else:
        print(f"Loaded {len(existing_players)} existing players")
    
    # 6. Run game
    game.run()
```

---

## 5. Benefits vs Costs

### Benefits ✅
1. **Persistence**: Game state saved automatically
2. **Multi-world**: Players can have multiple save games
3. **LLM Caching**: Expensive LLM calls made once, cached forever
4. **Historical Data**: Can query past events, analyze patterns
5. **Scalability**: Can handle large worlds (thousands of rooms)
6. **Debugging**: Can inspect game state directly in DB
7. **Analytics**: Can analyze player behavior

### Costs ❌
1. **Complexity**: Much more complex code
2. **Performance**: DB queries slower than in-memory (but cacheable)
3. **Testing**: Harder to test (need DB fixtures)
4. **Development Time**: 30-40 hours additional work
5. **Learning Curve**: Need to understand SQL/ORM, transactions, repositories

---

## 6. Recommendations

### ⭐ Primary Recommendation: SQLAlchemy ORM

**Use SQLAlchemy** for your implementation because:

1. **Perfect use case** - complex relationships, well-defined models
2. **Saves time** - less boilerplate, automatic relationships
3. **Better maintainability** - easier schema changes
4. **Type safety** - catches errors earlier
5. **Industry standard** - well-documented, large community

**Dependencies to add**:
```bash
pip install sqlalchemy alembic
```

### Implementation Order

1. **First**: Complete Phase 1-2 of v2_todo.md
   - Extract repositories (empty implementations)
   - Split Game class
   - Add type hints

2. **Then**: Add SQLAlchemy persistence
   - Define SQLAlchemy models
   - Implement repository methods
   - Add initialization flow
   - Add caching

3. **Finally**: Optimize
   - Add eager loading where needed
   - Profile queries
   - Optimize caching

### MVP Approach

**If you want to see results quickly:**

1. Start with **just rooms and players**
2. Skip complex features (memory, events) initially
3. Get basic save/load working
4. Add remaining features incrementally

This gets you 80% of the benefit with 20% of the complexity.

---

## 7. Complete SQLAlchemy Example

Here's a complete working example with SQLAlchemy:

```python
# database/base.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

def init_database(db_path: str = "game.db"):
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

# models/world.py
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class World(Base):
    __tablename__ = 'worlds'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    last_played_at = Column(DateTime, nullable=False, default=datetime.now)
    starting_coords_x = Column(Integer, nullable=False, default=0)
    starting_coords_y = Column(Integer, nullable=False, default=0)
    
    # Relationships
    rooms = relationship("Room", back_populates="world", cascade="all, delete-orphan")
    players = relationship("Player", back_populates="world", cascade="all, delete-orphan")
    events = relationship("GameEvent", back_populates="world", cascade="all, delete-orphan")

# models/room.py
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database.base import Base

class Room(Base):
    __tablename__ = 'rooms'
    
    id = Column(String, primary_key=True)
    world_id = Column(String, ForeignKey('worlds.id'), nullable=False)
    name = Column(String, nullable=False)
    coords_x = Column(Integer, nullable=False)
    coords_y = Column(Integer, nullable=False)
    description = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    
    # Relationships
    world = relationship("World", back_populates="rooms")
    players = relationship("Player", back_populates="current_room")
    paths = relationship("RoomPath", back_populates="from_room", cascade="all, delete-orphan")

# repositories/room_repository.py
from sqlalchemy.orm import Session
from models.room import Room

class RoomRepository:
    def __init__(self, session: Session, world_id: str):
        self.session = session
        self.world_id = world_id
    
    def get(self, room_id: str) -> Room | None:
        return self.session.query(Room).filter_by(
            id=room_id,
            world_id=self.world_id
        ).first()
    
    def get_by_coords(self, x: int, y: int) -> Room | None:
        return self.session.query(Room).filter_by(
            world_id=self.world_id,
            coords_x=x,
            coords_y=y
        ).first()
    
    def save(self, room: Room) -> None:
        self.session.add(room)
        self.session.commit()

# Usage:
session = init_database("game.db")
room_repo = RoomRepository(session, world_id)

# Get room
room = room_repo.get_by_coords(0, 0)
if room:
    print(f"Found room: {room.name}")
    print(f"Players in room: {[p.name for p in room.players]}")
```

---

## Summary

**Use SQLAlchemy ORM** for your SQLite persistence layer as demonstrated throughout this document. SQLAlchemy is the right choice because:

- ✅ Perfect fit for your complex domain model (Player, Room, GameEvent relationships)
- ✅ Dramatically reduces boilerplate code compared to manual SQL
- ✅ Handles relationships automatically with eager/lazy loading
- ✅ Provides type safety and validation at the Python level
- ✅ Easier to maintain and evolve as requirements change
- ✅ Built-in transaction management and rollback support
- ✅ Alembic migrations for seamless schema evolution

### Next Steps

1. Complete Phase 1-2 of v2_todo.md first (repository pattern, split Game class)
2. Install dependencies: `pip install sqlalchemy alembic`
3. Start with MVP: rooms and players tables only
4. Define SQLAlchemy models as shown in Section 7
5. Implement repositories with proper eager loading
6. Add remaining tables incrementally
7. Set up Alembic for future migrations

The architectural changes are significant but the long-term benefits—persistent game state, LLM caching, multi-world support, and scalability—make this investment worthwhile.

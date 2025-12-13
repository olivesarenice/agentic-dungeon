"""
FastAPI REST API backend for Agentic Dungeon.
Provides simple request/response endpoints for game actions.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path to import from src/
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.enums import PlayerType
from database.base import Base
from services.game_manager import GameManager

# Initialize FastAPI app
app = FastAPI(
    title="Agentic Dungeon API",
    description="REST API for text-based dungeon crawler with autonomous NPCs",
    version="0.1.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup - V3 uses new database
DATABASE_URL = "sqlite:///./game_v3.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all database tables if they don't exist
print("Initializing V3 database...")
Base.metadata.create_all(engine)
print("✅ V3 Database initialized successfully")

# Store game managers per world
game_managers: dict[str, GameManager] = {}

# Create a single narration service instance to track recent narrations
from services.narration_service import NarrationService

narration_service = NarrationService()


def get_or_create_game_manager(world_id: str) -> GameManager:
    """Get existing or create new GameManager for a world."""
    if world_id not in game_managers:
        session = SessionLocal()
        game_managers[world_id] = GameManager(session, world_id)
    return game_managers[world_id]


# Request/Response models
class ActionRequest(BaseModel):
    """Request model for player actions."""

    player_id: str
    action: str  # MOVE, TALK, INTERACT, OBSERVE
    direction: Optional[str] = None  # N, S, E, W for MOVE
    message: Optional[str] = None  # For TALK
    description: Optional[str] = None  # For INTERACT


class CreatePlayerRequest(BaseModel):
    """Request model for creating a player."""

    world_id: str
    player_name: str
    player_type: str = "HUMAN"  # HUMAN or NPC


class CreateWorldRequest(BaseModel):
    """Request model for creating a new world."""

    name: str
    theme: Optional[str] = None
    art_style: str = "retro_anime"
    grid_size: int = 3  # V3: 3, 5, or 7
    npc_count: int = 3


# ============================================================================
# Root and Health Check
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint - serve start page."""
    return FileResponse("static/start.html")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "agentic-dungeon"}


# ============================================================================
# World Management
# ============================================================================


@app.get("/api/worlds")
async def list_worlds():
    """List all available game worlds."""
    session = SessionLocal()
    try:
        from database.models import DBWorld

        worlds = session.query(DBWorld).all()
        return {
            "worlds": [
                {
                    "id": world.id,
                    "name": world.name,
                    "theme": world.theme,
                    "art_style": world.art_style,
                    "created_at": world.created_at.isoformat(),
                    "last_played_at": world.last_played_at.isoformat(),
                }
                for world in worlds
            ]
        }
    finally:
        session.close()


@app.get("/api/worlds/{world_id}")
async def get_world(world_id: str):
    """Get details about a specific world."""
    session = SessionLocal()
    try:
        from database.models import DBWorld

        world = session.query(DBWorld).filter(DBWorld.id == world_id).first()
        if not world:
            raise HTTPException(status_code=404, detail="World not found")

        return {
            "id": world.id,
            "name": world.name,
            "theme": world.theme,
            "art_style": world.art_style,
            "created_at": world.created_at.isoformat(),
            "last_played_at": world.last_played_at.isoformat(),
            "starting_coords": {
                "x": world.starting_coords_x,
                "y": world.starting_coords_y,
            },
        }
    finally:
        session.close()


@app.get("/api/worlds/{world_id}/players")
async def get_world_players(world_id: str):
    """Get all players in a specific world."""
    session = SessionLocal()
    try:
        from database.models import DBPlayer

        players = session.query(DBPlayer).filter(DBPlayer.world_id == world_id).all()

        return {
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "description": player.description,
                    "player_type": player.player_type,
                    "current_room_id": player.current_room_id,
                    "created_at": player.created_at.isoformat(),
                }
                for player in players
            ]
        }
    finally:
        session.close()


@app.post("/api/worlds")
async def create_world(request: CreateWorldRequest):
    """Create a new world with rooms and NPCs."""
    import uuid

    from faker import Faker

    fake = Faker()
    session = SessionLocal()

    try:
        from database.models import DBWorld
        from repositories import WorldRepository

        # V3: Calculate center coordinates for grid
        center = request.grid_size // 2

        # Create world in database
        world_id = str(uuid.uuid4())
        db_world = DBWorld(
            id=world_id,
            name=request.name,
            theme=request.theme,
            art_style=request.art_style,
            grid_size=request.grid_size,  # V3
            created_at=datetime.now(),
            last_played_at=datetime.now(),
            starting_coords_x=center,  # V3: Start at grid center
            starting_coords_y=center,
        )

        world_repo = WorldRepository(session)
        world_repo.add(db_world)

        # IMPORTANT: Commit the world to database BEFORE creating GameManager
        # Otherwise the GameManager's session won't see the theme
        session.commit()

        print(f"\n{'='*60}")
        print(f"Creating V3 World: {request.name}")
        print(f"  ID: {world_id}")
        print(
            f"  Grid Size: {request.grid_size}x{request.grid_size} ({request.grid_size * request.grid_size} rooms)"
        )
        if request.theme:
            print(f"  Theme: {request.theme}")
        print(f"  Art Style: {request.art_style}")
        print(f"  NPCs: {request.npc_count}")
        print(f"{'='*60}\n")

        # Initialize game manager and create organic labyrinth
        game_manager = get_or_create_game_manager(world_id)

        # Calculate max_rooms from grid_size (for backwards compatibility)
        # grid_size 2 = 4 rooms, 3 = 9 rooms, 4 = 16 rooms
        max_rooms = request.grid_size * request.grid_size

        game_manager.world_generator.create_organic_labyrinth(max_rooms)

        # V3: Place treasures (same number as grid_size for consistency)
        game_manager.world_generator.place_treasures(request.grid_size, session)

        # Update world with treasure count
        db_world.total_treasures = request.grid_size
        session.commit()

        # Create NPCs
        if request.npc_count > 0:
            print(f"👥 Spawning {request.npc_count} NPCs...")
            for i in range(request.npc_count):
                npc_name = fake.user_name() + "_" + str(fake.random_number(digits=3))
                game_manager.create_player(npc_name, PlayerType.NPC)
                print(f"   ✓ {npc_name}")
            print()

        print(f"{'='*60}")
        print(f"✅ World '{request.name}' ready to explore!")
        print(f"{'='*60}\n")

        return {
            "id": world_id,
            "name": request.name,
            "theme": request.theme,
            "art_style": request.art_style,
            "grid_size": request.grid_size,
            "total_treasures": request.grid_size,
            "created_at": db_world.created_at.isoformat(),
            "npc_count": request.npc_count,
        }

    except Exception as e:
        session.rollback()
        print(f"Error creating world: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create world: {str(e)}")
    finally:
        session.close()


# ============================================================================
# Player Management
# ============================================================================


@app.post("/api/players")
async def create_player(request: CreatePlayerRequest):
    """Create a new player in a world."""
    game_manager = get_or_create_game_manager(request.world_id)

    try:
        player_type = PlayerType[request.player_type.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail="Invalid player type")

    player = game_manager.create_player(request.player_name, player_type)

    if not player:
        raise HTTPException(
            status_code=400, detail=f"Player {request.player_name} already exists"
        )

    return {
        "id": player.id,
        "name": player.name,
        "description": player.description,
        "player_type": player.player_type.value,
        "current_room_id": player.room_id,
    }


@app.get("/api/players/{player_id}")
async def get_player(player_id: str):
    """Get player information."""
    session = SessionLocal()
    try:
        from database.models import DBPlayer

        player = session.query(DBPlayer).filter(DBPlayer.id == player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

        return {
            "id": player.id,
            "name": player.name,
            "description": player.description,
            "player_type": player.player_type,
            "current_room_id": player.current_room_id,
            "created_at": player.created_at.isoformat(),
        }
    finally:
        session.close()


# ============================================================================
# Game State
# ============================================================================


@app.get("/api/state/{player_id}")
async def get_game_state(player_id: str):
    """
    Get complete game state for a player.
    Returns current room, known rooms, NPCs present, and recent events.
    """
    session = SessionLocal()
    try:
        from database.models import DBGameEvent, DBPlayer, DBRoom

        # Get player
        db_player = session.query(DBPlayer).filter(DBPlayer.id == player_id).first()
        if not db_player:
            raise HTTPException(status_code=404, detail="Player not found")

        # Get current room
        current_room = (
            session.query(DBRoom).filter(DBRoom.id == db_player.current_room_id).first()
        )
        if not current_room:
            raise HTTPException(status_code=404, detail="Current room not found")

        # Get image URL for current room
        current_room_image_url = None
        if current_room.image_filepath:
            filename = Path(current_room.image_filepath).name
            current_room_image_url = f"/images/{filename}"

        # Get other players in same room
        players_in_room = (
            session.query(DBPlayer)
            .filter(
                DBPlayer.current_room_id == current_room.id,
                DBPlayer.id != player_id,
            )
            .all()
        )

        npcs_present = [
            {"name": p.name, "description": p.description} for p in players_in_room
        ]

        # Get recent events in this room (last 10 events)
        recent_events = (
            session.query(DBGameEvent)
            .filter(DBGameEvent.room_id == current_room.id)
            .order_by(DBGameEvent.timestamp.desc())
            .limit(10)
            .all()
        )

        events_list = [
            {
                "actor": event.actor_name,
                "action": event.action_type,
                "content": event.content,
                "timestamp": event.timestamp.isoformat(),
            }
            for event in reversed(recent_events)
        ]

        # Get known rooms (rooms player has visited)
        from database.models import DBPlayerKnownRoom, DBRoomPath

        known_rooms_query = (
            session.query(DBRoom)
            .join(DBPlayerKnownRoom, DBRoom.id == DBPlayerKnownRoom.room_id)
            .filter(DBPlayerKnownRoom.player_id == player_id)
            .all()
        )

        known_rooms = []
        for room in known_rooms_query:
            # Get paths for this room
            room_paths = (
                session.query(DBRoomPath).filter(DBRoomPath.room_id == room.id).all()
            )
            paths = [path.direction for path in room_paths]

            # Get image URL
            image_url = None
            if room.image_filepath:
                filename = Path(room.image_filepath).name
                image_url = f"/images/{filename}"

            room_data = {
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "image_url": image_url,
                "coords": {"x": room.coords_x, "y": room.coords_y},
                "paths": paths,
            }
            known_rooms.append(room_data)

        # Get available exits from current room
        from database.models import DBRoomPath

        paths = (
            session.query(DBRoomPath)
            .filter(DBRoomPath.room_id == current_room.id)
            .all()
        )

        # All paths are available, even if room doesn't exist yet (will be created on move)
        available_exits = [path.direction for path in paths]

        print(f"[STATE] Room {current_room.id} has paths: {available_exits}")

        # V3: Get treasure progress and inventory
        from database.models import DBItem, DBWorld

        world = session.query(DBWorld).filter_by(id=db_player.world_id).first()

        total_treasures = world.total_treasures if world else 0
        collected_treasures = (
            session.query(DBItem)
            .filter_by(
                world_id=db_player.world_id,
                item_type="TREASURE",
                is_collected=True,
                collected_by_player_id=player_id,
            )
            .count()
        )

        # Get player's inventory
        inventory_items = (
            session.query(DBItem)
            .filter_by(
                collected_by_player_id=player_id,
                is_collected=True,
            )
            .all()
        )

        inventory = [
            {
                "name": item.name,
                "description": item.description,
                "collected_at": (
                    item.collected_at.isoformat() if item.collected_at else None
                ),
            }
            for item in inventory_items
        ]

        has_won = (collected_treasures == total_treasures) and total_treasures > 0

        return {
            "player": {
                "id": db_player.id,
                "name": db_player.name,
                "description": db_player.description,
            },
            "current_room": {
                "id": current_room.id,
                "name": current_room.name,
                "description": current_room.description,
                "coords": {"x": current_room.coords_x, "y": current_room.coords_y},
                "image_url": current_room_image_url,
            },
            "npcs_present": npcs_present,
            "recent_events": events_list,
            "known_rooms": known_rooms,
            "available_exits": available_exits,
            "objective": {
                "total_treasures": total_treasures,
                "collected_treasures": collected_treasures,
                "has_won": has_won,
            },
            "inventory": inventory,
        }

    finally:
        session.close()


# ============================================================================
# Actions
# ============================================================================


@app.post("/api/action")
async def perform_action(request: ActionRequest):
    """
    Process a player action and return updated game state.
    """
    # Get player's world
    session = SessionLocal()
    try:
        from database.models import DBPlayer

        db_player = (
            session.query(DBPlayer).filter(DBPlayer.id == request.player_id).first()
        )
        if not db_player:
            raise HTTPException(status_code=404, detail="Player not found")

        world_id = db_player.world_id
    finally:
        session.close()

    # Get game manager
    game_manager = get_or_create_game_manager(world_id)

    # Process action based on type
    action_type = request.action.upper()

    if action_type == "MOVE":
        result = await handle_move_action(
            game_manager, request.player_id, request.direction
        )
    elif action_type == "INTERACT":
        result = await handle_interact_action(
            game_manager, request.player_id, request.description
        )
    elif action_type == "OBSERVE":
        result = await handle_observe_action(game_manager, request.player_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action_type}")

    # Return result along with updated game state
    state = await get_game_state(request.player_id)
    return {"success": result["success"], "message": result["message"], "state": state}


async def handle_move_action(
    game_manager: GameManager, player_id: str, direction: Optional[str]
):
    """Handle player movement."""
    if not direction:
        return {"success": False, "message": "Direction is required for MOVE action"}

    try:
        # Get player
        player = game_manager.get_player(player_id)
        if not player:
            return {"success": False, "message": "Player not found"}

        # Check if direction is valid
        current_room = game_manager.world_generator.get_room(player.room_id)
        if not current_room:
            return {"success": False, "message": "Current room not found"}

        # Check if this direction exists
        if direction not in current_room.paths:
            return {
                "success": False,
                "message": f"Cannot move {direction} - no path in that direction",
            }

        # Get all players for context
        players_map = game_manager.get_players()

        # Check if target room is already known BEFORE moving
        target_room_id = current_room.paths.get(direction)
        session_check = SessionLocal()
        try:
            from database.models import DBPlayerKnownRoom

            # Check if player has visited target room before
            was_previously_visited = (
                session_check.query(DBPlayerKnownRoom)
                .filter(
                    DBPlayerKnownRoom.player_id == player_id,
                    DBPlayerKnownRoom.room_id == target_room_id,
                )
                .count()
                > 0
            )
        finally:
            session_check.close()

        # Process the move
        print(f"[MOVE] Player {player.name} moving {direction}")
        success = game_manager.turn_system.process_player_move(
            player, direction, players_map
        )

        if success:
            # Ensure database commit happens immediately
            game_manager.session.commit()
            print(f"[MOVE] Successfully moved to room {player.room_id}")

            # Generate voiceover narration for the move (only if TTS enabled)
            from config.constants import TTSConstants

            if TTSConstants.ENABLED:
                try:
                    # Get rooms for context
                    to_room = game_manager.world_generator.get_room(player.room_id)

                    # For first visit, just use room description
                    # For returning, generate a short narration
                    if not was_previously_visited:
                        narration_text = to_room.description
                        print(f"[NARRATION] First visit - using room description")
                    else:
                        from_room = game_manager.world_generator.get_room(
                            current_room.id
                        )
                        narration_text = narration_service.generate_move_narration(
                            player, from_room, to_room, direction, False
                        )
                        print(f"[NARRATION] Returning - generated narration")

                    # Generate and save audio narration
                    session = SessionLocal()
                    await generate_and_save_narration(
                        player_id, player.room_id, narration_text, "MOVE", session
                    )
                    session.close()

                    print(f"[NARRATION] {narration_text}")
                except Exception as e:
                    print(f"[NARRATION] Failed: {e}")
                    import traceback

                    traceback.print_exc()

            return {
                "success": True,
                "message": f"Moved {direction}",
            }
        else:
            return {
                "success": False,
                "message": f"Cannot move {direction}",
            }

    except Exception as e:
        print(f"Error in handle_move_action: {e}")
        import traceback

        traceback.print_exc()
        return {"success": False, "message": f"Error: {str(e)}"}


async def handle_talk_action(
    game_manager: GameManager, player_id: str, message: Optional[str]
):
    """Handle player talking."""
    if not message:
        return {"success": False, "message": "Message is required for TALK action"}

    try:
        # Get player
        player = game_manager.get_player(player_id)
        if not player:
            return {"success": False, "message": "Player not found"}

        # Override the controller's action prompt with the user's message
        original_controller = player.controller

        # Create a temporary controller that returns the user's message
        class MessageController:
            def provide_action_details(self, action, room, players_map):
                return message

        player.controller = MessageController()

        # Get all players for context
        players_map = game_manager.get_players()

        # Process the action
        from config.enums import ActionType

        success = game_manager.turn_system.process_player_action(
            player, ActionType.TALK.value, players_map
        )

        # Restore original controller
        player.controller = original_controller

        if success:
            # Generate voiceover narration for the talk action (only if TTS enabled)
            from config.constants import TTSConstants

            if TTSConstants.ENABLED:
                try:

                    # Get current room
                    current_room = game_manager.world_generator.get_room(player.room_id)

                    # Get NPCs present
                    npcs_present = [
                        p.name
                        for pid, p in players_map.items()
                        if p.room_id == player.room_id and pid != player_id
                    ]

                    narration_text = narration_service.generate_action_narration(
                        player, current_room, "TALK", message, npcs_present
                    )

                    # Generate and save audio narration
                    session = SessionLocal()
                    await generate_and_save_narration(
                        player_id, player.room_id, narration_text, "ACTION", session
                    )
                    session.close()

                    print(f"[NARRATION] {narration_text}")
                except Exception as e:
                    print(f"[NARRATION] Failed: {e}")

            return {
                "success": True,
                "message": f"You said: {message}",
            }
        else:
            return {
                "success": False,
                "message": "Failed to talk",
            }

    except Exception as e:
        print(f"Error in handle_talk_action: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


async def handle_interact_action(
    game_manager: GameManager, player_id: str, description: Optional[str]
):
    """Handle player interaction - V3: checks for item collection first."""
    if not description:
        return {
            "success": False,
            "message": "Description is required for INTERACT action",
        }

    try:
        # Get player
        player = game_manager.get_player(player_id)
        if not player:
            return {"success": False, "message": "Player not found"}

        # Get current room
        current_room = game_manager.world_generator.get_room(player.room_id)

        # V3: CHECK FOR ITEM COLLECTION FIRST
        session = SessionLocal()
        collected_item = await check_and_collect_item(
            session, player_id, current_room.id, description
        )

        if collected_item:
            # Item found and collected!
            narration = f"You {description} and discover the {collected_item['name']}! ({collected_item['collected']}/{collected_item['total']} treasures found)"

            await generate_and_save_narration(
                player_id, current_room.id, narration, "ITEM_COLLECTED", session
            )

            # Check win condition
            if collected_item["has_won"]:
                from database.models import DBWorld

                world = (
                    session.query(DBWorld).filter_by(id=game_manager.world_id).first()
                )
                world.is_complete = True
                world.completed_at = datetime.now()
                session.commit()

                win_narration = "🎉 You've found all the treasures! The dungeon's secrets are now yours!"
                await generate_and_save_narration(
                    player_id, current_room.id, win_narration, "WIN", session
                )

            session.close()

            return {
                "success": True,
                "message": f"🎉 You found the {collected_item['name']}!",
                "item_collected": True,
                "item_name": collected_item["name"],
                "progress": f"{collected_item['collected']}/{collected_item['total']}",
                "has_won": collected_item["has_won"],
            }

        session.close()

        # NO ITEM - Continue with normal room interaction
        room_description_before = current_room.description

        # STEP 1: Narrate the ACTION itself (only if TTS enabled)
        from config.constants import TTSConstants

        if TTSConstants.ENABLED:
            try:
                players_map = game_manager.get_players()
                npcs_present = [
                    p.name
                    for pid, p in players_map.items()
                    if p.room_id == player.room_id and pid != player_id
                ]

                action_narration = narration_service.generate_action_narration(
                    player, current_room, "INTERACT", description, npcs_present
                )

                # Generate and save action narration
                session = SessionLocal()
                await generate_and_save_narration(
                    player_id, player.room_id, action_narration, "ACTION", session
                )
                session.close()

                print(f"[NARRATION] Action: {action_narration}")
            except Exception as e:
                print(f"[NARRATION] Failed to narrate action: {e}")

        # STEP 2: Execute the action
        # Override the controller's action prompt with the user's description
        original_controller = player.controller

        class InteractController:
            def provide_action_details(self, action, room, players_map):
                return description

        player.controller = InteractController()

        players_map = game_manager.get_players()
        from config.enums import ActionType

        success = game_manager.turn_system.process_player_action(
            player, ActionType.INTERACT.value, players_map
        )

        # Restore original controller
        player.controller = original_controller

        if success:
            # STEP 3: Check if room changed and narrate the RESULT (only if TTS enabled)
            if TTSConstants.ENABLED:
                try:
                    current_room = game_manager.world_generator.get_room(player.room_id)
                    room_description_after = current_room.description

                    # If room description changed, narrate the change
                    if room_description_before != room_description_after:
                        change_narration = (
                            f"The room shifts in response to your action."
                        )

                        session = SessionLocal()
                        await generate_and_save_narration(
                            player_id,
                            player.room_id,
                            change_narration,
                            "ROOM_CHANGE",
                            session,
                        )
                        session.close()

                        print(f"[NARRATION] Room change: {change_narration}")
                except Exception as e:
                    print(f"[NARRATION] Failed to narrate room change: {e}")

            return {
                "success": True,
                "message": f"You interact: {description}",
            }
        else:
            return {
                "success": False,
                "message": "Failed to interact",
            }

    except Exception as e:
        print(f"Error in handle_interact_action: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


async def handle_observe_action(game_manager: GameManager, player_id: str):
    """Handle player observation."""
    try:
        # Get player
        player = game_manager.get_player(player_id)
        if not player:
            return {"success": False, "message": "Player not found"}

        # Get current room
        current_room = game_manager.world_generator.get_room(player.room_id)
        if not current_room:
            return {"success": False, "message": "Current room not found"}

        # Get all players for context
        players_map = game_manager.get_players()

        # Re-observe the room
        player.observe(current_room, players_map)

        # Persist updated player state
        game_manager.player_repo.update(player)

        # Generate voiceover narration for the observe action (only if TTS enabled)
        from config.constants import TTSConstants

        if TTSConstants.ENABLED:
            try:

                # Get NPCs present
                npcs_present = [
                    p.name
                    for pid, p in players_map.items()
                    if p.room_id == player.room_id and pid != player_id
                ]

                narration_text = narration_service.generate_action_narration(
                    player,
                    current_room,
                    "OBSERVE",
                    "carefully observing surroundings",
                    npcs_present,
                )

                # Generate and save audio narration
                session = SessionLocal()
                await generate_and_save_narration(
                    player_id, player.room_id, narration_text, "ACTION", session
                )
                session.close()

                print(f"[NARRATION] {narration_text}")
            except Exception as e:
                print(f"[NARRATION] Failed: {e}")

        return {
            "success": True,
            "message": "You carefully observe your surroundings",
        }

    except Exception as e:
        print(f"Error in handle_observe_action: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}


# ============================================================================
# V3: Item Collection Helper
# ============================================================================


async def check_and_collect_item(
    session, player_id: str, room_id: str, interaction_text: str
) -> Optional[dict]:
    """
    V3: Check if interaction matches an item hint and collect it.

    Args:
        session: Database session
        player_id: Player ID
        room_id: Current room ID
        interaction_text: What player typed (e.g., "open the wooden chest")

    Returns:
        Dict with item info if collected, None otherwise
    """
    from database.models import DBItem, DBPlayer, DBWorld

    # Get uncollected items in this room
    items = (
        session.query(DBItem)
        .filter(DBItem.room_id == room_id, DBItem.is_collected == False)
        .all()
    )

    if not items:
        return None

    # Fuzzy match: check if interaction contains item hint
    interaction_lower = interaction_text.lower()

    for item in items:
        hint_lower = item.interaction_hint.lower()

        # Match if interaction contains the hint or vice versa
        # e.g., "open the wooden chest" matches hint "wooden chest"
        if hint_lower in interaction_lower or interaction_lower in hint_lower:
            # COLLECT THE ITEM!
            item.is_collected = True
            item.collected_by_player_id = player_id
            item.collected_at = datetime.now()
            session.commit()

            print(f"[ITEM] Player {player_id} collected '{item.name}'")

            # Get progress
            player = session.query(DBPlayer).filter_by(id=player_id).first()
            world = session.query(DBWorld).filter_by(id=player.world_id).first()

            total = world.total_treasures
            collected = (
                session.query(DBItem)
                .filter_by(
                    world_id=player.world_id,
                    item_type="TREASURE",
                    is_collected=True,
                )
                .count()
            )

            has_won = collected == total

            print(f"[ITEM] Progress: {collected}/{total} treasures")
            if has_won:
                print(f"[ITEM] 🎉 Player {player.name} has won!")

            return {
                "name": item.name,
                "description": item.description,
                "collected": collected,
                "total": total,
                "has_won": has_won,
            }

    return None


# ============================================================================
# Narration
# ============================================================================


@app.get("/api/narration/{player_id}/latest")
async def get_latest_narration(player_id: str):
    """
    Get recent narrations for a player (last 10 seconds).
    Returns all narrations created recently to support sequential playback.
    """
    session = SessionLocal()
    try:
        from datetime import timedelta

        from database.models import DBNarration

        # Get narrations from last 10 seconds
        recent_time = datetime.now() - timedelta(seconds=10)
        narrations = (
            session.query(DBNarration)
            .filter(
                DBNarration.player_id == player_id,
                DBNarration.created_at >= recent_time,
            )
            .order_by(
                DBNarration.created_at.asc()
            )  # Oldest first for sequential playback
            .all()
        )

        if not narrations:
            return {"narrations": []}

        narration_list = []
        for narration in narrations:
            audio_url = None
            if narration.audio_filepath:
                filename = Path(narration.audio_filepath).name
                audio_url = f"/narrations/{filename}"

            narration_list.append(
                {
                    "id": narration.id,
                    "text": narration.narration_text,
                    "type": narration.narration_type,
                    "audio_url": audio_url,
                    "created_at": narration.created_at.isoformat(),
                }
            )

        return {"narrations": narration_list}

    finally:
        session.close()


async def generate_and_save_narration(
    player_id: str,
    room_id: str,
    narration_text: str,
    narration_type: str,
    session,
) -> str:
    """
    Generate TTS audio for narration and save to database.
    Returns the audio filepath.
    """
    from config.constants import TTSConstants
    from database.models import DBNarration

    audio_filepath = None

    # Only generate TTS if enabled
    if TTSConstants.ENABLED:
        from llm.tts_module import create_tts_module

        # Create narrations directory if it doesn't exist
        narrations_dir = Path(TTSConstants.OUTPUT_DIR)
        narrations_dir.mkdir(exist_ok=True)

        # Generate unique filename
        import time

        timestamp = int(time.time() * 1000)
        audio_filename = f"narration_{player_id}_{timestamp}.mp3"
        audio_filepath = narrations_dir / audio_filename

        # Generate audio using TTS
        try:
            tts = create_tts_module()
            tts.save_to_file(narration_text, str(audio_filepath))
            print(f"[NARRATION] Generated audio: {audio_filepath}")
        except Exception as e:
            print(f"[NARRATION] TTS generation failed: {e}")
            audio_filepath = None
    else:
        print(f"[NARRATION] TTS disabled, skipping audio generation")

    # Save narration to database (with or without audio)
    db_narration = DBNarration(
        player_id=player_id,
        room_id=room_id,
        narration_text=narration_text,
        narration_type=narration_type,
        audio_filepath=str(audio_filepath) if audio_filepath else None,
        created_at=datetime.now(),
    )

    session.add(db_narration)
    session.commit()

    return str(audio_filepath) if audio_filepath else None


# ============================================================================
# Image Serving
# ============================================================================


@app.get("/images/{filename}")
async def serve_image(filename: str):
    """Serve generated room images."""
    image_path = Path("generated_images") / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)


@app.get("/narrations/{filename}")
async def serve_narration(filename: str):
    """Serve generated narration audio files."""
    audio_path = Path("generated_narrations") / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Narration audio not found")
    return FileResponse(audio_path, media_type="audio/mpeg")


# ============================================================================
# Static Files
# ============================================================================

# Mount static files (HTML, CSS, JS) - should be last
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    print("Starting Agentic Dungeon API server...")
    print("Access the game at: http://localhost:8000")
    print("API docs at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

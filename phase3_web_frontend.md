# Phase 3: Web-Based Frontend - Design Specification

This document outlines the web-based user interface implementation for Agentic Dungeon, to be implemented **after** completing Phase 1-2 architectural improvements and SQLite persistence layer.

---

## Prerequisites

Before starting Phase 3, ensure completion of:
- ✅ **Phase 1-2 (v2_todo.md)**: Repository pattern, Game class refactoring, type hints, enums
- ✅ **SQLite Persistence**: Database layer with SQLAlchemy ORM
- ✅ **Image Generation in Game Logic**: Room image URLs stored in database

---

## Overview

### Frontend Requirements

The web UI needs to provide four core features:

1. **Player's Known Map** - Visual representation of explored rooms
2. **Input Dialogue & Options** - Action buttons and text input
3. **Action Outcomes** - Real-time feed of events (player actions, others talking, etc.)
4. **Room Images** - Display LLM-generated images for immersion

### Key Principle

> **Image generation is part of the game logic (backend)**. The frontend simply retrieves and displays image URLs from the database.

---

## Technology Stack

### Backend: FastAPI + WebSockets

**Why FastAPI?**
- Native Python integration with existing codebase
- Excellent WebSocket support for real-time multiplayer
- Async/await for handling multiple concurrent players
- Automatic API documentation

**WebSocket Use Cases**:
- Real-time action broadcasts (player moves, talks, etc.)
- Live updates when other players perform actions in the same room
- Bidirectional communication for player commands

### Frontend: Vanilla HTML/CSS/JavaScript (Minimal/ASCII Style)

**Why Not React/Vue?**
- Requirements are straightforward (4 features)
- No need for complex state management
- Faster development, no build step
- Easier to iterate and modify
- Text-focused game doesn't need heavy frameworks

**Technology Choices**:
- **Map Rendering**: ASCII art in `<pre>` tags using Unicode box-drawing characters
- **Styling**: Plain CSS with terminal/retro aesthetic (green-on-black)
- **Communication**: Native WebSocket API
- **Image Display**: Standard `<img>` tags (subtle, atmospheric, low opacity)
- **No External Libraries**: Zero dependencies, single HTML file

**Design Philosophy**:
- Text-first, images as atmospheric support
- Terminal/command-line aesthetic
- Minimal, focused interface
- Classic text adventure feel

---

## Architecture Design

```
┌────────────────────────────────────────────────┐
│              Browser (Single Page)             │
├────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌─────────────────────┐    │
│  │  Known Map   │  │   Room Image        │    │
│  │  (Canvas)    │  │   <img> from DB     │    │
│  │              │  │                     │    │
│  │   [x,y]      │  │  [LLM-generated]    │    │
│  └──────────────┘  └─────────────────────┘    │
│  ┌──────────────────────────────────────────┐ │
│  │   Message/Event Log                      │ │
│  │   - Player X moved North                 │ │
│  │   - Player Y: "Hello!"                   │ │
│  │   - You interacted with a lever          │ │
│  └──────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────┐ │
│  │   Input Controls                         │ │
│  │   [N] [S] [E] [W] [Talk] [Interact]     │ │
│  │   <input> for chat/actions               │ │
│  └──────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
                    ↕ WebSocket
┌────────────────────────────────────────────────┐
│           FastAPI Backend Server               │
├────────────────────────────────────────────────┤
│  • WebSocket connection manager                │
│  • Route player actions to Game class          │
│  • Broadcast events to relevant players        │
│  • Serve static frontend files                 │
└────────────────────────────────────────────────┘
                    ↕
┌────────────────────────────────────────────────┐
│           Game Logic (Your Code)               │
├────────────────────────────────────────────────┤
│  • Process moves, actions, events              │
│  • Update player memory                        │
│  • Generate room images (via LLM)              │
│  • Store image URLs in database                │
└────────────────────────────────────────────────┘
                    ↕
┌────────────────────────────────────────────────┐
│        SQLite Database (SQLAlchemy)            │
├────────────────────────────────────────────────┤
│  • rooms table (includes image_url column)     │
│  • players, events, memory tables              │
│  • Image URLs cached after generation          │
└────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. Database Schema Addition

Add image URL to rooms table:

```python
# models/room.py (SQLAlchemy)
class Room(Base):
    __tablename__ = 'rooms'
    
    id = Column(String, primary_key=True)
    world_id = Column(String, ForeignKey('worlds.id'))
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    coords_x = Column(Integer, nullable=False)
    coords_y = Column(Integer, nullable=False)
    
    # NEW: Image URL from LLM generation
    image_url = Column(String, nullable=True)  # URL to generated image
    image_prompt = Column(String, nullable=True)  # Store prompt for regeneration
    
    created_at = Column(DateTime, nullable=False)
    
    # ... relationships
```

### 2. Image Generation in Game Logic

Image generation happens when a room is created:

```python
# services/room_service.py
class RoomService:
    def create_room(self, coords: tuple[int, int], description: str) -> Room:
        """Create new room with image generation"""
        
        # 1. Create room object
        room = Room(
            id=generate_room_id(),
            coords_x=coords[0],
            coords_y=coords[1],
            name=generate_room_name(),
            description=description,
            created_at=datetime.now()
        )
        
        # 2. Generate image (only once!)
        image_prompt = self._create_image_prompt(room)
        image_url = self.image_generator.generate(image_prompt)
        
        # 3. Store everything in database
        room.image_url = image_url
        room.image_prompt = image_prompt
        self.room_repo.save(room)
        
        return room
    
    def _create_image_prompt(self, room: Room) -> str:
        """Create prompt for image generation"""
        return f"""Fantasy dungeon room called '{room.name}'.
        Description: {room.description}
        Style: Atmospheric, detailed, game art, top-down view"""
```

**Image Generation Options**:
- OpenAI DALL-E 3 (best quality, costs money)
- Stable Diffusion (free, self-hosted)
- Midjourney API (high quality)

**Image Storage**:
- Option A: Store URLs from API (images hosted by provider)
- Option B: Download and store in S3/CloudFlare R2
- Option C: Store in database as base64 (not recommended for many images)

### 3. Backend WebSocket Server

```python
# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from typing import Dict, Set
import json

app = FastAPI()

class ConnectionManager:
    """Manage WebSocket connections per world"""
    
    def __init__(self):
        # {world_id: {player_id: websocket}}
        self.connections: Dict[str, Dict[str, WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, world_id: str, player_id: str):
        await websocket.accept()
        if world_id not in self.connections:
            self.connections[world_id] = {}
        self.connections[world_id][player_id] = websocket
    
    def disconnect(self, world_id: str, player_id: str):
        if world_id in self.connections:
            self.connections[world_id].pop(player_id, None)
    
    async def send_to_player(self, world_id: str, player_id: str, message: dict):
        """Send message to specific player"""
        if ws := self.connections.get(world_id, {}).get(player_id):
            await ws.send_json(message)
    
    async def broadcast_to_room(self, world_id: str, room_id: str, message: dict):
        """Send message to all players in a room"""
        # Query which players are in this room
        players_in_room = game.get_players_in_room(world_id, room_id)
        
        for player_id in players_in_room:
            await self.send_to_player(world_id, player_id, message)

manager = ConnectionManager()

@app.websocket("/ws/{world_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, world_id: str, player_id: str):
    await manager.connect(websocket, world_id, player_id)
    
    try:
        # Send initial state
        initial_state = {
            "type": "INITIAL_STATE",
            "player_id": player_id,
            "current_room": game.get_current_room_data(player_id),
            "known_map": game.get_player_known_map(player_id),
            "available_actions": game.get_available_actions(player_id)
        }
        await websocket.send_json(initial_state)
        
        # Listen for player actions
        while True:
            data = await websocket.receive_json()
            action_type = data.get("action")
            
            if action_type == "MOVE":
                result = game.process_player_move(player_id, data["direction"])
                
                # Send updated state to player
                await manager.send_to_player(world_id, player_id, {
                    "type": "MOVE_RESULT",
                    "success": result.success,
                    "new_room": result.room_data,
                    "updated_map": result.updated_map
                })
                
                # Broadcast to old room
                await manager.broadcast_to_room(world_id, result.old_room_id, {
                    "type": "PLAYER_LEFT",
                    "player_name": result.player_name,
                    "direction": data["direction"]
                })
                
                # Broadcast to new room
                await manager.broadcast_to_room(world_id, result.new_room_id, {
                    "type": "PLAYER_ENTERED",
                    "player_name": result.player_name
                })
            
            elif action_type == "TALK":
                result = game.process_talk(player_id, data["message"])
                
                # Broadcast to everyone in the room
                await manager.broadcast_to_room(world_id, result.room_id, {
                    "type": "MESSAGE",
                    "player_id": player_id,
                    "player_name": result.player_name,
                    "text": data["message"],
                    "timestamp": result.timestamp
                })
            
            elif action_type == "INTERACT":
                result = game.process_interaction(player_id, data["description"])
                
                # Broadcast to room
                await manager.broadcast_to_room(world_id, result.room_id, {
                    "type": "INTERACTION",
                    "player_name": result.player_name,
                    "description": data["description"],
                    "result": result.description
                })
    
    except WebSocketDisconnect:
        manager.disconnect(world_id, player_id)
        # Notify others
        current_room = game.get_player_room(player_id)
        await manager.broadcast_to_room(world_id, current_room.id, {
            "type": "PLAYER_DISCONNECTED",
            "player_id": player_id
        })

# Serve static frontend files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 4. Frontend Implementation

**File Structure**:
```
static/
├── index.html          # Main game page
├── styles.css          # Styling
└── game.js            # Game logic
```

**Key Frontend Components**:

#### A. Map Rendering (Canvas)
```javascript
// game.js
class MapRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.roomSize = 40;
        this.centerX = this.canvas.width / 2;
        this.centerY = this.canvas.height / 2;
    }
    
    drawMap(knownRooms, currentRoomId) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        knownRooms.forEach(room => {
            const x = this.centerX + room.coords_x * this.roomSize;
            const y = this.centerY - room.coords_y * this.roomSize; // Flip Y
            
            // Draw room
            this.ctx.fillStyle = room.id === currentRoomId ? '#4CAF50' : '#2196F3';
            this.ctx.fillRect(x - 15, y - 15, 30, 30);
            
            // Draw room label
            this.ctx.fillStyle = 'white';
            this.ctx.font = '10px Arial';
            this.ctx.textAlign = 'center';
            this.ctx.fillText(room.name.substring(0, 4), x, y + 5);
            
            // Draw connections
            if (room.connections) {
                this.ctx.strokeStyle = '#666';
                this.ctx.lineWidth = 2;
                
                room.connections.forEach(dir => {
                    const offset = this.getDirectionOffset(dir);
                    this.ctx.beginPath();
                    this.ctx.moveTo(x, y);
                    this.ctx.lineTo(x + offset.x * 20, y + offset.y * 20);
                    this.ctx.stroke();
                });
            }
        });
    }
    
    getDirectionOffset(direction) {
        const offsets = {
            'N': {x: 0, y: -1}, 'S': {x: 0, y: 1},
            'E': {x: 1, y: 0}, 'W': {x: -1, y: 0}
        };
        return offsets[direction] || {x: 0, y: 0};
    }
}
```

#### B. Message Log
```javascript
class MessageLog {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
    }
    
    addMessage(type, data) {
        const div = document.createElement('div');
        div.className = `message message-${type}`;
        
        switch(type) {
            case 'talk':
                div.textContent = `${data.player_name}: ${data.text}`;
                break;
            case 'move':
                div.textContent = `${data.player_name} ${data.action}`;
                break;
            case 'interact':
                div.textContent = `${data.player_name} ${data.description}`;
                break;
            case 'system':
                div.textContent = data.text;
                div.className += ' system';
                break;
        }
        
        this.container.appendChild(div);
        div.scrollIntoView({ behavior: 'smooth' });
        
        // Keep only last 100 messages
        if (this.container.children.length > 100) {
            this.container.removeChild(this.container.firstChild);
        }
    }
}
```

#### C. WebSocket Manager
```javascript
class GameConnection {
    constructor(worldId, playerId) {
        this.worldId = worldId;
        this.playerId = playerId;
        this.ws = null;
        this.onMessageCallbacks = [];
    }
    
    connect() {
        this.ws = new WebSocket(`ws://localhost:8000/ws/${this.worldId}/${this.playerId}`);
        
        this.ws.onopen = () => {
            console.log('Connected to game server');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.onMessageCallbacks.forEach(cb => cb(data));
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('Disconnected from server');
            // Auto-reconnect after 3 seconds
            setTimeout(() => this.connect(), 3000);
        };
    }
    
    send(action, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action, ...data }));
        }
    }
    
    onMessage(callback) {
        this.onMessageCallbacks.push(callback);
    }
}
```

#### D. Main Game Controller
```javascript
class GameUI {
    constructor() {
        this.connection = new GameConnection('default-world', this.generatePlayerId());
        this.mapRenderer = new MapRenderer('map-canvas');
        this.messageLog = new MessageLog('message-log');
        
        this.currentRoom = null;
        this.knownMap = [];
        
        this.setupEventHandlers();
        this.connection.connect();
    }
    
    setupEventHandlers() {
        // Handle incoming messages
        this.connection.onMessage((data) => {
            switch(data.type) {
                case 'INITIAL_STATE':
                    this.handleInitialState(data);
                    break;
                case 'MOVE_RESULT':
                    this.handleMoveResult(data);
                    break;
                case 'MESSAGE':
                    this.messageLog.addMessage('talk', data);
                    break;
                case 'PLAYER_ENTERED':
                case 'PLAYER_LEFT':
                    this.messageLog.addMessage('move', data);
                    break;
                case 'INTERACTION':
                    this.messageLog.addMessage('interact', data);
                    break;
            }
        });
        
        // Movement buttons
        ['N', 'S', 'E', 'W'].forEach(dir => {
            document.getElementById(`btn-${dir}`).onclick = () => {
                this.connection.send('MOVE', { direction: dir });
            };
        });
        
        // Talk button
        document.getElementById('btn-talk').onclick = () => {
            const input = document.getElementById('chat-input');
            if (input.value.trim()) {
                this.connection.send('TALK', { message: input.value });
                input.value = '';
            }
        };
        
        // Interact button
        document.getElementById('btn-interact').onclick = () => {
            const description = prompt('What do you do?');
            if (description) {
                this.connection.send('INTERACT', { description });
            }
        };
    }
    
    handleInitialState(data) {
        this.currentRoom = data.current_room;
        this.knownMap = data.known_map;
        this.updateUI();
    }
    
    handleMoveResult(data) {
        if (data.success) {
            this.currentRoom = data.new_room;
            this.knownMap = data.updated_map;
            this.updateUI();
        }
    }
    
    updateUI() {
        // Update room image
        document.getElementById('room-image').src = this.currentRoom.image_url;
        
        // Update room info
        document.getElementById('room-name').textContent = this.currentRoom.name;
        document.getElementById('room-description').textContent = this.currentRoom.description;
        
        // Redraw map
        this.mapRenderer.drawMap(this.knownMap, this.currentRoom.id);
    }
    
    generatePlayerId() {
        return 'player-' + Math.random().toString(36).substr(2, 9);
    }
}

// Initialize when page loads
window.onload = () => {
    new GameUI();
};
```

---

## Project Structure

```
agentic-dungeon/
├── backend/
│   ├── main.py                  # FastAPI server with WebSocket endpoints
│   ├── connection_manager.py    # WebSocket connection management
│   └── requirements.txt         # fastapi, uvicorn, websockets
│
├── static/                      # Frontend files (served by FastAPI)
│   ├── index.html              # Main game UI
│   ├── styles.css              # Styling
│   └── game.js                 # Game logic & WebSocket handling
│
├── src/                         # Existing game logic
│   ├── models/                 # SQLAlchemy models
│   ├── services/               # Game services
│   ├── repositories/           # Data access
│   └── game.py                 # Main game orchestrator
│
└── database/
    └── game.db                 # SQLite database
```

---

## Implementation Phases

### Week 1: Backend WebSocket Server
- [ ] Set up FastAPI project structure
- [ ] Implement ConnectionManager class
- [ ] Create WebSocket endpoint with basic echo
- [ ] Test connection with simple HTML client

### Week 2: Game Logic Integration
- [ ] Connect FastAPI to Game class
- [ ] Implement action handlers (MOVE, TALK, INTERACT)
- [ ] Add room broadcasting logic
- [ ] Test with multiple concurrent connections

### Week 3: Frontend Development
- [ ] Create HTML layout with 4 main sections
- [ ] Implement Canvas-based map rendering
- [ ] Build message log with auto-scroll
- [ ] Add control buttons and input fields

### Week 4: Integration & Polish
- [ ] Connect frontend to WebSocket
- [ ] Test real-time multiplayer scenarios
- [ ] Add error handling and reconnection logic
- [ ] Style and improve UX

### Week 5: Testing & Deployment
- [ ] End-to-end testing
- [ ] Performance optimization
- [ ] Deploy to Render/Railway
- [ ] Documentation

---

## Key Design Decisions

### 1. Image Generation is Backend Responsibility

**Reasoning**:
- Expensive operation (LLM API calls cost money/time)
- Should only happen once per room
- Results cached in database
- Frontend just displays pre-generated URLs

**Flow**:
```
1. Game creates new room
2. Room service calls image generator
3. Image URL stored in rooms.image_url
4. Frontend receives room data with image_url
5. Frontend displays <img src="{image_url}">
```

### 2. WebSocket for Real-Time Updates

**Reasoning**:
- Players need to see each other's actions immediately
- Multiplayer witnessing system requires live updates
- More efficient than polling

**Alternative Considered**: Server-Sent Events (SSE)
- Rejected because one-way only (server→client)
- WebSockets provide bidirectional communication

### 3. Single-Page Application (SPA)

**Reasoning**:
- Game state is continuous (no page reloads)
- Better UX for real-time game
- Simpler to manage WebSocket connection

### 4. ASCII Map with `<pre>` Tags (RECOMMENDED for Minimal Style)

**Reasoning**:
- Perfect for text-adventure aesthetic
- Zero rendering complexity
- Uses Unicode box-drawing characters (┌─┐│└┘├┤┬┴┼)
- Easy to update and maintain
- Fits the terminal/retro theme

**Example ASCII Map**:
```
     ┌─┐
     │ │
 ┌─┐ @ ┌─┐
 │ └─┼─┘ │
 │   │   │
 └───┴───┘
```

**Alternative**: Canvas/SVG
- Use if you want more graphical representation
- Canvas for performance, SVG for interactivity
- Consider if aesthetics shift away from text-focus

---

## Minimal Example Implementation

A complete working example has been created in `static/minimal_example.html` demonstrating:

### Visual Design
- **Color Scheme**: Green-on-black terminal aesthetic (#00ff00 on #0c0c0c)
- **Typography**: Courier New monospace throughout
- **Layout**: Two-column grid (map sidebar + main game area)
- **Image Treatment**: Low opacity (0.4), grayscale filter, subtle atmospheric effect

### Key Features Implemented

1. **ASCII Map Display**
   - Uses `<pre>` tag with Unicode box-drawing characters
   - Shows current position with @ symbol
   - Other rooms marked with #
   - Animated between different layouts (demo)

2. **Room Image Integration**
   - Displayed but de-emphasized (40% opacity, grayscale)
   - Overlaid with gradient to maintain text readability
   - Room name overlaid on image

3. **Message Log**
   - Color-coded messages:
     - System messages: Gray
     - Player talk: Cyan
     - Actions: Yellow
   - Auto-scrolls to latest
   - Maintains last 100 messages

4. **Command Interface**
   - Direction buttons (⬆ NORTH, ⬇ SOUTH, ➡ EAST, ⬅ WEST)
   - Text input for commands (talk, interact, observe)
   - Green-on-black styling with hover effects

5. **Status Indicators**
   - Player name display
   - Connection status with pulsing dot animation
   - Players present in current room

### File Structure
```html
static/minimal_example.html  (Single file, ~460 lines)
├── <style>     Embedded CSS (~200 lines)
├── <body>      HTML structure (~100 lines)
└── <script>    Game logic (~160 lines)
```

### How to Use

1. **Open directly in browser**:
   ```bash
   # Just open the file
   open static/minimal_example.html
   ```

2. **Or serve with Python**:
   ```bash
   python -m http.server 8000
   # Visit: http://localhost:8000/static/minimal_example.html
   ```

3. **Connect to FastAPI backend** (when ready):
   - Uncomment WebSocket connection code
   - Backend at `ws://localhost:8000/ws/{world_id}/{player_id}`

### Customization Options

**Color Schemes**:
```css
/* Green on black (default) */
color: #00ff00; background: #0c0c0c;

/* Amber on black */
color: #ffb000; background: #0c0c0c;

/* White on blue (classic) */
color: #ffffff; background: #0000aa;
```

**Fonts**:
- Current: Courier New (built-in)
- Retro pixel: Add Press Start 2P from Google Fonts
- Terminal: VT323 or IBM Plex Mono

**Image Treatment**:
- Adjust opacity: Change from 0.4 to 0.6 for more visible images
- Remove grayscale: Delete `filter: grayscale(50%)`
- Full-screen option: Remove width/height constraints

### Next Steps

1. Replace demo functions with real WebSocket calls
2. Implement actual map generation from game data
3. Add player authentication
4. Connect to FastAPI backend
5. Test with multiple concurrent players

---

## Dependencies

### Backend
```bash
pip install fastapi uvicorn[standard] websockets python-multipart
```

### Frontend
- No npm dependencies needed!
- Pure HTML/CSS/JavaScript
- Optional: Add Tailwind CSS via CDN for styling

---

## Deployment Considerations

### Option 1: Render (Recommended)
- Free tier available
- WebSocket support included
- Auto-deploy from GitHub
- https://render.com

### Option 2: Railway
- Similar to Render
- Good free tier
- https://railway.app

### Option 3: Self-hosted (DigitalOcean/AWS)
- More control
- Need to configure nginx for WebSockets
- More complex but cheaper at scale

---

## Future Enhancements (Post-Phase 3)

### Phase 4 Ideas:
- [ ] Mobile-responsive design
- [ ] Sound effects and ambient music
- [ ] Minimap zoom and pan
- [ ] Player avatars
- [ ] Inventory system UI
- [ ] Combat UI (if adding combat)
- [ ] Admin panel for game management
- [ ] Analytics dashboard

---

## Success Criteria

Phase 3 is complete when:
- ✅ Players can connect via browser
- ✅ Map updates as player explores
- ✅ Room images display correctly
- ✅ Real-time chat works
- ✅ Multiple players can interact simultaneously
- ✅ Game state persists across reconnections
- ✅ Deployed and accessible via URL

---

## Estimated Effort

- **Development**: 4-5 weeks (part-time)
- **Testing**: 1 week
- **Deployment**: 2-3 days
- **Total**: ~6 weeks

---

## Notes

- Image generation should be implemented in Phase 2 (persistence layer) as part of room creation
- Frontend image display is trivial once URLs are in database
- Focus on functionality first, polish UI later
- Start with simple styling, improve iteratively
- Test with 2-3 concurrent players before scaling

---

## References

- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/)
- [HTML5 Canvas Tutorial](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial)
- [WebSocket API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

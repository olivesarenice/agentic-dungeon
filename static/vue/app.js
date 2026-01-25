// Game Screen Component - exports globally for use in index.html
const GameScreenComponent = {
    data() {
        return {
            playerId: null,
            status: 'ready', // ready, thinking, speaking
            currentRoom: {
                name: 'LOADING...',
                description: 'Initializing...',
                imageUrl: '',
                coords: { x: 0, y: 0 }
            },
            treasureHints: [],
            availableExits: [],
            knownRooms: [],
            events: [],
            imageOpacity: 0,
            interactModalVisible: false,
            interactInput: '',
            victoryModalVisible: false,
            victoryShown: false,
            currentAudio: null,
            lastNarrationId: null,
            tooltipVisible: false,
            tooltipRoom: null,
            tooltipX: 0,
            tooltipY: 0
        };
    },

    computed: {
        statusIcon() {
            const icons = {
                ready: 'fa-solid fa-circle-check',
                thinking: 'fa-solid fa-brain',
                speaking: 'fa-solid fa-microphone'
            };
            return icons[this.status] || 'fa-solid fa-circle-check';
        },

        statusText() {
            const texts = {
                ready: 'Ready',
                thinking: 'Thinking',
                speaking: 'Speaking'
            };
            return texts[this.status] || 'Ready';
        },

        roomDescriptionHtml() {
            let desc = this.currentRoom.description;
            if (this.treasureHints.length > 0) {
                const hints = this.treasureHints.map(h => h.hint).sort((a, b) => b.length - a.length);
                hints.forEach(hint => {
                    const regex = new RegExp(`(${this.escapeRegex(hint)})`, 'gi');
                    desc = desc.replace(regex, '<span class="treasure-hint-highlight">$1</span>');
                });
            }
            return desc;
        }
    },

    methods: {
        escapeRegex(str) {
            return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        },

        addEvent(type, text) {
            // Filter out player enter/leave events
            if (text.includes('entered the') || text.includes('left the')) return;

            this.events.push({ type, text, id: Date.now() });
            // Keep only the latest 10 events
            if (this.events.length > 10) this.events.shift();

            this.$nextTick(() => {
                const log = this.$refs.eventsLog;
                if (log) log.scrollTop = log.scrollHeight;
            });
        },

        async loadGameState() {
            try {
                this.status = 'thinking';
                const response = await fetch(`/api/state/${this.playerId}`);
                if (!response.ok) {
                    const error = await response.json();
                    this.addEvent('error', `Failed: ${error.detail}`);
                    return;
                }
                const state = await response.json();
                this.updateUI(state);
                this.status = 'ready';
            } catch (error) {
                this.addEvent('error', `Error: ${error.message}`);
                this.status = 'ready';
            }
        },

        updateUI(state, forceImageReload = false) {
            let imageUrl = state.current_room.image_url || '';
            if (forceImageReload && imageUrl) {
                imageUrl += (imageUrl.includes('?') ? '&' : '?') + `_t=${Date.now()}`;
            }

            this.currentRoom = {
                name: state.current_room.name.toUpperCase(),
                description: state.current_room.description,
                imageUrl,
                coords: state.current_room.coords
            };

            this.imageOpacity = 0;
            setTimeout(() => { this.imageOpacity = 1; }, 300);

            this.treasureHints = state.treasure_hints || [];
            this.availableExits = state.available_exits || [];
            this.knownRooms = state.known_rooms || [];

            // Load DM narration events from server into event log
            // Show all NARRATION_* types (DM spoken narrations)
            if (state.recent_events && state.recent_events.length > 0) {
                state.recent_events.forEach(event => {
                    // Only show NARRATION_* action types from DM
                    if (event.actor === 'DM' && event.action.startsWith('NARRATION_')) {
                        // Check if we already have this event (by timestamp)
                        const eventTime = new Date(event.timestamp).getTime();
                        const exists = this.events.some(e => e.timestamp === eventTime);
                        if (!exists) {
                            this.events.push({
                                type: 'system',
                                text: `🎙️ ${event.content}`,
                                id: eventTime,
                                timestamp: eventTime
                            });
                        }
                    }
                });
                // Sort by timestamp and keep only latest 10
                this.events.sort((a, b) => (a.timestamp || a.id) - (b.timestamp || b.id));
                while (this.events.length > 10) this.events.shift();
            }

            this.$nextTick(() => this.drawMap());

            if (state.objective && state.objective.has_won && !this.victoryShown) {
                this.victoryModalVisible = true;
                this.victoryShown = true;
            }
        },

        async move(direction) {
            if (!this.availableExits.includes(direction)) return;
            await this.sendAction('MOVE', { direction });
        },

        showInteractModal() {
            this.interactModalVisible = true;
            this.$nextTick(() => this.$refs.interactInput?.focus());
        },

        closeInteractModal() {
            this.interactModalVisible = false;
            this.interactInput = '';
        },

        async executeInteract() {
            if (!this.interactInput.trim()) {
                this.addEvent('error', 'Please describe what you want to do');
                return;
            }
            const description = this.interactInput;
            this.closeInteractModal();
            this.addEvent('action', `You ${description}`);
            await this.sendAction('INTERACT', { description: description });
        },

        async sendAction(action, params = {}) {
            try {
                this.status = 'thinking';
                const isInteract = action === 'INTERACT';

                const response = await fetch('/api/action', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ player_id: this.playerId, action, ...params })
                });

                if (!response.ok) {
                    const error = await response.json();
                    this.addEvent('error', `Failed: ${error.detail}`);
                    this.status = 'ready';
                    return;
                }

                const data = await response.json();
                if (data.success) {
                    if (data.state) this.updateUI(data.state, isInteract);
                    // Filter out "Moved X" messages - only show non-move messages
                    if (data.message && !data.message.startsWith('Moved ')) {
                        this.addEvent('system', data.message);
                    }
                    await this.fetchAndPlayNarration();
                } else {
                    this.addEvent('error', data.message);
                    this.status = 'ready';
                }
            } catch (error) {
                this.addEvent('error', `Error: ${error.message}`);
                this.status = 'ready';
            }
        },

        async fetchAndPlayNarration() {
            try {
                const response = await fetch(`/api/narration/${this.playerId}/latest`);
                if (!response.ok) {
                    this.status = 'ready';
                    return;
                }

                const data = await response.json();
                if (data.narration && data.narration.id !== this.lastNarrationId) {
                    if (this.currentAudio) {
                        this.currentAudio.pause();
                        this.currentAudio = null;
                    }
                    await this.playNarration(data.narration);
                    this.lastNarrationId = data.narration.id;
                } else {
                    this.status = 'ready';
                }
            } catch (error) {
                console.error('Narration error:', error);
                this.status = 'ready';
            }
        },

        async playNarration(narration) {
            // NOTE: Narration text is now loaded from server events in updateUI()
            // Do NOT add here to avoid duplicates

            if (!narration.audio_url) {
                this.status = 'ready';
                return;
            }

            try {
                this.status = 'speaking';

                const audio = new Audio(narration.audio_url);
                this.currentAudio = audio;

                await new Promise((resolve) => {
                    audio.onended = () => {
                        this.currentAudio = null;
                        this.status = 'ready';
                        resolve();
                    };
                    audio.onerror = () => {
                        this.status = 'ready';
                        resolve();
                    };
                    audio.play().catch(() => {
                        this.status = 'ready';
                        resolve();
                    });
                });
            } catch (error) {
                this.status = 'ready';
            }
        },

        drawMap() {
            const canvas = this.$refs.mapCanvas;
            if (!canvas || !this.knownRooms.length) return;

            const ctx = canvas.getContext('2d');
            const { width, height } = canvas;
            const curr = this.currentRoom.coords;

            ctx.fillStyle = '#0d0d0d';
            ctx.fillRect(0, 0, width, height);

            let minX = curr.x, maxX = curr.x, minY = curr.y, maxY = curr.y;
            this.knownRooms.forEach(r => {
                minX = Math.min(minX, r.coords.x);
                maxX = Math.max(maxX, r.coords.x);
                minY = Math.min(minY, r.coords.y);
                maxY = Math.max(maxY, r.coords.y);
            });

            const gridW = maxX - minX + 1;
            const gridH = maxY - minY + 1;
            const spacing = 8;
            const cellSize = Math.min(
                (width - 60 - (gridW - 1) * spacing) / gridW,
                (height - 60 - (gridH - 1) * spacing) / gridH
            );

            const totalW = gridW * cellSize + (gridW - 1) * spacing;
            const totalH = gridH * cellSize + (gridH - 1) * spacing;
            const offsetX = (width - totalW) / 2;
            const offsetY = (height - totalH) / 2;

            this.knownRooms.forEach(room => {
                const x = offsetX + (room.coords.x - minX) * (cellSize + spacing);
                const y = offsetY + (maxY - room.coords.y) * (cellSize + spacing);
                const isCurr = room.coords.x === curr.x && room.coords.y === curr.y;

                ctx.fillStyle = isCurr ? 'rgba(100, 85, 65, 0.6)' : 'rgba(50, 45, 40, 0.4)';
                ctx.fillRect(x, y, cellSize, cellSize);

                const paths = room.paths || [];
                ctx.strokeStyle = isCurr ? '#8c7858' : '#5a5045';
                ctx.lineWidth = 2;

                if (!paths.includes('N')) {
                    ctx.beginPath();
                    ctx.moveTo(x, y);
                    ctx.lineTo(x + cellSize, y);
                    ctx.stroke();
                }
                if (!paths.includes('S')) {
                    ctx.beginPath();
                    ctx.moveTo(x, y + cellSize);
                    ctx.lineTo(x + cellSize, y + cellSize);
                    ctx.stroke();
                }
                if (!paths.includes('W')) {
                    ctx.beginPath();
                    ctx.moveTo(x, y);
                    ctx.lineTo(x, y + cellSize);
                    ctx.stroke();
                }
                if (!paths.includes('E')) {
                    ctx.beginPath();
                    ctx.moveTo(x + cellSize, y);
                    ctx.lineTo(x + cellSize, y + cellSize);
                    ctx.stroke();
                }

                if (isCurr) {
                    ctx.fillStyle = '#c9a870';
                    ctx.beginPath();
                    ctx.arc(x + cellSize / 2, y + cellSize / 2, cellSize * 0.25, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = '#e8d4a8';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            });
        },

        continueExploring() {
            this.victoryModalVisible = false;
        },

        createNewWorld() {
            this.$emit('back-to-start');
        },

        backToWorldSelection() {
            this.$emit('back-to-start');
        },

        handleMapMouseMove(e) {
            const canvas = this.$refs.mapCanvas;
            if (!canvas || !this.knownRooms.length) return;

            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const room = this.getRoomAtPosition(mouseX, mouseY);

            if (room) {
                this.tooltipRoom = room;
                this.tooltipVisible = true;
                this.tooltipX = e.clientX + 15;
                this.tooltipY = e.clientY + 15;
            } else {
                this.tooltipVisible = false;
                this.tooltipRoom = null;
            }
        },

        handleMapMouseLeave() {
            this.tooltipVisible = false;
            this.tooltipRoom = null;
        },

        getRoomAtPosition(mouseX, mouseY) {
            const canvas = this.$refs.mapCanvas;
            if (!canvas || !this.knownRooms.length) return null;

            const { width, height } = canvas;
            const curr = this.currentRoom.coords;

            let minX = curr.x, maxX = curr.x, minY = curr.y, maxY = curr.y;
            this.knownRooms.forEach(r => {
                minX = Math.min(minX, r.coords.x);
                maxX = Math.max(maxX, r.coords.x);
                minY = Math.min(minY, r.coords.y);
                maxY = Math.max(maxY, r.coords.y);
            });

            const gridW = maxX - minX + 1;
            const gridH = maxY - minY + 1;
            const spacing = 8;
            const cellSize = Math.min(
                (width - 60 - (gridW - 1) * spacing) / gridW,
                (height - 60 - (gridH - 1) * spacing) / gridH
            );

            const totalW = gridW * cellSize + (gridW - 1) * spacing;
            const totalH = gridH * cellSize + (gridH - 1) * spacing;
            const offsetX = (width - totalW) / 2;
            const offsetY = (height - totalH) / 2;

            for (const room of this.knownRooms) {
                const x = offsetX + (room.coords.x - minX) * (cellSize + spacing);
                const y = offsetY + (maxY - room.coords.y) * (cellSize + spacing);

                if (mouseX >= x && mouseX <= x + cellSize &&
                    mouseY >= y && mouseY <= y + cellSize) {
                    return room;
                }
            }

            return null;
        }
    },

    mounted() {
        const id = localStorage.getItem('playerId');
        if (!id) {
            this.addEvent('error', 'No player ID found. Redirecting...');
            setTimeout(() => this.$emit('back-to-start'), 2000);
            return;
        }

        this.playerId = id;
        this.addEvent('system', 'Connecting to server...');

        this.loadGameState().then(() => {
            this.addEvent('system', 'Ready! Use movement or click INTERACT.');
        });
    },

    template: `
        <div>
            <!-- Fixed Status Indicator - Bottom Left -->
            <div class="status-indicator" :class="status">
                <i :class="statusIcon"></i>
                <span class="status-text">{{ statusText }}</span>
            </div>
            
            <div class="game-container">
                <!-- Left Sidebar -->
                <div class="left-sidebar">
                    <div class="panel">
                        <h3><i class="fa-solid fa-map"></i> Map</h3>
                        <canvas ref="mapCanvas" class="map-canvas" width="280" height="300" 
                                @mousemove="handleMapMouseMove" 
                                @mouseleave="handleMapMouseLeave"></canvas>
                    </div>
                    
                    <div class="panel">
                        <h3><i class="fa-solid fa-compass"></i> Movement</h3>
                        <div class="movement-grid">
                            <button @click="move('N')" :disabled="!availableExits.includes('N')" class="move-btn btn-n"><i class="fa-solid fa-arrow-up"></i><br>North</button>
                            <button @click="move('W')" :disabled="!availableExits.includes('W')" class="move-btn btn-w"><i class="fa-solid fa-arrow-left"></i><br>West</button>
                            <button @click="showInteractModal" class="move-btn btn-interact"><i class="fa-solid fa-hand-pointer"></i><br>Interact</button>
                            <button @click="move('E')" :disabled="!availableExits.includes('E')" class="move-btn btn-e"><i class="fa-solid fa-arrow-right"></i><br>East</button>
                            <button @click="move('S')" :disabled="!availableExits.includes('S')" class="move-btn btn-s"><i class="fa-solid fa-arrow-down"></i><br>South</button>
                        </div>
                        <div class="exits-info">Available: {{ availableExits.join(', ') || 'None' }}</div>
                    </div>
                    
                <button @click="backToWorldSelection"><i class="fa-solid fa-arrow-left"></i> Back to World Selection</button>
                </div>
                
                <div class="center-panel">
                    <div class="room-viewport">
                        <img :src="currentRoom.imageUrl" :style="{ opacity: imageOpacity }" alt="Room">
                    </div>
                    <div class="room-title">{{ currentRoom.name }}</div>
                    <div class="room-description" v-html="roomDescriptionHtml"></div>
                </div>
                
                <!-- Right Sidebar -->
                <div class="right-sidebar">
                    <div class="panel" style="flex: 1;">
                        <h3><i class="fa-solid fa-scroll"></i> Events</h3>
                        <div ref="eventsLog" class="events-log" style="max-height: none; height: 100%;">
                            <div v-for="event in events" :key="event.id" class="event" :class="event.type">{{ event.text }}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div v-if="interactModalVisible" class="modal" @click.self="closeInteractModal">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>What do you do?</h3>
                        <button class="close-btn" @click="closeInteractModal">✕</button>
                    </div>
                    <input ref="interactInput" v-model="interactInput" type="text" placeholder="Describe your action..." @keypress.enter="executeInteract">
                    <button type="button" @click="executeInteract" class="proceed-btn">→ PROCEED</button>
                </div>
            </div>
            
            <div v-if="victoryModalVisible" class="modal victory-modal">
                <div class="modal-content">
                    <div class="victory-title"><i class="fa-solid fa-trophy"></i> Victory! <i class="fa-solid fa-trophy"></i></div>
                    <div class="victory-message">You've found all the treasures!<br>The dungeon's secrets are now yours.</div>
                    <div class="victory-buttons">
                        <button @click="continueExploring">Continue Exploring</button>
                        <button @click="createNewWorld">Create New World</button>
                    </div>
                </div>
            </div>
            
            <!-- Map Tooltip -->
            <div v-if="tooltipVisible && tooltipRoom" class="map-tooltip" :style="{ left: tooltipX + 'px', top: tooltipY + 'px' }">
                <h4>{{ tooltipRoom.name }}</h4>
                <p>{{ tooltipRoom.description }}</p>
                <img v-if="tooltipRoom.image_url" :src="tooltipRoom.image_url" alt="Room">
            </div>
        </div>
        `
};

// Register globally so index.html can use it
if (window.Vue) {
    window.GameScreenComponent = GameScreenComponent;
}

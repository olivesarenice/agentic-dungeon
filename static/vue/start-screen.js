// Start Screen Component
(function () {
    const app = window.Vue.createApp({});

    app.component('start-screen', {
        props: ['faker'],
        data() {
            return {
                worlds: [],
                selectedWorldId: null,
                showCreateForm: false,
                worldTheme: '',
                selectedArtStyle: 'retro_anime',
                selectedGridSize: 3,
                loadingWorlds: false,
                creatingWorld: false,
                errorMessage: '',
                // Progress tracking
                showProgressModal: false,
                generatingWorldId: null,
                generationProgress: {
                    percent: 0,
                    step: 'Initializing...',
                    totalRooms: 0,
                    generatedRooms: 0,
                    status: 'GENERATING'
                },
                progressPollInterval: null
            };
        },
        async mounted() {
            await this.loadWorlds();
        },
        computed: {
            themeWordCount() {
                return this.worldTheme.trim().split(/\s+/).filter(w => w).length;
            },
            isThemeValid() {
                const trimmed = this.worldTheme.trim();
                return trimmed.length > 0 && this.themeWordCount <= 200;
            },
            themeValidationClass() {
                if (this.themeWordCount === 0) return '';
                if (this.themeWordCount > 200) return 'error';
                if (this.themeWordCount > 150) return 'warning';
                return '';
            }
        },
        methods: {
            async loadWorlds() {
                this.loadingWorlds = true;
                try {
                    const response = await fetch('/api/worlds');
                    const data = await response.json();
                    // Filter to only show completed worlds, and add player info
                    const completedWorlds = data.worlds.filter(w => w.generation_status === 'COMPLETE');
                    this.worlds = await Promise.all(completedWorlds.map(async (world) => {
                        try {
                            const playersResp = await fetch(`/api/worlds/${world.id}/players`);
                            const playersData = await playersResp.json();
                            const humanPlayer = playersData.players?.find(p => p.player_type === 'HUMAN');
                            return { ...world, player: humanPlayer || null };
                        } catch {
                            return { ...world, player: null };
                        }
                    }));
                } catch (error) {
                    this.errorMessage = `Error: ${error.message}`;
                } finally {
                    this.loadingWorlds = false;
                }
            },

            formatDate(dateString) {
                const date = new Date(dateString);
                return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            },

            truncateTheme(theme, maxLength = 60) {
                if (!theme) return '';
                return theme.length > maxLength ? theme.substring(0, maxLength) + '...' : theme;
            },

            async enterWorld(worldId) {
                const world = this.worlds.find(w => w.id === worldId);
                if (world && world.player) {
                    localStorage.setItem('playerId', world.player.id);
                    this.$emit('start-game');
                } else {
                    await this.createPlayerForWorld(worldId);
                }
            },

            async createNewWorld() {
                if (!this.faker) return;
                this.creatingWorld = true;
                this.errorMessage = '';

                try {
                    const worldName = `${this.faker.word.adjective()}-${this.faker.color.human()}-${this.faker.animal.type()}`;
                    const response = await fetch('/api/worlds', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: worldName,
                            theme: this.worldTheme.trim() || null,
                            art_style: this.selectedArtStyle,
                            grid_size: this.selectedGridSize,
                            npc_count: 0
                        })
                    });
                    if (!response.ok) throw new Error('Failed to create world');
                    const worldData = await response.json();

                    // Show progress modal and start polling
                    this.generatingWorldId = worldData.id;
                    this.showProgressModal = true;
                    this.showCreateForm = false;
                    this.generationProgress = {
                        percent: 0,
                        step: 'Initializing world...',
                        totalRooms: this.selectedGridSize * this.selectedGridSize,
                        generatedRooms: 0,
                        status: 'GENERATING'
                    };

                    // Start polling for progress
                    this.startProgressPolling(worldData.id);

                } catch (error) {
                    this.errorMessage = `Error: ${error.message}`;
                    this.creatingWorld = false;
                }
            },

            startProgressPolling(worldId) {
                // Poll every 2 seconds
                this.progressPollInterval = setInterval(async () => {
                    try {
                        const response = await fetch(`/api/worlds/${worldId}/generation-status`);
                        if (!response.ok) return;

                        const data = await response.json();
                        this.generationProgress = {
                            percent: data.progress_percent,
                            step: data.current_step,
                            totalRooms: data.total_rooms,
                            generatedRooms: data.generated_rooms,
                            status: data.status
                        };

                        // Check if complete
                        if (data.status === 'COMPLETE') {
                            this.stopProgressPolling();
                            this.creatingWorld = false;
                            // Auto-create player and start game
                            await this.createPlayerForWorld(worldId);
                        } else if (data.status === 'FAILED') {
                            this.stopProgressPolling();
                            this.showProgressModal = false;
                            this.creatingWorld = false;
                            this.errorMessage = data.error_message || 'World generation failed';
                        }
                    } catch (error) {
                        console.error('Progress polling error:', error);
                    }
                }, 2000);
            },

            stopProgressPolling() {
                if (this.progressPollInterval) {
                    clearInterval(this.progressPollInterval);
                    this.progressPollInterval = null;
                }
            },

            async createPlayerForWorld(worldId) {
                if (!this.faker) return;
                try {
                    const playerName = this.faker.person.firstName();
                    const response = await fetch('/api/players', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            world_id: worldId,
                            player_name: playerName,
                            player_type: 'HUMAN'
                        })
                    });
                    if (!response.ok) throw new Error('Failed to create player');
                    const playerData = await response.json();
                    localStorage.setItem('playerId', playerData.id);
                    this.$emit('start-game');
                } catch (error) {
                    this.errorMessage = `Error: ${error.message}`;
                }
            }
        },
        template: `
            <div class="start-container">
                <div class="start-content">
                    <h1 class="start-title">AGENTIC DUNGEON</h1>
                    
                    <div v-if="!showCreateForm" class="panel">
                        <div class="panel-header">
                            <h2>Select or Create World</h2>
                            <button @click="showCreateForm = true" class="create-world-btn">+ Create New World</button>
                        </div>
                        <div v-if="loadingWorlds" class="loading">Loading worlds...</div>
                        <div v-else>
                            <div class="section">
                                <h3>Your Worlds</h3>
                                <div class="world-grid">
                                    <p v-if="worlds.length === 0" class="no-worlds-message">
                                        No worlds found. Create a new one!
                                    </p>
                                    <div v-for="world in worlds" :key="world.id" class="world-card">
                                        <img v-if="world.lobby_image_url" :src="world.lobby_image_url" class="world-thumbnail" alt="World preview">
                                        <div v-else class="world-thumbnail-placeholder">
                                            <i class="fa-solid fa-dungeon"></i>
                                        </div>
                                        <div class="world-card-info">
                                            <h4 class="world-card-name">{{ world.name }}</h4>
                                            <span class="art-style-badge">{{ world.art_style.replace('_', ' ') }}</span>
                                            <p class="world-card-theme">{{ truncateTheme(world.theme) }}</p>
                                            <div class="world-card-meta">
                                                <span>{{ world.room_count }} rooms</span>
                                                <span>{{ formatDate(world.last_played_at) }}</span>
                                            </div>
                                            <button @click="enterWorld(world.id)" class="enter-world-btn">
                                                <i class="fa-solid fa-door-open"></i> ENTER
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-if="errorMessage" class="error">{{ errorMessage }}</div>
                    </div>

                    <div v-else class="panel">
                        <h2>Create New World</h2>
                        <div class="section">
                            <label>World Theme <span class="required">*</span></label>
                            <textarea v-model="worldTheme" placeholder="Describe the world theme... (required, max 200 words)" maxlength="2000"></textarea>
                            <div class="theme-validation">
                                <span v-if="worldTheme.trim().length === 0" class="error-msg">Theme is required</span>
                                <span v-else-if="themeWordCount > 200" class="error-msg">Theme exceeds 200 words</span>
                                <span v-else></span>
                                <span class="word-count" :class="themeValidationClass">{{ themeWordCount }}/200 words</span>
                            </div>
                        </div>
                        <div class="section">
                            <label>Art Style</label>
                            <div class="option-card art-style-card" :class="{ selected: selectedArtStyle === 'retro_anime' }" @click="selectedArtStyle = 'retro_anime'">
                                <img src="/vue/art_samples/retro_anime.jpg" class="art-preview" @error="$event.target.style.display='none'" alt="Retro Anime">
                                <div class="art-style-info">
                                    <strong>Retro Anime</strong>
                                    <span>90s anime style with hand-painted backgrounds and VHS aesthetic</span>
                                </div>
                            </div>
                            <div class="option-card art-style-card" :class="{ selected: selectedArtStyle === 'pixel_art' }" @click="selectedArtStyle = 'pixel_art'">
                                <img src="/vue/art_samples/pixel_art.jpg" class="art-preview" @error="$event.target.style.display='none'" alt="Pixel Art">
                                <div class="art-style-info">
                                    <strong>Pixel Art</strong>
                                    <span>16-bit retro RPG style like classic SNES/Genesis games</span>
                                </div>
                            </div>
                            <div class="option-card art-style-card" :class="{ selected: selectedArtStyle === 'photorealistic' }" @click="selectedArtStyle = 'photorealistic'">
                                <img src="/vue/art_samples/photorealistic.jpg" class="art-preview" @error="$event.target.style.display='none'" alt="Photorealistic">
                                <div class="art-style-info">
                                    <strong>Photorealistic</strong>
                                    <span>Cinematic film look with dramatic lighting and depth</span>
                                </div>
                            </div>
                            <div class="option-card art-style-card" :class="{ selected: selectedArtStyle === 'low_poly' }" @click="selectedArtStyle = 'low_poly'">
                                <img src="/vue/art_samples/low_poly.png" class="art-preview" @error="$event.target.style.display='none'" alt="Low Poly">
                                <div class="art-style-info">
                                    <strong>Low Poly</strong>
                                    <span>Stylized flat-shaded geometric style with clean pastel gradients</span>
                                </div>
                            </div>
                        </div>
                        <div class="section">
                            <label>Labyrinth Size</label>
                            <div class="option-card" :class="{ selected: selectedGridSize === 2 }" @click="selectedGridSize = 2">
                                <strong>Trial</strong> ~4 rooms, 2 treasures
                            </div>
                            <div class="option-card" :class="{ selected: selectedGridSize === 3 }" @click="selectedGridSize = 3">
                                <strong>Normal</strong> ~9 rooms, 3 treasures
                            </div>
                            <div class="option-card" :class="{ selected: selectedGridSize === 4 }" @click="selectedGridSize = 4">
                                <strong>Large</strong> ~16 rooms, 4 treasures
                            </div>
                        </div>
                        <button @click="createNewWorld" :disabled="creatingWorld || !faker || !isThemeValid">
                            {{ creatingWorld ? 'Creating...' : 'Create World' }}
                        </button>
                        <button @click="showCreateForm = false; errorMessage = ''" class="secondary-btn">Back</button>
                        <div v-if="errorMessage" class="error">{{ errorMessage }}</div>
                    </div>
                    
                    <!-- Progress Modal -->
                    <div v-if="showProgressModal" class="progress-modal-overlay">
                        <div class="progress-modal">
                            <h2>🏰 Generating Your World</h2>
                            <div class="progress-step">{{ generationProgress.step }}</div>
                            <div class="progress-bar-container">
                                <div class="progress-bar" :style="{ width: generationProgress.percent + '%' }"></div>
                            </div>
                            <div class="progress-percent">{{ generationProgress.percent }}%</div>
                            <div class="progress-details">
                                <span v-if="generationProgress.totalRooms > 0">
                                    Rooms: {{ generationProgress.generatedRooms }}/{{ generationProgress.totalRooms }}
                                </span>
                            </div>
                            <p class="progress-hint">This may take a few minutes for larger worlds...</p>
                        </div>
                    </div>
                </div>
            </div>
        `
    });
})();

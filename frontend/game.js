/**
 * ARCANE Game — Phaser.js Scene
 *
 * Renders the Tiled town map and character sprites.
 * Polls the API for agent positions and animates movement.
 */

const TILE_SIZE = 32;

// Expose globally so UI can call focusAgent
window.ArcaneGame = {
    focusAgent: null,
};

// Track current agent state for smooth interpolation
let agentSprites = {};    // { agent_id: Phaser.GameObjects.Sprite }
let agentLabels = {};     // { agent_id: Phaser.GameObjects.Text }
let agentEmojis = {};     // { agent_id: Phaser.GameObjects.Text }
let agentTargetPos = {};  // { agent_id: {x, y} }
let currentState = null;

// --- Phaser Scene ---
class ArcaneScene extends Phaser.Scene {
    constructor() {
        super({ key: 'ArcaneScene' });
    }

    preload() {
        // Tileset images
        const mapAssets = '/assets/the_ville/visuals/map_assets/';

        this.load.image('blocks_1', mapAssets + 'blocks/blocks_1.png');
        this.load.image('walls', mapAssets + 'v1/Room_Builder_32x32.png');
        this.load.image('interiors_pt1', mapAssets + 'v1/interiors_pt1.png');
        this.load.image('interiors_pt2', mapAssets + 'v1/interiors_pt2.png');
        this.load.image('interiors_pt3', mapAssets + 'v1/interiors_pt3.png');
        this.load.image('interiors_pt4', mapAssets + 'v1/interiors_pt4.png');
        this.load.image('interiors_pt5', mapAssets + 'v1/interiors_pt5.png');
        this.load.image('CuteRPG_Field_B', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Field_B.png');
        this.load.image('CuteRPG_Field_C', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Field_C.png');
        this.load.image('CuteRPG_Harbor_C', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Harbor_C.png');
        this.load.image('CuteRPG_Village_B', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Village_B.png');
        this.load.image('CuteRPG_Forest_B', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Forest_B.png');
        this.load.image('CuteRPG_Desert_C', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Desert_C.png');
        this.load.image('CuteRPG_Mountains_B', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Mountains_B.png');
        this.load.image('CuteRPG_Lake_B', mapAssets + 'cute_rpg_word_VXAce/tilesets/CuteRPG_Lake_B.png');

        // Tiled map JSON
        this.load.tilemapTiledJSON('map', '/assets/the_ville/visuals/the_ville_jan7.json');

        // Character sprite atlas (shared for all characters - walk animations)
        // Each character PNG is a ~96x128 sprite sheet (3 cols x 4 rows, 32x32 frames)
        // Load profile images for agent portraits on the map
        this.load.setPath('/assets/characters/');

        // We'll load the actual sprites dynamically once we know agent assignments
        // For now, preload all profile images
        const characterNames = [
            'Abigail_Chen', 'Adam_Smith', 'Arthur_Burton', 'Ayesha_Khan',
            'Carlos_Gomez', 'Carmen_Ortiz', 'Eddy_Lin', 'Francisco_Lopez',
            'Giorgio_Rossi', 'Hailey_Johnson', 'Isabella_Rodriguez', 'Jane_Moreno',
            'Jennifer_Moore', 'John_Lin', 'Klaus_Mueller', 'Latoya_Williams',
            'Maria_Lopez', 'Mei_Lin', 'Rajiv_Patel', 'Ryan_Park',
            'Sam_Moore', 'Tamara_Taylor', 'Tom_Moreno', 'Wolfgang_Schulz',
            'Yuriko_Yamamoto'
        ];

        for (const name of characterNames) {
            // Profile image (32x32 face icon)
            this.load.image('profile_' + name, `profile/${name}.png`);
            // Full sprite sheet for walk animations
            this.load.spritesheet('sprite_' + name, `${name}.png`, {
                frameWidth: 32,
                frameHeight: 32,
            });
        }

        // Speech bubble
        this.load.image('speech_bubble', '/assets/speech_bubble/v1.png');
    }

    create() {
        // --- Create tilemap ---
        const map = this.make.tilemap({ key: 'map' });

        // Add tilesets — names must match the Tiled JSON tileset names
        const tilesets = [];

        const addTs = (tiledName, phaserKey) => {
            const ts = map.addTilesetImage(tiledName, phaserKey);
            if (ts) tilesets.push(ts);
            return ts;
        };

        addTs('blocks_1', 'blocks_1');
        const walls = addTs('Room_Builder_32x32', 'walls');
        addTs('interiors_pt1', 'interiors_pt1');
        addTs('interiors_pt2', 'interiors_pt2');
        addTs('interiors_pt3', 'interiors_pt3');
        addTs('interiors_pt4', 'interiors_pt4');
        addTs('interiors_pt5', 'interiors_pt5');
        addTs('CuteRPG_Field_B', 'CuteRPG_Field_B');
        const fieldC = addTs('CuteRPG_Field_C', 'CuteRPG_Field_C');
        addTs('CuteRPG_Harbor_C', 'CuteRPG_Harbor_C');
        addTs('CuteRPG_Village_B', 'CuteRPG_Village_B');
        addTs('CuteRPG_Forest_B', 'CuteRPG_Forest_B');
        addTs('CuteRPG_Desert_C', 'CuteRPG_Desert_C');
        addTs('CuteRPG_Mountains_B', 'CuteRPG_Mountains_B');
        addTs('CuteRPG_Lake_B', 'CuteRPG_Lake_B');

        // Create layers (order matters for rendering depth)
        const layerNames = [
            'Bottom Ground', 'Exterior Ground',
            'Exterior Decoration L1', 'Exterior Decoration L2',
            'Interior Ground', 'Wall',
            'Interior Furniture L1', 'Interior Furniture L2',
            'Foreground L1', 'Foreground L2',
            'Collisions'
        ];

        for (const layerName of layerNames) {
            try {
                const layer = map.createLayer(layerName, tilesets, 0, 0);
                if (layer) {
                    if (layerName.startsWith('Foreground')) {
                        layer.setDepth(2);
                    } else if (layerName === 'Collisions') {
                        layer.setDepth(-1);
                        layer.setVisible(false);
                    }
                }
            } catch (e) {
                console.warn(`Could not create layer "${layerName}":`, e.message);
            }
        }

        // --- Camera setup ---
        const camera = this.cameras.main;
        camera.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
        camera.setZoom(1.5);
        // Start camera at center of map
        camera.scrollX = map.widthInPixels / 2 - camera.width / (2 * camera.zoom);
        camera.scrollY = map.heightInPixels / 2 - camera.height / (2 * camera.zoom);

        // Camera controls: arrow keys to pan
        this.cursors = this.input.keyboard.createCursorKeys();

        // Mouse wheel zoom
        this.input.on('wheel', (pointer, gameObjects, deltaX, deltaY) => {
            const newZoom = camera.zoom - deltaY * 0.001;
            camera.setZoom(Phaser.Math.Clamp(newZoom, 0.5, 4));
        });

        // Middle mouse drag to pan
        this.input.on('pointermove', (pointer) => {
            if (pointer.middleButtonDown()) {
                camera.scrollX -= pointer.velocity.x / camera.zoom * 0.02;
                camera.scrollY -= pointer.velocity.y / camera.zoom * 0.02;
            }
        });

        // Store map ref
        this._map = map;

        // --- Create walk animations for each character ---
        this._createAnimations();

        // --- Connect to API ---
        this._connectAPI();

        // Hide loading
        ArcaneUI.init();
        ArcaneUI.hideLoading();
    }

    _createAnimations() {
        const characters = [
            'Abigail_Chen', 'Adam_Smith', 'Arthur_Burton', 'Ayesha_Khan',
            'Carlos_Gomez', 'Carmen_Ortiz', 'Eddy_Lin', 'Francisco_Lopez',
            'Giorgio_Rossi', 'Hailey_Johnson', 'Isabella_Rodriguez', 'Jane_Moreno',
            'Jennifer_Moore', 'John_Lin', 'Klaus_Mueller', 'Latoya_Williams',
            'Maria_Lopez', 'Mei_Lin', 'Rajiv_Patel', 'Ryan_Park',
            'Sam_Moore', 'Tamara_Taylor', 'Tom_Moreno', 'Wolfgang_Schulz',
            'Yuriko_Yamamoto'
        ];

        // The sprite sheets are 3 cols wide.
        // Row 0: down (frames 0,1,2)
        // Row 1: left (frames 3,4,5)
        // Row 2: right (frames 6,7,8)
        // Row 3: up (frames 9,10,11)
        for (const name of characters) {
            const key = 'sprite_' + name;
            if (!this.textures.exists(key)) continue;

            const dirs = [
                { dir: 'down', start: 0, end: 2, idle: 1 },
                { dir: 'left', start: 3, end: 5, idle: 4 },
                { dir: 'right', start: 6, end: 8, idle: 7 },
                { dir: 'up', start: 9, end: 11, idle: 10 },
            ];

            for (const d of dirs) {
                const animKey = `${name}_${d.dir}`;
                if (!this.anims.exists(animKey)) {
                    this.anims.create({
                        key: animKey,
                        frames: this.anims.generateFrameNumbers(key, {
                            start: d.start, end: d.end
                        }),
                        frameRate: 6,
                        repeat: -1,
                    });
                }
            }
        }
    }

    _connectAPI() {
        // Register callbacks
        ArcaneAPI.onStateUpdate((state) => {
            currentState = state;
            this._updateAgents(state);
            ArcaneUI.updateFromState(state);
        });

        ArcaneAPI.onEventsUpdate((events) => {
            ArcaneUI.updateEventLog(events);
            ArcaneUI.updateMetrics(events);
        });

        ArcaneAPI.onResultsUpdate((results) => {
            ArcaneUI.updateResults(results);
        });

        // Do an initial fetch
        ArcaneAPI.fetchState().then(state => {
            if (state) {
                currentState = state;
                this._updateAgents(state);
                ArcaneUI.updateFromState(state);
            }
        });

        ArcaneAPI.fetchEvents(50).then(events => {
            if (events) {
                ArcaneUI.updateEventLog(events);
                ArcaneUI.updateMetrics(events);
            }
        });

        // Start polling every 800ms
        ArcaneAPI.startPolling(800);
    }

    _updateAgents(state) {
        if (!state || !state.agents) return;

        for (const [id, agent] of Object.entries(state.agents)) {
            const worldX = agent.pos[0] * TILE_SIZE + TILE_SIZE / 2;
            const worldY = agent.pos[1] * TILE_SIZE + TILE_SIZE / 2;

            if (!agentSprites[id]) {
                // Create new sprite
                this._createAgentSprite(id, agent, worldX, worldY);
            } else {
                // Set target for smooth interpolation
                agentTargetPos[id] = { x: worldX, y: worldY };
            }
        }
    }

    _createAgentSprite(id, agent, x, y) {
        const spriteKey = 'sprite_' + agent.sprite;
        const hasSprite = this.textures.exists(spriteKey);

        let sprite;
        if (hasSprite) {
            sprite = this.add.sprite(x, y, spriteKey, 1); // idle down frame
        } else {
            // Fallback: use profile image
            const profileKey = 'profile_' + agent.sprite;
            sprite = this.add.sprite(x, y, profileKey);
        }

        sprite.setDepth(1);
        sprite.setScale(1);

        // Color tint ring indicator
        if (agent.type === 'deviant') {
            // Red glow effect
            sprite.setTint(0xffcccc);
        }

        agentSprites[id] = sprite;
        agentTargetPos[id] = { x, y };

        // Name label
        const label = this.add.text(x, y + 20, agent.name, {
            fontSize: '10px',
            fontFamily: 'Consolas, monospace',
            color: agent.type === 'deviant' ? '#ff6b6b' : '#60a5fa',
            stroke: '#000000',
            strokeThickness: 3,
        });
        label.setOrigin(0.5, 0);
        label.setDepth(3);
        agentLabels[id] = label;

        // Emoji / pronunciatio
        const emoji = this.add.text(x, y - 22, agent.pronunciatio || '💬', {
            fontSize: '16px',
            stroke: '#000000',
            strokeThickness: 2,
        });
        emoji.setOrigin(0.5, 1);
        emoji.setDepth(3);
        agentEmojis[id] = emoji;

        // Make clickable
        sprite.setInteractive();
        sprite.on('pointerdown', () => {
            this._focusOnAgent(id);
        });
    }

    _focusOnAgent(agentId) {
        const sprite = agentSprites[agentId];
        if (!sprite) return;

        this.cameras.main.pan(sprite.x, sprite.y, 500, 'Power2');
    }

    update(time, delta) {
        // Camera movement with arrow keys
        const cam = this.cameras.main;
        const speed = 400 / cam.zoom;

        if (this.cursors.left.isDown) cam.scrollX -= speed * delta / 1000;
        if (this.cursors.right.isDown) cam.scrollX += speed * delta / 1000;
        if (this.cursors.up.isDown) cam.scrollY -= speed * delta / 1000;
        if (this.cursors.down.isDown) cam.scrollY += speed * delta / 1000;

        // Smooth agent movement interpolation
        for (const [id, target] of Object.entries(agentTargetPos)) {
            const sprite = agentSprites[id];
            if (!sprite) continue;

            const dx = target.x - sprite.x;
            const dy = target.y - sprite.y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist > 2) {
                // Lerp toward target
                const lerpSpeed = 0.05;
                sprite.x += dx * lerpSpeed;
                sprite.y += dy * lerpSpeed;

                // Determine direction and play walk animation
                const agent = currentState?.agents?.[id];
                const spriteName = agent?.sprite;
                if (spriteName) {
                    let dir = 'down';
                    if (Math.abs(dx) > Math.abs(dy)) {
                        dir = dx > 0 ? 'right' : 'left';
                    } else {
                        dir = dy > 0 ? 'down' : 'up';
                    }
                    const animKey = `${spriteName}_${dir}`;
                    if (sprite.anims && this.anims.exists(animKey)) {
                        sprite.play(animKey, true);
                    }
                }
            } else {
                // Snap to target and stop animation
                sprite.x = target.x;
                sprite.y = target.y;
                if (sprite.anims) {
                    sprite.anims.stop();
                }
            }

            // Update label and emoji positions
            const label = agentLabels[id];
            if (label) {
                label.x = sprite.x;
                label.y = sprite.y + 20;
            }

            const emoji = agentEmojis[id];
            if (emoji) {
                emoji.x = sprite.x;
                emoji.y = sprite.y - 22;

                // Update emoji text if changed
                const agent = currentState?.agents?.[id];
                if (agent && agent.pronunciatio && emoji.text !== agent.pronunciatio) {
                    emoji.setText(agent.pronunciatio);
                }
            }
        }
    }
}

// --- Expose focus function ---
window.ArcaneGame.focusAgent = (agentId) => {
    const scene = window._arcaneScene;
    if (scene) scene._focusOnAgent(agentId);
};

// --- Launch Phaser ---
const config = {
    type: Phaser.AUTO,
    parent: 'game-container',
    width: window.innerWidth - 380,  // subtract HUD width
    height: window.innerHeight,
    pixelArt: true,
    backgroundColor: '#111122',
    scene: ArcaneScene,
    scale: {
        mode: Phaser.Scale.RESIZE,
        autoCenter: Phaser.Scale.NO_CENTER,
    },
};

const game = new Phaser.Game(config);

// Store scene instance for external access
game.events.on('ready', () => {
    window._arcaneScene = game.scene.getScene('ArcaneScene');
});

// Handle window resize
window.addEventListener('resize', () => {
    const hudWidth = 380;
    game.scale.resize(window.innerWidth - hudWidth, window.innerHeight);
});

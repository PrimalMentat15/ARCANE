/**
 * ARCANE Setup Screen
 *
 * Handles the pre-simulation configuration UI: LLM provider selection,
 * agent roster customization, and simulation launch.
 */

const ArcaneSetup = (() => {
    let _personas = [];
    let _selectedPersonas = new Set();
    let _selectedProvider = 'local';
    let _modelName = '';
    let _localBaseUrl = 'http://localhost:1234/v1';

    /**
     * Initialize the setup screen.
     */
    async function init() {
        const screen = document.getElementById('setup-screen');
        if (!screen) return;

        // Check if model is already initialized (direct mode / page refresh)
        const status = await ArcaneAPI.fetchSetupStatus();
        if (status && status.ready) {
            dismiss();
            return;
        }

        // Load data
        const [personasData, providersData] = await Promise.all([
            ArcaneAPI.fetchPersonas(),
            ArcaneAPI.fetchProviders(),
        ]);

        if (personasData) {
            _personas = personasData.personas;
            renderPersonas();
            // Pre-select the first 3 benign + 1 deviant
            const benign = _personas.filter(p => p.type === 'benign');
            const deviant = _personas.filter(p => p.type === 'deviant');
            benign.slice(0, 2).forEach(p => togglePersona(p.id));
            deviant.slice(0, 1).forEach(p => togglePersona(p.id));
        }

        if (providersData) {
            const providers = providersData.providers;
            const current = providers.find(p => p.current);
            if (current) {
                _selectedProvider = current.id;
                _localBaseUrl = current.base_url || _localBaseUrl;
            }
            renderProviders(providers);
        }

        updateCounter();
        bindEvents();
        screen.style.display = 'flex';
    }

    /**
     * Render the LLM provider selector cards.
     */
    function renderProviders(providers) {
        const container = document.getElementById('setup-providers');
        if (!container) return;

        container.innerHTML = providers.map(p => {
            const isSelected = p.id === _selectedProvider;
            const statusHtml = p.id === 'local'
                ? `<div class="provider-status" id="local-status">
                     <span class="status-dot"></span>
                     <span class="status-text">Click "Test" to check</span>
                   </div>
                   <div class="provider-url-row">
                     <input type="text" id="local-url" class="setup-input" value="${p.base_url || 'http://localhost:1234/v1'}" />
                     <button id="btn-test-connection" class="setup-btn-small">Test</button>
                   </div>`
                : `<div class="provider-status" id="gemini-status">
                     <span class="status-dot ${p.has_key ? 'connected' : 'error'}"></span>
                     <span class="status-text">${p.has_key ? 'API key found in .env' : 'No GEMINI_API_KEY in .env'}</span>
                   </div>`;

            return `
                <div class="provider-card ${isSelected ? 'selected' : ''}" data-provider="${p.id}" id="provider-${p.id}">
                    <div class="provider-card-header">
                        <div class="provider-radio ${isSelected ? 'active' : ''}"></div>
                        <div class="provider-name">${p.name}</div>
                    </div>
                    <div class="provider-desc">${p.description}</div>
                    ${statusHtml}
                    <div class="provider-model-row">
                        <label>Model:</label>
                        <input type="text" class="setup-input provider-model" data-provider="${p.id}"
                               value="${p.default_model}" placeholder="Model name" />
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Render the agent persona grid.
     */
    function renderPersonas() {
        const container = document.getElementById('setup-agents');
        if (!container) return;

        // Sort: deviant first, then benign
        const sorted = [..._personas].sort((a, b) => {
            if (a.type !== b.type) return a.type === 'deviant' ? -1 : 1;
            return a.name.localeCompare(b.name);
        });

        container.innerHTML = sorted.map(p => {
            const isSelected = _selectedPersonas.has(p.id);
            const typeBadge = p.type === 'deviant'
                ? '<span class="setup-type-badge deviant">DEVIANT</span>'
                : '<span class="setup-type-badge benign">BENIGN</span>';
            const coverInfo = p.cover_role
                ? `<div class="persona-cover">Cover: ${p.cover_role}</div>`
                : '';
            const secretsInfo = p.secrets_count
                ? `<span class="persona-secrets">${p.secrets_count} secret${p.secrets_count > 1 ? 's' : ''}</span>`
                : '';

            return `
                <div class="persona-card ${isSelected ? 'selected' : ''} ${p.type}" data-persona="${p.id}">
                    <div class="persona-check">${isSelected ? '✓' : ''}</div>
                    <img class="persona-portrait" src="/assets/characters/profile/${p.sprite}.png"
                         alt="${p.name}" onerror="this.src='/assets/characters/profile/Adam_Smith.png'" />
                    <div class="persona-info">
                        <div class="persona-name-row">
                            <span class="persona-name">${p.name}</span>
                            ${typeBadge}
                        </div>
                        <div class="persona-meta">${p.age} · ${p.occupation}</div>
                        ${coverInfo}
                        <div class="persona-details-row">
                            ${secretsInfo}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Toggle a persona selection.
     */
    function togglePersona(id) {
        if (_selectedPersonas.has(id)) {
            _selectedPersonas.delete(id);
        } else {
            _selectedPersonas.add(id);
        }
        renderPersonas();
        updateCounter();
    }

    /**
     * Update the agent counter display.
     */
    function updateCounter() {
        const el = document.getElementById('agent-counter');
        if (!el) return;

        const selected = _personas.filter(p => _selectedPersonas.has(p.id));
        const benign = selected.filter(p => p.type === 'benign').length;
        const deviant = selected.filter(p => p.type === 'deviant').length;
        el.textContent = `${selected.length} agents selected (${benign} benign, ${deviant} deviant)`;

        // Enable/disable launch button
        const btn = document.getElementById('btn-launch');
        if (btn) {
            const valid = selected.length >= 2 && deviant >= 1 && benign >= 1;
            btn.disabled = !valid;
            btn.title = valid ? '' : 'Select at least 1 deviant and 1 benign agent';
        }
    }

    /**
     * Bind all event listeners.
     */
    function bindEvents() {
        // Provider selection
        document.getElementById('setup-providers')?.addEventListener('click', (e) => {
            const card = e.target.closest('.provider-card');
            if (card) {
                _selectedProvider = card.dataset.provider;
                document.querySelectorAll('.provider-card').forEach(c => {
                    c.classList.toggle('selected', c.dataset.provider === _selectedProvider);
                    c.querySelector('.provider-radio')?.classList.toggle('active', c.dataset.provider === _selectedProvider);
                });
            }
        });

        // Test connection button
        document.getElementById('setup-providers')?.addEventListener('click', async (e) => {
            if (e.target.id === 'btn-test-connection') {
                const urlInput = document.getElementById('local-url');
                const statusEl = document.getElementById('local-status');
                if (!urlInput || !statusEl) return;

                _localBaseUrl = urlInput.value.trim();
                statusEl.innerHTML = '<span class="status-dot testing"></span><span class="status-text">Testing...</span>';

                const result = await ArcaneAPI.testConnection(_localBaseUrl);
                if (result.connected) {
                    const modelList = result.models?.length ? result.models.join(', ') : 'connected';
                    statusEl.innerHTML = `<span class="status-dot connected"></span><span class="status-text">Connected: ${modelList}</span>`;
                    // Auto-fill model name from first model
                    if (result.models?.length) {
                        const modelInput = document.querySelector('.provider-model[data-provider="local"]');
                        if (modelInput) modelInput.value = result.models[0];
                    }
                } else {
                    statusEl.innerHTML = `<span class="status-dot error"></span><span class="status-text">${result.error}</span>`;
                }
            }
        });

        // Persona selection
        document.getElementById('setup-agents')?.addEventListener('click', (e) => {
            const card = e.target.closest('.persona-card');
            if (card) {
                togglePersona(card.dataset.persona);
            }
        });

        // Quick select buttons
        document.getElementById('btn-select-all-benign')?.addEventListener('click', () => {
            _personas.filter(p => p.type === 'benign').forEach(p => {
                if (!_selectedPersonas.has(p.id)) _selectedPersonas.add(p.id);
            });
            renderPersonas();
            updateCounter();
        });

        document.getElementById('btn-select-all-deviant')?.addEventListener('click', () => {
            _personas.filter(p => p.type === 'deviant').forEach(p => {
                if (!_selectedPersonas.has(p.id)) _selectedPersonas.add(p.id);
            });
            renderPersonas();
            updateCounter();
        });

        document.getElementById('btn-clear-all')?.addEventListener('click', () => {
            _selectedPersonas.clear();
            renderPersonas();
            updateCounter();
        });

        // Launch button
        document.getElementById('btn-launch')?.addEventListener('click', launch);
    }

    /**
     * Launch the simulation with selected config.
     */
    async function launch() {
        const btn = document.getElementById('btn-launch');
        const statusEl = document.getElementById('launch-status');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Launching...';
        }
        if (statusEl) statusEl.textContent = '';

        // Get model name from selected provider
        const modelInput = document.querySelector(`.provider-model[data-provider="${_selectedProvider}"]`);
        _modelName = modelInput ? modelInput.value.trim() : '';

        // Build agent roster
        let benignIdx = 1, deviantIdx = 1;
        const agents = _personas
            .filter(p => _selectedPersonas.has(p.id))
            .map(p => {
                const isDeviant = p.type === 'deviant';
                const id = isDeviant
                    ? `agent_deviant_${deviantIdx++}`
                    : `agent_benign_${benignIdx++}`;
                return { persona: p.id, id, starting_location: p.starting_location };
            });

        const config = {
            provider: _selectedProvider,
            model: _modelName,
            agents: agents,
        };

        const result = await ArcaneAPI.launchSimulation(config);

        if (result.error) {
            if (statusEl) statusEl.textContent = `Error: ${result.error}`;
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Launch Simulation';
            }
            return;
        }

        if (statusEl) {
            statusEl.textContent = `Launched! ${result.agents} agents (${result.benign_count} benign, ${result.deviant_count} deviant)`;
        }

        // Dismiss setup screen after short delay
        setTimeout(dismiss, 500);
    }

    /**
     * Dismiss the setup screen and start the simulation view.
     */
    function dismiss() {
        const screen = document.getElementById('setup-screen');
        if (screen) {
            screen.style.opacity = '0';
            setTimeout(() => {
                screen.style.display = 'none';
                // Remove loading overlay if still visible
                const loading = document.getElementById('loading-overlay');
                if (loading) loading.classList.add('hidden');
                // Start the game and polling
                if (typeof ArcaneGame !== 'undefined' && ArcaneGame.init) {
                    ArcaneGame.init();
                }
                if (typeof ArcaneUI !== 'undefined' && ArcaneUI.init) {
                    ArcaneUI.init();
                }
                ArcaneAPI.startPolling(1000);
            }, 400);
        }
    }

    return { init, dismiss };
})();

// Initialize setup on page load
document.addEventListener('DOMContentLoaded', () => {
    ArcaneSetup.init();
});

/**
 * ARCANE API Client
 *
 * Polls the FastAPI backend for simulation state and events.
 * Exposes a simple interface for game.js and ui.js to consume.
 */

const ArcaneAPI = (() => {
    let _lastStep = -1;
    let _pollInterval = null;
    let _onStateUpdate = null;
    let _onEventsUpdate = null;
    let _onResultsUpdate = null;

    /**
     * Fetch current simulation state.
     */
    async function fetchState() {
        try {
            const resp = await fetch('/api/state');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API state fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch recent events.
     */
    async function fetchEvents(n = 50) {
        try {
            const resp = await fetch(`/api/events?n=${n}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API events fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch detailed agent info.
     */
    async function fetchAgents() {
        try {
            const resp = await fetch('/api/agents');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API agents fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch current attack results.
     */
    async function fetchResults() {
        try {
            const resp = await fetch('/api/results');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API results fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch list of past simulation runs.
     */
    async function fetchHistory() {
        try {
            const resp = await fetch('/api/history');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API history fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch results from a past simulation run.
     */
    async function fetchHistoricalResults(runId) {
        try {
            const resp = await fetch(`/api/history/${runId}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API historical results fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch list of conversation pairs.
     */
    async function fetchConversations() {
        try {
            const resp = await fetch('/api/conversations');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API conversations fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch conversation between two agents.
     */
    async function fetchConversation(agent1Id, agent2Id) {
        try {
            const resp = await fetch(`/api/conversations/${agent1Id}/${agent2Id}`);
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API conversation fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch all messages (combined feed).
     */
    async function fetchAllMessages() {
        try {
            const resp = await fetch('/api/conversations/all');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API all messages fetch failed:', e);
            return null;
        }
    }

    /**
     * Start polling for updates.
     */
    function startPolling(intervalMs = 1000) {
        if (_pollInterval) clearInterval(_pollInterval);

        _pollInterval = setInterval(async () => {
            const state = await fetchState();
            if (state && state.step !== _lastStep) {
                _lastStep = state.step;
                if (_onStateUpdate) _onStateUpdate(state);

                // Also fetch events and results when state changes
                const events = await fetchEvents(50);
                if (events && _onEventsUpdate) _onEventsUpdate(events);

                const results = await fetchResults();
                if (results && _onResultsUpdate) _onResultsUpdate(results);
            }
        }, intervalMs);
    }

    /**
     * Register callbacks.
     */
    function onStateUpdate(cb) { _onStateUpdate = cb; }
    function onEventsUpdate(cb) { _onEventsUpdate = cb; }
    function onResultsUpdate(cb) { _onResultsUpdate = cb; }

    /**
     * Fetch setup status (is model initialized?).
     */
    async function fetchSetupStatus() {
        try {
            const resp = await fetch('/api/setup/status');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            return null;
        }
    }

    /**
     * Fetch available personas for setup screen.
     */
    async function fetchPersonas() {
        try {
            const resp = await fetch('/api/setup/personas');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API personas fetch failed:', e);
            return null;
        }
    }

    /**
     * Fetch available LLM providers.
     */
    async function fetchProviders() {
        try {
            const resp = await fetch('/api/setup/providers');
            if (!resp.ok) return null;
            return await resp.json();
        } catch (e) {
            console.warn('API providers fetch failed:', e);
            return null;
        }
    }

    /**
     * Test connection to a local LLM server.
     */
    async function testConnection(baseUrl) {
        try {
            const resp = await fetch('/api/setup/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ base_url: baseUrl }),
            });
            if (!resp.ok) return { connected: false, error: 'Request failed' };
            return await resp.json();
        } catch (e) {
            return { connected: false, error: e.message };
        }
    }

    /**
     * Launch simulation with selected config.
     */
    async function launchSimulation(config) {
        try {
            const resp = await fetch('/api/setup/launch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            if (!resp.ok) return { error: 'Request failed' };
            return await resp.json();
        } catch (e) {
            return { error: e.message };
        }
    }

    return {
        fetchState,
        fetchEvents,
        fetchAgents,
        fetchResults,
        fetchHistory,
        fetchHistoricalResults,
        fetchConversations,
        fetchConversation,
        fetchAllMessages,
        fetchSetupStatus,
        fetchPersonas,
        fetchProviders,
        testConnection,
        launchSimulation,
        startPolling,
        onStateUpdate,
        onEventsUpdate,
        onResultsUpdate,
    };
})();

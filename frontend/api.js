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

    return {
        fetchState,
        fetchEvents,
        fetchAgents,
        fetchResults,
        fetchHistory,
        fetchHistoricalResults,
        startPolling,
        onStateUpdate,
        onEventsUpdate,
        onResultsUpdate,
    };
})();

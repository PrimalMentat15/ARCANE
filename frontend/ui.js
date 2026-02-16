/**
 * ARCANE HUD UI Controller
 * 
 * Manages the sidebar: event log, agent cards, metrics.
 * Gets data from ArcaneAPI callbacks.
 */

const ArcaneUI = (() => {

    function init() {
        _setupTabs();
    }

    // --- Tab switching ---
    function _setupTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
            });
        });
    }

    // --- Step Info ---
    function updateStepInfo(state) {
        const el = document.getElementById('step-info');
        if (state && state.step > 0) {
            el.textContent = `Step ${state.step} • ${state.sim_time}`;
        } else {
            el.textContent = 'Waiting for simulation...';
        }
    }

    // --- Event Log ---
    function updateEventLog(eventsData) {
        const container = document.getElementById('event-log');
        if (!eventsData || !eventsData.events || eventsData.events.length === 0) return;

        let html = '';
        // Show events in reverse chronological order
        const events = eventsData.events.slice().reverse();

        for (const evt of events) {
            const cssClass = 'evt-' + evt.type;
            const ts = evt.timestamp || '';
            const agent = evt.agent ? `[${evt.agent}]` : '';
            const target = evt.target ? ` → ${evt.target}` : '';
            const content = _escapeHtml(evt.content || '');

            html += `<div class="event-entry ${cssClass}">` +
                `<span class="timestamp">${ts}</span>` +
                `${content}` +
                `</div>`;
        }

        container.innerHTML = html;
    }

    // --- Agent Cards ---
    function updateAgentCards(state) {
        const container = document.getElementById('agent-list');
        if (!state || !state.agents) return;

        let html = '';
        const agents = Object.entries(state.agents);

        for (const [id, agent] of agents) {
            const typeClass = agent.type || 'benign';
            const emoji = typeClass === 'deviant' ? '🕵️' : '👤';
            const portraitUrl = `/assets/characters/profile/${agent.sprite}.png`;

            html += `<div class="agent-card ${typeClass}" data-agent-id="${id}">` +
                `  <div class="agent-card-header">` +
                `    <img class="agent-portrait" src="${portraitUrl}" alt="${agent.name}" onerror="this.style.display='none'">` +
                `    <span class="agent-name">${_escapeHtml(agent.name)}</span>` +
                `    <span class="agent-type-badge ${typeClass}">${typeClass}</span>` +
                `  </div>` +
                `  <div class="agent-detail"><strong>Location:</strong> ${_escapeHtml(agent.location || 'unknown')}</div>` +
                `  <div class="agent-detail"><strong>Activity:</strong> ${_escapeHtml(agent.activity || 'idle')}</div>` +
                `  <div class="agent-detail"><strong>Pos:</strong> (${agent.pos[0]}, ${agent.pos[1]})</div>` +
                `</div>`;
        }

        container.innerHTML = html;

        // Click handler to focus camera on agent
        container.querySelectorAll('.agent-card').forEach(card => {
            card.addEventListener('click', () => {
                const agentId = card.dataset.agentId;
                if (window.ArcaneGame && window.ArcaneGame.focusAgent) {
                    window.ArcaneGame.focusAgent(agentId);
                }
            });
        });
    }

    // --- Metrics ---
    function updateMetrics(eventsData) {
        if (!eventsData || !eventsData.events) return;

        const events = eventsData.events;
        let msgCount = 0, revealCount = 0, tacticCount = 0;

        for (const evt of events) {
            if (evt.type === 'message_sent') msgCount++;
            if (evt.type === 'information_revealed') revealCount++;
            if (evt.type === 'tactic_used') tacticCount++;
        }

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };

        setVal('m-messages', msgCount);
        setVal('m-reveals', revealCount);
        setVal('m-tactics', tacticCount);
    }

    function updateFromState(state) {
        updateStepInfo(state);
        updateAgentCards(state);

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val;
        };
        setVal('m-step', state.step);
        setVal('m-time', state.sim_time || '—');
    }

    // --- Helpers ---
    function _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function hideLoading() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) overlay.classList.add('hidden');
    }

    return {
        init,
        updateFromState,
        updateEventLog,
        updateMetrics,
        hideLoading,
    };
})();

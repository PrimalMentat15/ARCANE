/**
 * ARCANE HUD UI Controller
 *
 * Manages the sidebar: event log, agent cards, metrics, results, history, chats.
 * Gets data from ArcaneAPI callbacks.
 */

const ArcaneUI = (() => {

    let _historyLoaded = false;
    let _chatsLoaded = false;

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

                if (btn.dataset.tab === 'history' && !_historyLoaded) {
                    loadHistoryList();
                    _historyLoaded = true;
                }

                if (btn.dataset.tab === 'chats' && !_chatsLoaded) {
                    loadConversationList();
                    _chatsLoaded = true;
                }
            });
        });
    }

    // --- Step Info ---
    function updateStepInfo(state) {
        const el = document.getElementById('step-info');
        if (state && state.step > 0) {
            el.textContent = `Step ${state.step} \u2022 ${state.sim_time}`;
        } else {
            el.textContent = 'Waiting for simulation...';
        }
    }

    // --- Event Log ---
    function updateEventLog(eventsData) {
        const container = document.getElementById('event-log');
        if (!eventsData || !eventsData.events || eventsData.events.length === 0) return;

        let html = '';
        const events = eventsData.events.slice().reverse();

        for (const evt of events) {
            const cssClass = 'evt-' + evt.type;
            const ts = evt.timestamp || '';
            const content = _escapeHtml(evt.content || '');

            html += `<div class="event-entry ${cssClass}">` +
                `<span class="timestamp">${ts}</span>` +
                `${content}` +
                `</div>`;
        }

        container.innerHTML = html;

        // Refresh chats list on new events if tab is open
        if (_chatsLoaded) {
            loadConversationList();
        }
    }

    // --- Agent Cards ---
    function updateAgentCards(state) {
        const container = document.getElementById('agent-list');
        if (!state || !state.agents) return;

        let html = '';
        const agents = Object.entries(state.agents);

        for (const [id, agent] of agents) {
            const typeClass = agent.type || 'benign';
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
        setVal('m-time', state.sim_time || '\u2014');
    }

    // --- Conversation List ---
    async function loadConversationList() {
        const container = document.getElementById('convo-list');
        const data = await ArcaneAPI.fetchConversations();

        if (!data || !data.conversations || data.conversations.length === 0) {
            container.innerHTML = '<div class="chat-empty">No conversations yet. Run the simulation first.</div>';
            return;
        }

        let html = `<div class="convo-all-btn" id="convo-all-btn"><span>\uD83D\uDCAC</span><span>All Messages</span></div>`;

        for (const convo of data.conversations) {
            const a1 = convo.agents[0];
            const a2 = convo.agents[1];
            const avatar1 = `/assets/characters/profile/${a1.sprite}.png`;
            const avatar2 = `/assets/characters/profile/${a2.sprite}.png`;

            html += `<div class="convo-entry" data-agent1="${a1.id}" data-agent2="${a2.id}">` +
                `<div class="convo-avatars">` +
                `  <img class="convo-avatar" src="${avatar1}" alt="" onerror="this.style.display='none'">` +
                `  <img class="convo-avatar" src="${avatar2}" alt="" onerror="this.style.display='none'">` +
                `</div>` +
                `<div class="convo-info">` +
                `  <div class="convo-names">${_escapeHtml(a1.name)} \u2194 ${_escapeHtml(a2.name)}</div>` +
                `  <div class="convo-meta">Last active: step ${convo.last_step}</div>` +
                `</div>` +
                `<span class="convo-count">${convo.message_count}</span>` +
                `</div>`;
        }

        container.innerHTML = html;

        document.getElementById('convo-all-btn')?.addEventListener('click', () => {
            _setActiveConvo(null);
            loadAllMessages();
        });

        container.querySelectorAll('.convo-entry').forEach(entry => {
            entry.addEventListener('click', () => {
                _setActiveConvo(entry);
                loadConversation(entry.dataset.agent1, entry.dataset.agent2);
            });
        });
    }

    function _setActiveConvo(activeEntry) {
        document.querySelectorAll('.convo-entry').forEach(e => e.classList.remove('active'));
        const allBtn = document.getElementById('convo-all-btn');
        if (allBtn) allBtn.classList.remove('active');

        if (activeEntry === null) {
            if (allBtn) allBtn.classList.add('active');
        } else {
            activeEntry.classList.add('active');
        }
    }

    // --- Chat Messages (pair view) ---
    async function loadConversation(agent1Id, agent2Id) {
        const container = document.getElementById('chat-messages');
        container.innerHTML = '<div class="chat-empty">Loading...</div>';

        const data = await ArcaneAPI.fetchConversation(agent1Id, agent2Id);
        if (!data || !data.messages || data.messages.length === 0) {
            container.innerHTML = '<div class="chat-empty">No messages between these agents yet.</div>';
            return;
        }

        container.innerHTML = _renderChatBubbles(data.messages, agent1Id);
        container.scrollTop = container.scrollHeight;
    }

    // --- All Messages (combined feed) ---
    async function loadAllMessages() {
        const container = document.getElementById('chat-messages');
        container.innerHTML = '<div class="chat-empty">Loading...</div>';

        const data = await ArcaneAPI.fetchAllMessages();
        if (!data || !data.messages || data.messages.length === 0) {
            container.innerHTML = '<div class="chat-empty">No messages yet. Run the simulation first.</div>';
            return;
        }

        container.innerHTML = _renderChatBubbles(data.messages, null);
        container.scrollTop = container.scrollHeight;
    }

    function _renderChatBubbles(messages, perspectiveAgentId) {
        let html = '';

        for (const msg of messages) {
            // Pair view: agent1 = right (sent), other = left (received)
            // Global view: deviant = right, benign = left
            let alignment;
            if (perspectiveAgentId) {
                alignment = msg.sender_id === perspectiveAgentId ? 'sent' : 'received';
            } else {
                alignment = msg.sender_type === 'deviant' ? 'sent' : 'received';
            }

            const isDeviant = msg.sender_type === 'deviant';
            const deviantClass = isDeviant ? 'deviant-sender' : '';
            const nameClass = isDeviant ? 'deviant' : 'benign';
            const avatarUrl = `/assets/characters/profile/${msg.sender_sprite}.png`;
            const senderName = _escapeHtml(msg.sender_name || msg.sender_id);
            const targetName = msg.target_name ? ` \u2192 ${_escapeHtml(msg.target_name)}` : '';
            const content = _escapeHtml(msg.content || '');

            html += `<div class="chat-bubble ${alignment} ${deviantClass}">` +
                `<div class="chat-bubble-header">` +
                `  <img class="chat-bubble-avatar" src="${avatarUrl}" alt="" onerror="this.style.display='none'">` +
                `  <span class="chat-bubble-name ${nameClass}">${senderName}${targetName}</span>` +
                `</div>` +
                `<div class="chat-bubble-content">${content}</div>` +
                `<div class="chat-bubble-footer">` +
                `  <span class="chat-bubble-time">${_escapeHtml(msg.timestamp || '')}</span>` +
                (msg.channel ? `  <span class="chat-channel-badge">${_escapeHtml(msg.channel)}</span>` : '') +
                `  <span class="chat-step-badge">step ${msg.step}</span>` +
                `</div>` +
                `</div>`;
        }

        return html;
    }

    // --- Results Panel ---
    function updateResults(data) {
        const container = document.getElementById('results-panel');
        if (!data || data.error) {
            container.innerHTML = '<div style="color: #555; padding: 20px; text-align: center;">Run simulation to see results...</div>';
            return;
        }
        container.innerHTML = _renderResultsHTML(data);
    }

    function _renderResultsHTML(data) {
        let html = '';

        if (data.deviant_name) {
            html += `<div class="results-header">` +
                `<div class="attacker-name">${_escapeHtml(data.deviant_name)}</div>` +
                `<div class="run-info">${_escapeHtml(data.deviant_id)} | Step ${data.total_steps} | ${_escapeHtml(data.sim_time || '')}</div>` +
                `</div>`;
        }

        const targets = data.targets || [];
        for (const t of targets) {
            const trustPct = Math.round((t.trust_level || 0) * 100);
            let trustColor = '#3498db';
            if (trustPct > 60) trustColor = '#ff6600';
            if (trustPct > 80) trustColor = '#ff0000';

            html += `<div class="target-card">`;
            html += `<div class="target-card-header">`;
            html += `<span class="target-name">${_escapeHtml(t.target_name)}</span>`;
            html += `<span class="phase-badge">Phase ${t.current_phase}/5</span>`;
            html += `</div>`;
            html += `<div class="target-stat"><strong>Trust:</strong> ${(t.trust_level || 0).toFixed(2)}</div>`;
            html += `<div class="trust-bar"><div class="trust-bar-fill" style="width:${trustPct}%;background:${trustColor}"></div></div>`;
            html += `<div class="target-stat"><strong>Messages:</strong> ${t.messages_sent} sent, ${t.messages_received} received</div>`;

            if (t.channels_used && t.channels_used.length > 0) {
                html += `<div class="target-stat"><strong>Channels:</strong> `;
                for (const ch of t.channels_used) {
                    html += `<span class="channel-badge">${_escapeHtml(ch)}</span>`;
                }
                html += `</div>`;
            }

            if (t.tactics_used && t.tactics_used.length > 0) {
                const tacticCounts = {};
                for (const tc of t.tactics_used) {
                    const name = tc.tactic || 'unknown';
                    tacticCounts[name] = (tacticCounts[name] || 0) + 1;
                }
                html += `<div class="target-stat"><strong>Tactics:</strong> `;
                for (const [name, count] of Object.entries(tacticCounts)) {
                    html += `<span class="tactic-badge">${_escapeHtml(name)} x${count}</span>`;
                }
                html += `</div>`;
            }

            if (t.info_extracted && t.info_extracted.length > 0) {
                html += `<div class="target-stat" style="margin-top:6px"><strong>Extracted Info:</strong></div>`;
                for (const item of t.info_extracted) {
                    const sensClass = item.sensitivity === 'high' ? 'high' : '';
                    const valueHtml = item.value
                        ? `<div class="extracted-value">${_escapeHtml(item.value)}</div>`
                        : '';
                    html += `<div class="extracted-item ${sensClass}">` +
                        `${_escapeHtml(item.info_type)} (${_escapeHtml(item.sensitivity)}) ` +
                        `-- via ${_escapeHtml(item.channel || '?')} at step ${item.step}` +
                        valueHtml + `</div>`;
                }
            } else {
                html += `<div class="target-stat" style="color:#555"><strong>Extracted:</strong> None yet</div>`;
            }

            html += `</div>`;
        }

        html += `<div class="results-summary">`;
        html += `<div class="target-stat"><strong>Total:</strong> ${data.total_messages} messages | ${data.total_reveals} reveals | ${data.total_tactics} tactics</div>`;
        if (data.attack_success) {
            html += `<div class="status-success" style="margin-top:6px">ATTACK SUCCESSFUL -- high-sensitivity info obtained</div>`;
        } else {
            html += `<div class="status-pending" style="margin-top:6px">Attack in progress -- no high-sensitivity info yet</div>`;
        }
        html += `</div>`;

        return html;
    }

    // --- History Panel ---
    async function loadHistoryList() {
        const container = document.getElementById('history-panel');
        container.innerHTML = '<div style="color:#555;padding:20px;text-align:center">Loading...</div>';

        const data = await ArcaneAPI.fetchHistory();
        if (!data || !data.runs || data.runs.length === 0) {
            container.innerHTML = '<div style="color:#555;padding:20px;text-align:center">No past runs found.</div>';
            return;
        }

        let html = '';
        for (const run of data.runs) {
            const revealText = run.reveals > 0
                ? `<span class="reveal-count">${run.reveals} reveals</span>`
                : '0 reveals';

            html += `<div class="history-entry" data-run-id="${_escapeHtml(run.run_id)}">` +
                `<div class="run-id">${_escapeHtml(run.run_id)}</div>` +
                `<div class="run-meta">${_escapeHtml(run.date)} | ${run.steps} steps | ${revealText} | ${run.size_kb}KB</div>` +
                `</div>`;
        }

        container.innerHTML = html;

        container.querySelectorAll('.history-entry').forEach(entry => {
            entry.addEventListener('click', () => {
                loadHistoricalRun(entry.dataset.runId);
            });
        });
    }

    async function loadHistoricalRun(runId) {
        const container = document.getElementById('history-panel');
        container.innerHTML = '<div style="color:#555;padding:20px;text-align:center">Loading run...</div>';

        const data = await ArcaneAPI.fetchHistoricalResults(runId);
        if (!data || data.error) {
            container.innerHTML = `<div style="color:#ff4444;padding:20px;text-align:center">Error: ${_escapeHtml(data?.error || 'Failed to load')}</div>`;
            return;
        }

        let html = `<button class="history-back-btn" onclick="ArcaneUI.loadHistoryList()">&larr; Back to list</button>`;
        html += _renderResultsHTML(data);
        container.innerHTML = html;
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
        updateResults,
        loadConversationList,
        loadConversation,
        loadAllMessages,
        loadHistoryList,
        loadHistoricalRun,
        hideLoading,
    };
})();

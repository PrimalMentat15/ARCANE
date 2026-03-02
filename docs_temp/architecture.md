# Architecture: ARCANE v1.0.0

## Overview

ARCANE is structured in four logical layers that communicate through well-defined interfaces:

```
+--------------------+
|   Frontend (Viz)   |  Phaser.js pixel art world + HUD sidebar
+--------------------+
         |  REST (polling)
+--------------------+
|  Server / Runner   |  FastAPI + REPL CLI orchestrator
+--------------------+
         |
+--------------------+
|   Core Engine      |  Agents + Memory + Channels + Research
+--------------------+
         |
+--------------------+
|   LLM Layer        |  Gemini / OpenRouter / Local provider abstraction
+--------------------+
```

### Directory Mapping

```
backend/
  agents/       → Agent cognition (base, benign, deviant) + persona YAML
  channels/     → Communication channels (SMS, email, DM, router)
  config/       → Global settings (settings.yaml)
  llms/         → LLM provider abstraction layer
  memory/       → Memory stream module
  research/     → Event logger + results analyzer
  scenarios/    → Scenario YAML definitions
  model.py      → Mesa model orchestrator
  server.py     → FastAPI server
frontend/       → Phaser.js client (index.html, game.js, ui.js, api.js, assets/)
storage/        → JSONL event logs per run
```

---

## Core Engine

### Agent Cognition Loop

Each simulation step, every agent runs the following loop (adapted from Park et al. 2023):

```
1. PERCEIVE
   - Read world state (who is nearby, what locations are visible)
   - Check incoming messages from all channels (SMS inbox, email, DMs)
   - Deliver any pending async messages (delayed SMS/email/DM)

2. RETRIEVE
   - Query memory stream for relevant past experiences
   - Score by: recency + importance (LLM-rated 1-10) + relevance

3. REFLECT (periodic — every N steps, configurable)
   - Synthesize recent memories into higher-level insights
   - Update beliefs about other agents (trust, suspicion, etc.)

4. PLAN
   - For benign agents: update daily schedule, decide next action
   - For deviant agents: evaluate goal tree progress, select next tactic, choose channel

5. ACT
   - Execute chosen action (move to location, speak, send message)
   - Write outcome to memory stream
   - Log event via EventLogger (JSONL + console)
```

Implementation: `backend/agents/base_agent.py` (shared loop), `backend/agents/benign_agent.py` (victim logic), `backend/agents/deviant_agent.py` (attacker logic).

### Deviant Agent Goal Tree

The goal tree is a key addition over the original Generative Agents architecture. Based on the ScamAgents paper, deviant agents decompose their objective hierarchically:

```
OBJECTIVE: Extract [target_info] from [victim_agent]
|
+-- PHASE 1: Establish contact + build initial rapport
|   |-- sub-goal: Send first message (social DM or email)
|   |-- sub-goal: Establish cover persona credibility
|   `-- sub-goal: Find common ground / shared interest
|
+-- PHASE 2: Deepen relationship
|   |-- sub-goal: Reference details from victim's profile
|   |-- sub-goal: Provide value / offer (fake job, opportunity, help)
|   `-- sub-goal: Gauge victim personality (probe responses)
|
+-- PHASE 3: Apply pressure tactic (chosen based on victim Big Five profile)
|   |-- tactic_urgency: time-sensitive offer / deadline
|   |-- tactic_authority: invoke authority figure or institution
|   |-- tactic_reciprocity: "I helped you, now I need your info to proceed"
|   `-- tactic_fear: warn of consequence if not acted on
|
+-- PHASE 4: Information extraction
|   |-- sub-goal: Make direct ask framed within cover story
|   |-- sub-goal: If resistance — backtrack to Phase 2, try different tactic
|   `-- sub-goal: Record any information obtained
|
`-- PHASE 5: Maintain cover / disengage
    |-- sub-goal: Follow up naturally to avoid suspicion
    `-- sub-goal: Disengage gracefully once objective met
```

The SE Tactic Selector picks tactics from the library based on the target's Big Five personality profile (e.g., high neuroticism → urgency/fear, high agreeableness → reciprocity). A pacing system enforces cooldown timers, unanswered-message limits, and multi-channel rotation.

Phase advancement uses LLM self-evaluation: after each exchange, the agent assesses whether the current phase goal was met, then selects the next sub-goal.

Implementation: `backend/agents/deviant_agent.py` — `_select_tactic()`, `_evaluate_phase()`, `record_info_extracted()`.

### Information Reveal Detection

When a benign agent responds to a message, its response text is scanned for keyword matches against its secret list (defined in persona YAML). If a match is found:

1. The benign agent records it in `revealed_info` with the secret type, sensitivity level, channel, step, and the actual value
2. The deviant agent is notified via `record_info_extracted()` with all fields including the value
3. The event logger writes an `INFORMATION_REVEALED` event with the value in metadata
4. The results analyzer surfaces this in both CLI reports and dashboard

Implementation: `backend/agents/benign_agent.py` — `_check_information_reveal()`.

### Memory Stream

Stored as a list of memory objects in `backend/memory/memory_stream.py`:

```python
@dataclass
class Memory:
    id: str
    timestamp: int           # simulation step
    agent_id: str
    content: str             # natural language description
    memory_type: str         # "observation" | "reflection" | "plan"
    importance: float        # LLM-rated 1-10, normalized
    embedding: list[float]   # for semantic retrieval (placeholder)
    last_accessed: int       # for recency scoring
```

Retrieval score = alpha * recency + beta * importance + gamma * relevance

All three weights are configurable in `backend/config/settings.yaml` under `memory.retrieval_weights`.

---

## Channel System

The channel abstraction allows any agent to communicate through any medium. The **channel adds context to the LLM prompt** — a deviant agent speaking via SMS gets a different prompt framing than one speaking face-to-face.

```python
class BaseChannel:
    def send(self, sender, recipient, content, step, **kwargs) -> Message
    def deliver_pending(self, current_step) -> list[Message]
    def get_prompt_context(self, agent, other) -> str
```

Each channel has a configurable delivery delay (steps before the message arrives):

| Channel | Default Delay | Prompt Context |
|---------|--------------|----------------|
| Proximity (face-to-face) | 0 (instant) | "You are speaking in person with [name] at [location]." |
| SMS | 1 step | "You are texting [name] via SMS. Keep messages brief." |
| Email | 2 steps | "You are emailing [name]. You can write a longer message." |
| Social DM | 1 step | "You are sending a DM to [name] on a social platform." |

The `ChannelRouter` (`backend/channels/router.py`) routes messages through the appropriate channel, manages delivery timing, pushes delivered messages to the recipient's `Smartphone` inbox, and logs all events.

Implementation: `backend/channels/base_channel.py` (channel classes), `backend/channels/smartphone.py` (per-agent inbox), `backend/channels/router.py` (routing hub).

---

## Conversation Tracking

The `EventLogger` provides conversation-level querying on top of the raw event stream:

- **`get_conversation_between(agent1_id, agent2_id)`** — Returns all `MESSAGE_SENT` events between two specific agents, chronologically.
- **`get_all_conversations()`** — Scans all message events and returns a list of unique agent pairs that have exchanged messages, with message counts and the last step number.

These methods power the Chats tab in the frontend and the `/api/conversations` endpoints.

---

## LLM Provider Layer

All agent reasoning goes through the provider abstraction. This makes swapping models trivial.

```python
class BaseProvider:
    async def complete(self, system_prompt: str, messages: list[dict],
                       temperature: float, max_tokens: int) -> str
    def complete_sync(self, ...) -> str       # sync variant (Gemini + Local)
    async def embed(self, text: str) -> list[float]
```

Per-agent-type model assignment is configured in `backend/config/settings.yaml`:

```yaml
llm:
  benign_agents:
    provider: local                            # or "gemini" / "openrouter"
    model: meta-llama-3.1-8b-instruct
  deviant_agents:
    provider: local
    model: meta-llama-3.1-8b-instruct
  reflection:
    provider: local
    model: meta-llama-3.1-8b-instruct

# Local LLM server configuration (LM Studio / Ollama / vLLM)
local_llm:
  base_url: http://localhost:1234/v1
  timeout: 120
```

### Supported Providers

| Provider | SDK | Notes |
|----------|-----|-------|
| **Gemini** | `google-genai` | Cloud provider. Supports sync + async completions and embeddings. |
| **OpenRouter** | `httpx` | Cloud access to free/open-source models (LLaMA, Mistral, Qwen, etc.). Async only. Retry logic for free-tier rate limits. |
| **Local** | `httpx` | Any OpenAI-compatible local server (LM Studio, Ollama, vLLM). Supports sync + async. No API key needed. |

Implementation: `backend/llms/base_provider.py`, `backend/llms/gemini_provider.py`, `backend/llms/openrouter_provider.py`, `backend/llms/local_provider.py`.

### Prompt Construction

`backend/llms/prompt_builder.py` assembles the system prompt from:

1. Persona card (identity, backstory, communication style)
2. Big Five personality trait injections (natural language)
3. Memory context (recent memories, reflections)
4. Channel-specific framing
5. Relationship context
6. Current situation / activity
7. Response guidelines

---

## Persona and Big Five Traits

Each agent loads a YAML persona file at startup from `backend/agents/personas/benign/` or `backend/agents/personas/deviant/`. The Big Five scores are injected into the system prompt using natural language:

| Trait | High Score Prompt Injection | Low Score Prompt Injection |
|-------|---------------------------|---------------------------|
| Openness | "You are curious and open to new ideas and people." | "You prefer familiar routines and are cautious about novelty." |
| Conscientiousness | "You are careful, organized, and think before acting." | "You are spontaneous and sometimes act without thinking things through." |
| Extraversion | "You enjoy talking and meeting new people." | "You are reserved and prefer not to share too much." |
| Agreeableness | "You are trusting and find it hard to say no to people." | "You are skeptical and push back when something feels off." |
| Neuroticism | "You are sensitive to stress and urgency makes you act quickly." | "You are emotionally stable and not easily pressured." |

These descriptions are composed and injected into the `[PERSONALITY]` block of every agent system prompt.

Implementation: `backend/agents/personas/loader.py`, `backend/llms/prompt_builder.py` — `build_personality_block()`.

---

## Research Logging

### EventLogger

The `EventLogger` (`backend/research/event_logger.py`) is the central logging system. Every simulation event is written to:

1. An in-memory buffer (for the live dashboard event feed)
2. A JSONL file on disk (`storage/logs/run_YYYYMMDD_HHMMSS.jsonl`)
3. Console output via Python logging

Every event is a `SimEvent` dataclass:

```python
@dataclass
class SimEvent:
    step: int
    event_type: EventType      # one of 16 types
    timestamp: str             # in-simulation time
    agent_id: str | None
    target_id: str | None
    channel: str | None
    location: str | None
    content: str | None
    metadata: dict             # event-specific data
```

### Event Types (16)

| Category | Event Types |
|----------|-------------|
| Agent actions | `agent_move`, `agent_perceive`, `agent_plan`, `agent_reflect` |
| Communication | `message_sent`, `message_received`, `conversation_start`, `conversation_end` |
| Social engineering | `tactic_used`, `goal_phase_change`, `information_revealed`, `trust_change` |
| System | `step_start`, `step_end`, `simulation_start`, `simulation_end` |

### Example JSONL entries

```json
{"step": 5, "event_type": "message_sent", "timestamp": "Day 1 09:40", "agent_id": "agent_deviant_1", "target_id": "agent_benign_1", "channel": "social_dm", "content": "Hi Sarah! I'm Marcus from InnovateCorp...", "metadata": {"delivered": true}}
```

```json
{"step": 12, "event_type": "information_revealed", "timestamp": "Day 1 13:40", "agent_id": "agent_benign_1", "target_id": "agent_deviant_1", "channel": "email", "content": "INFORMATION REVEALED (high): financial = I have about $45,000 in my savings account", "metadata": {"info_type": "financial", "sensitivity": "high", "value": "I have about $45,000 in my savings account"}}
```

### Results Analyzer

The `ResultsAnalyzer` (`backend/research/results_analyzer.py`) processes event logs into structured attack progress reports. It supports two modes:

- **`analyze_live(model)`** — builds results from the live running model's event buffer
- **`analyze_file(log_path)`** — builds results from a JSONL log file on disk

Results include per-target: messages sent/received, tactics used, channels exploited, current phase, trust level, and extracted information with actual secret values.

Used by both the CLI (`results`, `review` commands) and the API (`/api/results`, `/api/history/{run_id}` endpoints).

---

## Server Architecture

### FastAPI Backend (`backend/server.py`)

A single FastAPI application serves both the static frontend files and the REST API. It is started in a background thread by `run.py`.

**Static file mounts:**
- `/` — serves `frontend/index.html`
- `/assets/` — serves `frontend/assets/` (sprites, tilesets, maps)
- Frontend JS files served from `frontend/`

**API endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/state` | GET | Current simulation state (step, time, agent positions) |
| `/api/events?n=50` | GET | Last N events from the event buffer |
| `/api/agents` | GET | Detailed agent info (type, location, activity, sprite) |
| `/api/results` | GET | Live attack progress report |
| `/api/history` | GET | List of past simulation run log files |
| `/api/history/{run_id}` | GET | Results from a specific past run |
| `/api/conversations` | GET | List of agent pairs that have exchanged messages, with counts |
| `/api/conversations/all` | GET | All messages across all agents (combined feed) |
| `/api/conversations/{agent1_id}/{agent2_id}` | GET | Full message thread between two specific agents |

### Terminal CLI (`run.py`)

The interactive REPL provides direct simulation control:

| Command | Description |
|---------|-------------|
| `run <N>` | Execute N steps with per-step progress |
| `status` | Step count, sim time, message/reveal/tactic totals |
| `agents` | List agents with type, location, activity |
| `log [N]` | Show last N events |
| `results` | Full attack progress report |
| `history` | List past runs |
| `review <id>` | View results from a past run |
| `help` / `quit` | Help / exit |

Headless mode: `python run.py --headless --steps 50 --no-server`

---

## Simulation Orchestrator (`backend/model.py`)

The `ArcaneModel` extends Mesa's `Model` class and orchestrates each simulation step:

1. Load config from `backend/config/settings.yaml`
2. Load persona YAML files and instantiate agents (benign + deviant)
3. Initialize LLM providers per agent type
4. Create the `ChannelRouter` with configured delivery delays
5. Create the `EventLogger` writing to `storage/logs/`

**Each `model.step()` call:**
1. Advance simulation time
2. Deliver pending async messages via `ChannelRouter.deliver_pending()`
3. Each agent runs its cognition loop (perceive → retrieve → reflect → plan → act)
4. Log step start/end events

The model exposes `agents_by_id` (dict), `step_count`, `sim_time_str`, `event_logger`, and `channel_router` for the server and CLI to query.

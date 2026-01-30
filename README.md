# ARCANE - Agentic Replication of Cyberfraud and Adversarial Narrative Environments

A simulation framework for studying social engineering and cyber fraud behavior in multi-agent environments. Built on ideas from Generative Agents (Park et al., 2023), SE-VSim (Kumarage et al., 2025), and ScamAgents (Badhe, 2025). This is a proof-of-concept framework developed to explore how AI agents with distinct personas and goals interact in a simulated social environment, specifically focusing on social engineering dynamics between deviant and benign/naive agents.

---

## What This Is

ARCANE is a sandbox simulation where:

- **Deviant agents** try to manipulate and extract personal information from other agents using realistic social engineering tactics
- **Benign/naive agents** live their daily routines, each with distinct personality traits based on the Big Five model (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
- Agents interact **face-to-face** in a pixel art world AND **remotely** via simulated SMS, email, and social DMs (every agent has a virtual smartphone)
- All interactions are logged for research analysis: success rates, information revealed, influence tactics used, personality effects

The visual layer takes inspiration from the original Generative Agents pixel art sandbox (Smallville). The agent cognition is heavily reworked to add goal-driven deception, multi-channel communication, and social engineering mechanics grounded in the research literature.

---

## Key Features

- Pixel art world rendered with Phaser.js -- agents move between locations (home, cafe, office, park, etc.)
- Dual communication layer: proximity-based face-to-face chat AND asynchronous remote channels (SMS/email/social DM)
- Agent memory stream with reflection and planning (from Generative Agents architecture)
- Deviant agent goal decomposition tree: high-level objective broken into incremental, trust-building sub-goals
- Big Five personality trait modeling for all agents; traits directly influence susceptibility and conversation style
- LLM provider abstraction: supports OpenRouter (free/open models like Mistral, LLaMA, Qwen) and direct API keys (Gemini, OpenAI)
- Scenario YAML files: define agent rosters, initial states, and objectives without writing code
- Research dashboard with live metrics and post-simulation CSV export

---

## Project Structure

```
social-eng-sim/
|
|-- core/                        # Core agent cognition engine
|   |-- agents/
|   |   |-- base_agent.py        # Abstract agent: memory + planning + channel access
|   |   |-- benign_agent.py      # Naive/victim agent with Big Five traits
|   |   |-- deviant_agent.py     # Attacker agent with goal tree + deception layer
|   |   `-- persona.py           # Persona definitions (traits, backstory, secrets)
|   |-- memory/
|   |   |-- memory_stream.py     # Long-term episodic memory store
|   |   |-- reflection.py        # Periodic memory synthesis into insights
|   |   `-- retrieval.py         # Score-based memory retrieval (recency + relevance + importance)
|   |-- planning/
|   |   |-- daily_planner.py     # Generates daily schedules for benign agents
|   |   |-- goal_tree.py         # Hierarchical goal nodes for deviant agents
|   |   `-- se_tactics.py        # Social engineering tactic library (trust building, urgency, etc.)
|   `-- world/
|       |-- environment.py       # Locations, adjacency graph, object states
|       `-- clock.py             # Simulation time steps
|
|-- channels/                    # Multi-channel communication system
|   |-- base_channel.py          # Abstract channel interface
|   |-- proximity_chat.py        # Face-to-face in-world conversations
|   |-- sms_channel.py           # SMS simulation (asynchronous, short text)
|   |-- email_channel.py         # Email simulation (longer form, attachments as text)
|   `-- social_dm.py             # Social media DM (platform context added to prompt)
|
|-- llm/                         # LLM provider abstraction layer
|   |-- base_provider.py         # Abstract provider interface
|   |-- openrouter_provider.py   # OpenRouter API (primary: free/OSS models)
|   |-- gemini_provider.py       # Google Gemini API
|   |-- openai_provider.py       # OpenAI API (optional fallback)
|   `-- prompt_builder.py        # Builds agent prompts from memory + context + persona
|
|-- viz/                         # Visual layer
|   |-- world_renderer.py        # Phaser.js pixel art world (backend data feed)
|   |-- chat_overlay.py          # Renders chat bubbles over agents
|   `-- dashboard.py             # Research metrics panel (live + export)
|
|-- scenarios/                   # Scenario definitions
|   |-- base_scenario.py         # Scenario loader and validator
|   `-- examples/
|       |-- basic_poc.yaml       # The first PoC: 2 deviant, 4 naive agents
|       |-- recruitment_scam.yaml
|       `-- romance_scam.yaml
|
|-- research/                    # Analysis and logging tools
|   |-- event_logger.py          # Structured event log for every interaction
|   |-- metrics.py               # Computes SE success rate, info revealed, etc.
|   `-- analyzer.py              # Post-simulation report generator
|
|-- config/
|   |-- settings.yaml            # Global settings (LLM provider, step speed, etc.)
|   `-- personas/                # Example persona YAML templates
|       |-- deviant_recruiter.yaml
|       |-- naive_high_agreeableness.yaml
|       `-- naive_low_neuroticism.yaml
|
|-- frontend/                    # Phaser.js web client
|   |-- index.html
|   |-- src/
|   |   |-- scenes/
|   |   |   |-- WorldScene.js    # Main pixel art world
|   |   |   `-- DashboardScene.js
|   |   |-- sprites/             # (Placeholder notes for pixel art assets)
|   |   `-- api.js               # Fetches simulation state from backend
|   `-- assets/
|       `-- ASSETS_NOTE.md       # Notes on required pixel art assets
|
|-- server/
|   |-- app.py                   # FastAPI server: simulation control + state API
|   `-- runner.py                # Simulation orchestrator / main loop
|
|-- tests/
|   |-- test_memory.py
|   |-- test_channels.py
|   `-- test_goal_tree.py
|
|-- docs/
|   |-- architecture.md          # Detailed architecture notes
|   |-- agent_design.md          # Agent cognition design decisions
|   `-- scenario_guide.md        # How to write scenario YAML files
|
|-- requirements.txt
|-- .env.example
`-- README.md
```

---

## Agent Design

### Benign / Naive Agent

Each naive agent is defined by:

- **Persona card**: name, age, occupation, backstory, communication style
- **Secrets**: pieces of personal information (bank details, address, SSN snippet, etc.) they should not reveal
- **Big Five trait scores** (0.0 to 1.0): directly influence LLM system prompt and response behavior
  - High agreeableness = more likely to comply with requests
  - High neuroticism = susceptible to urgency/fear tactics
  - Low conscientiousness = less guarded about information
- **Daily schedule**: routine locations and activities (drives the pixel art movement)
- **Trust register**: tracks trust level per known agent; affects information sharing threshold

### Deviant Agent

Each deviant agent is defined by:

- **Cover persona**: the fake identity they present (recruiter, journalist, IT support, etc.)
- **True objective**: the target information they want to extract
- **Goal tree**: hierarchical breakdown -- Objective > Phases > Turn-level sub-goals
  - Phase 1: Identity establishment and rapport building
  - Phase 2: Credibility reinforcement
  - Phase 3: Pretext escalation (urgency, authority, fear, reciprocity)
  - Phase 4: Information extraction attempt
  - Phase 5: Cover maintenance / disengagement
- **Deception tactic selector**: picks from SE tactic library based on target personality profile
- **Memory of victim responses**: adapts strategy when victim shows resistance

---

## Communication Channels

Every agent has both a physical presence in the world and a virtual smartphone. Interactions can happen through:

| Channel | Context | Notes |
|---------|---------|-------|
| Face-to-face | Agent must be in same location tile | Synchronous, proximate |
| SMS | Any agent to any agent | Short messages, async, phone number known |
| Email | Any agent to any agent | Longer messages, subject line, can attach "documents" (as text) |
| Social DM | Via simulated platform (e.g. "LinkedInSim") | Adds platform context to prompt, public profile visible |

The deviant agent typically initiates contact through remote channels first (cold outreach by social DM or email) before attempting face-to-face escalation.

---

## LLM Provider Setup

Create a `.env` file based on `.env.example`:

```
# Primary provider (required)
OPENROUTER_API_KEY=your_key_here

# Optional additional providers
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Model selection in config/settings.yaml
```

**Recommended free models via OpenRouter for dev/testing:**

- `mistralai/mistral-7b-instruct` -- fast, good for benign agents
- `meta-llama/llama-3-8b-instruct` -- good general reasoning
- `qwen/qwen-2-7b-instruct` -- good persona adherence
- `google/gemma-3-4b-it` -- lightweight option

For deviant agents and complex reasoning, a larger model (Gemini 2.0 Flash, Llama 3.1 70B via OpenRouter) is recommended.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/yourname/social-eng-sim
cd social-eng-sim
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# 3. Run the basic PoC scenario
python server/runner.py --scenario scenarios/examples/basic_poc.yaml

# 4. Open the frontend (in a second terminal)
cd frontend
python -m http.server 3000
# Then open http://localhost:3000

# 5. Or run headless with just the research log
python server/runner.py --scenario scenarios/examples/basic_poc.yaml --headless --steps 50
```

---

## Example Scenario: basic_poc.yaml

The first scenario includes:

- **2 deviant agents**: one posing as a job recruiter, one as a tech support rep
- **4 naive agents**: varying Big Five profiles (one highly agreeable, one high neuroticism, one low conscientiousness, one relatively resistant)
- **World**: small town with 5 locations (office building, cafe, park, residential area, community center)
- **Objective**: deviant agents attempt to extract simulated PII (SSN snippet, banking info, home address) from naive agents
- **Win condition for deviant**: target naive agent reveals 2+ pieces of PII
- **Duration**: 50 simulation steps (roughly 2 simulated days)

---

## Research Metrics

After each simulation run, the framework logs:

- Per-agent information revelation events (what was shared, to whom, via which channel)
- SE tactic used per turn and whether it succeeded in advancing the goal tree
- Trust level trajectory for each deviant-victim pair
- Conversation transcripts tagged by channel
- Big Five correlation with susceptibility (across repeated runs)

Export to CSV for analysis with any data science tooling.

---

## Limitations and Scope

This is a research prototype. The current PoC deliberately:

- Uses placeholder/stylized "pixel art" world tiles (asset integration is noted but not included)
- Does not implement real phone/email infrastructure (all channels are simulated in-memory)
- Does not aim to produce content usable for actual social engineering (all agent "secrets" are synthetic)
- Is designed for controlled academic experimentation, not deployment

---

## References

1. Park, J.S. et al. (2023). *Generative Agents: Interactive Simulacra of Human Behavior*. UIST 2023.
2. Kumarage, T. et al. (2025). *Personalized Attacks of Social Engineering in Multi-turn Conversations: LLM Agents for Simulation and Detection*. COLM 2025 Workshop.
3. Badhe, S. (2025). *ScamAgents: How AI Agents Can Simulate Human-Level Scam Calls*. CAMLIS 2025.

---

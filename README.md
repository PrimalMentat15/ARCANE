# ⬡ ARCANE v0.9
## Agentic Replication of Cyberfraud and Adversarial Narrative Environments

![ARCANE Dashboard](assets/dashboard.png)

A simulation framework for studying social engineering and cyber fraud behavior in multi-agent environments. 

**v0.9 Update:** Now features a **FastAPI + Phaser.js** frontend, **Terminal CLI** control, and optimized **LLM workload splitting** (OpenRouter + Gemini).

Built on ideas from Generative Agents (Park et al., 2023), SE-VSim (Kumarage et al., 2025), and ScamAgents (Badhe, 2025).

---

## What This Is

ARCANE is a sandbox simulation where:

- **🕵️ Deviant agents** try to manipulate and extract personal information using realistic social engineering tactics
- **👤 Benign/naive agents** live daily routines, driven by Big Five personality traits
- **📱 Dual Communication:** Face-to-face proximity chat + Virtual Smartphones (SMS, Email, Social DM)
- **📊 Research Dashboard:** Real-time event logs, agent states, and social graph metrics

---

## Key Features

- **💻 Modern Frontend:** Custom **Phaser.js** engine rendering a Tiled pixel art world with animated sprites.
- **🖥️ Terminal CLI:** Interactive REPL (`run`, `status`, `log`) for precise step-by-step simulation control.
- **🧠 Hybrid LLM Engine:**
  - **Benign Agents:** OpenRouter (Llama 3.3 70B Free) — cost-effective for background population
  - **Deviant Agents:** Google Gemini 2.5 Flash Lite — high intelligence for deception planning
- **📈 Research-Grade Logging:** Structured JSON event logs for every interaction, tactic, and outcome.
- **🎭 Multi-Channel Deception:** Cold reading via Social DMs, urgency via SMS, authority via Email.

---

## Project Structure

```
ARCANE/
|
|-- arcane/
|   |-- agents/                  # Cognitive architectures (Deviant/Benign)
|   |-- channels/                # Smartphone & Proximity channels
|   |-- config/                  # Settings & Persona definitions
|   |-- frontend/                # Phaser.js Web Client (HTML/JS)
|   |-- llm/                     # OpenRouter & Gemini providers
|   |-- memory/                  # Episodic memory stream
|   |-- research/                # Event logging & Metrics
|   |-- model.py                 # Mesa simulation orchestrator
|   `-- server.py                # FastAPI backend serving the frontend
|
|-- environment/                 # Game Assets
|   `-- frontend_server/static_dirs/assets/
|       |-- characters/          # 32-bit Pixel Art Sprites
|       `-- the_ville/           # Tiled Maps
|
|-- run.py                       # Main Terminal CLI Entry Point
|-- requirements.txt
`-- README.md
```

---

## Agent Design

### Benign / Naive Agent <img src="assets/characters/profile/Abigail_Chen.png" width="32" style="vertical-align:middle">

Each naive agent is defined by:

- **Persona card**: name, age, occupation, backstory, communication style
- **Secrets**: pieces of personal information (bank details, address, SSN snippet, etc.) they should not reveal
- **Big Five trait scores** (0.0 to 1.0): directly influence LLM system prompt and response behavior
  - High agreeableness = more likely to comply with requests
  - High neuroticism = susceptible to urgency/fear tactics
  - Low conscientiousness = less guarded about information
- **Daily schedule**: routine locations and activities (drives the pixel art movement)
- **Trust register**: tracks trust level per known agent; affects information sharing threshold

### Deviant Agent <img src="assets/characters/profile/Adam_Smith.png" width="32" style="vertical-align:middle">

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

## Quick Start

1. **Install Dependencies**
   ```bash
   conda create -n arcane python=3.11
   conda activate arcane
   pip install -r requirements.txt
   ```

2. **Configure Keys** (`.env`)
   ```ini
   OPENROUTER_API_KEY=sk-or-...  # For Benign Agents
   GEMINI_API_KEY=AIza...        # For Deviant Agents
   ```

3. **Launch ARCANE**
   ```bash
   python run.py
   ```

4. **Open Dashboard**
   Go to **http://localhost:8765** in your browser.

5. **Control Simulation**
   In the terminal:
   ```bash
   arcane> run 5     # Execute 5 steps
   arcane> status    # Check simulation state
   arcane> log 10    # View last 10 events
   ```

---

## LLM Configuration

ARCANE v0.9 splits the workload to optimize cost and performance:

| Agent Type | Provider | Model | Logic |
|------------|----------|-------|-------|
| **Benign** | OpenRouter | `meta-llama/llama-3.3-70b-instruct:free` | Routine conversations, daily planning |
| **Deviant** | Gemini | `gemini-2.5-flash-lite` | Complex deception strategies, multi-turn planning |

Configure these in `arcane/config/settings.yaml`.

---

## References

1. Park, J.S. et al. (2023). *Generative Agents*.
2. Kumarage, T. et al. (2025). *SE-VSim: Personalized Attacks*.
3. Badhe, S. (2025). *ScamAgents*.

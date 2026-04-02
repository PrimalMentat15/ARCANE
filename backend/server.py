"""
ARCANE Server - Lightweight FastAPI backend

Serves the Phaser.js frontend and exposes REST API endpoints
for the browser to poll simulation state. Does NOT control
step execution — that's done from the terminal CLI (run.py).
"""

import os
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

logger = logging.getLogger("root.server")

# Paths
_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_FRONTEND_DIR = _PROJECT_ROOT / "frontend"
_ASSETS_DIR = _PROJECT_ROOT / "frontend" / "assets"

# Global model reference — set by run.py before starting the server
_model = None

# Sprite assignment cache
_sprite_assignments: dict[str, str] = {}


def set_model(model):
    """Set the shared model reference (called by run.py)."""
    global _model
    _model = model
    _assign_sprites()


def _assign_sprites():
    """Assign character sprites to agents from their persona or fallback pool."""
    global _sprite_assignments

    profile_dir = _ASSETS_DIR / "characters" / "profile"
    if not profile_dir.exists():
        logger.warning(f"Profile sprite directory not found: {profile_dir}")
        return

    available = sorted([f.stem for f in profile_dir.glob("*.png")])
    if not available:
        return

    if _model is None:
        return

    agents = list(_model.agents_by_id.values())

    # Build set of already-used sprites (from persona definitions)
    used = set()
    for agent in agents:
        persona_sprite = getattr(agent, 'sprite', None)
        if persona_sprite and persona_sprite in available:
            _sprite_assignments[agent.agent_id] = persona_sprite
            used.add(persona_sprite)

    # Assign from remaining pool for agents without a persona sprite
    pool = [s for s in available if s not in used]
    for agent in agents:
        if agent.agent_id not in _sprite_assignments:
            if pool:
                sprite_name = pool.pop(0)
            else:
                sprite_name = available[hash(agent.agent_id) % len(available)]
            _sprite_assignments[agent.agent_id] = sprite_name

    logger.info(f"Assigned sprites to {len(_sprite_assignments)} agents")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="ARCANE", docs_url=None, redoc_url=None)

    # --- Static file mounts ---

    # Frontend files (HTML/JS/CSS)
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="frontend")

    # Game assets (tilesets, sprites, maps)
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")

    # --- Routes ---

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the main frontend page."""
        index_path = _FRONTEND_DIR / "index.html"
        return FileResponse(str(index_path))

    @app.get("/api/state")
    async def get_state():
        """Return current simulation state for the frontend to render."""
        if _model is None:
            return {"error": "Model not initialized", "step": 0, "agents": {}}

        agents_data = {}
        for agent_id, agent in _model.agents_by_id.items():
            pos = getattr(agent, 'current_tile', (0, 0))
            agents_data[agent_id] = {
                "name": getattr(agent, 'name', 'Unknown'),
                "type": getattr(agent, 'agent_type', 'benign'),
                "pos": list(pos) if pos else [0, 0],
                "sprite": _sprite_assignments.get(agent_id, "Adam_Smith"),
                "pronunciatio": getattr(agent, 'pronunciatio', '💬'),
                "activity": getattr(agent, 'current_activity', 'idle')[:60],
                "location": getattr(agent, 'current_location_name', ''),
            }

        return {
            "step": _model.step_count,
            "sim_time": _model.sim_time_str,
            "grid": {
                "width": _model.grid.width,
                "height": _model.grid.height,
            },
            "agents": agents_data,
        }

    @app.get("/api/events")
    async def get_events(n: int = Query(default=30, le=200)):
        """Return recent events for the interaction log."""
        if _model is None:
            return {"events": []}

        events = _model.event_logger.get_recent_events(n)
        return {
            "events": [
                {
                    "step": e.step,
                    "type": e.event_type.value,
                    "timestamp": e.timestamp,
                    "agent": e.agent_id or "",
                    "target": e.target_id or "",
                    "content": e.content,
                }
                for e in events
            ]
        }

    @app.get("/api/agents")
    async def get_agents():
        """Return detailed agent info."""
        if _model is None:
            return {"agents": []}

        agents_list = []
        for agent_id, agent in _model.agents_by_id.items():
            info = {
                "id": agent_id,
                "name": getattr(agent, 'name', 'Unknown'),
                "type": getattr(agent, 'agent_type', 'benign'),
                "activity": getattr(agent, 'current_activity', 'idle'),
                "location": getattr(agent, 'current_location_name', ''),
                "pos": list(getattr(agent, 'current_tile', (0, 0))),
                "sprite": _sprite_assignments.get(agent_id, "Adam_Smith"),
            }

            # Add trust info for benign agents
            if hasattr(agent, 'trust_register'):
                info["trust"] = dict(agent.trust_register)

            agents_list.append(info)

        return {"agents": agents_list}

    @app.get("/api/results")
    async def get_results():
        """Return current attack progress results."""
        if _model is None:
            return {"error": "Model not initialized"}

        from backend.research.results_analyzer import analyze_live, results_to_dict
        results = analyze_live(_model)
        return results_to_dict(results)

    @app.get("/api/history")
    async def get_history():
        """Return list of past simulation runs."""
        from backend.research.results_analyzer import list_runs

        log_dir = "storage/logs"
        if _model and hasattr(_model, 'event_logger'):
            log_dir = _model.event_logger.log_dir

        return {"runs": list_runs(log_dir)}

    @app.get("/api/history/{run_id}")
    async def get_historical_results(run_id: str):
        """Return results from a past simulation run."""
        from backend.research.results_analyzer import list_runs, analyze_file, results_to_dict

        log_dir = "storage/logs"
        if _model and hasattr(_model, 'event_logger'):
            log_dir = _model.event_logger.log_dir

        runs = list_runs(log_dir)
        target_file = None
        for run in runs:
            if run["run_id"] == run_id:
                target_file = run["file"]
                break

        if not target_file:
            return {"error": f"Run '{run_id}' not found"}

        results = analyze_file(target_file)
        return results_to_dict(results)

    @app.get("/api/conversations")
    async def get_conversations():
        """Return list of agent pairs that have exchanged messages."""
        if _model is None:
            return {"conversations": []}

        convos = _model.event_logger.get_all_conversations()

        # Enrich with agent names and sprites
        for convo in convos:
            enriched_agents = []
            for agent_id in convo["agents"]:
                agent = _model.agents_by_id.get(agent_id)
                name = getattr(agent, 'name', agent_id) if agent else agent_id
                agent_type = getattr(agent, 'agent_type', 'benign') if agent else 'benign'
                sprite = _sprite_assignments.get(agent_id, "Adam_Smith")
                enriched_agents.append({
                    "id": agent_id,
                    "name": name,
                    "type": agent_type,
                    "sprite": sprite,
                })
            convo["agents"] = enriched_agents

        return {"conversations": convos}

    @app.get("/api/conversations/all")
    async def get_all_messages():
        """Return all messages across all agents (combined feed)."""
        if _model is None:
            return {"messages": []}

        from backend.research.event_logger import EventType
        events = [
            e for e in _model.event_logger.all_events
            if e.event_type == EventType.MESSAGE_SENT
        ]

        messages = []
        for e in events:
            sender = _model.agents_by_id.get(e.agent_id)
            target = _model.agents_by_id.get(e.target_id)
            messages.append({
                "step": e.step,
                "timestamp": e.timestamp,
                "sender_id": e.agent_id or "",
                "sender_name": getattr(sender, 'name', e.agent_id) if sender else (e.agent_id or ""),
                "sender_type": getattr(sender, 'agent_type', 'benign') if sender else 'benign',
                "sender_sprite": _sprite_assignments.get(e.agent_id, "Adam_Smith"),
                "target_id": e.target_id or "",
                "target_name": getattr(target, 'name', e.target_id) if target else (e.target_id or ""),
                "channel": e.channel or "",
                "content": e.content or "",
            })

        return {"messages": messages}

    @app.get("/api/conversations/{agent1_id}/{agent2_id}")
    async def get_conversation(agent1_id: str, agent2_id: str):
        """Return the full message thread between two agents."""
        if _model is None:
            return {"messages": []}

        events = _model.event_logger.get_conversation_between(agent1_id, agent2_id)

        messages = []
        for e in events:
            sender = _model.agents_by_id.get(e.agent_id)
            messages.append({
                "step": e.step,
                "timestamp": e.timestamp,
                "sender_id": e.agent_id or "",
                "sender_name": getattr(sender, 'name', e.agent_id) if sender else (e.agent_id or ""),
                "sender_type": getattr(sender, 'agent_type', 'benign') if sender else 'benign',
                "sender_sprite": _sprite_assignments.get(e.agent_id, "Adam_Smith"),
                "target_id": e.target_id or "",
                "channel": e.channel or "",
                "content": e.content or "",
            })

        return {"messages": messages}

    # --- Setup API endpoints ---

    @app.get("/api/setup/status")
    async def get_setup_status():
        """Check if the simulation model is initialized."""
        return {
            "ready": _model is not None,
            "step": _model.step_count if _model else 0,
        }

    @app.get("/api/setup/personas")
    async def get_setup_personas():
        """Return all available personas with full metadata for the setup screen."""
        from backend.agents.personas.loader import load_persona, list_available_personas

        personas = []
        for agent_type in ("benign", "deviant"):
            for persona_id in list_available_personas(agent_type):
                try:
                    data = load_persona(persona_id)
                    persona_info = {
                        "id": persona_id,
                        "name": data.get("name", persona_id),
                        "type": data.get("type", agent_type),
                        "age": data.get("age", ""),
                        "occupation": data.get("occupation", ""),
                        "backstory": data.get("backstory", ""),
                        "sprite": data.get("sprite", "Adam_Smith"),
                        "traits": data.get("traits", {}),
                        "secrets_count": len(data.get("secrets", [])),
                        "starting_location": data.get("starting_location", ""),
                    }
                    # Include cover persona for deviant display
                    if agent_type == "deviant" and "cover_persona" in data:
                        persona_info["cover_role"] = data["cover_persona"].get("role", "")
                    personas.append(persona_info)
                except Exception as e:
                    logger.warning(f"Failed to load persona '{persona_id}': {e}")

        return {"personas": personas}

    @app.get("/api/setup/providers")
    async def get_setup_providers():
        """Return available LLM providers and current configuration."""
        import yaml as _yaml

        config_path = _BACKEND_DIR / "config" / "settings.yaml"
        config = {}
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                config = _yaml.safe_load(f) or {}

        llm_cfg = config.get("llm", {})
        local_cfg = config.get("local_llm", {})

        providers = [
            {
                "id": "local",
                "name": "Local LLM (LM Studio / Ollama)",
                "description": "Run models locally — no API key needed",
                "requires_key": False,
                "base_url": local_cfg.get("base_url", "http://localhost:1234/v1"),
                "default_model": "meta-llama-3.1-8b-instruct",
                "current": llm_cfg.get("benign_agents", {}).get("provider") == "local",
            },
            {
                "id": "gemini",
                "name": "Google Gemini API",
                "description": "Cloud API — requires GEMINI_API_KEY in .env",
                "requires_key": True,
                "has_key": bool(os.environ.get("GEMINI_API_KEY")),
                "default_model": "gemini-2.0-flash-lite",
                "current": llm_cfg.get("benign_agents", {}).get("provider") == "gemini",
            },
        ]

        return {"providers": providers}

    @app.post("/api/setup/launch")
    async def launch_simulation(body: dict):
        """Create the simulation model with user-selected configuration.

        Expected body:
        {
            "provider": "local" | "gemini",
            "model": "model-name",
            "agents": [
                {"persona": "sarah_chen", "id": "agent_benign_1"},
                {"persona": "marcus_webb", "id": "agent_deviant_1"},
                ...
            ]
        }
        """
        global _model

        if _model is not None:
            return {"error": "Simulation already running. Restart the server to configure a new one."}

        import yaml as _yaml

        # Load base config
        config_path = _BACKEND_DIR / "config" / "settings.yaml"
        if config_path.exists():
            with open(config_path, encoding='utf-8') as f:
                config = _yaml.safe_load(f) or {}
        else:
            config = {}

        # Override LLM provider from user selection
        provider = body.get("provider", "local")
        model_name = body.get("model", "")

        if provider == "local":
            local_cfg = config.get("local_llm", {})
            default_model = "meta-llama-3.1-8b-instruct"
            config["llm"] = {
                "benign_agents": {"provider": "local", "model": model_name or default_model},
                "deviant_agents": {"provider": "local", "model": model_name or default_model},
                "reflection": {"provider": "local", "model": model_name or default_model},
            }
        elif provider == "gemini":
            default_model = "gemini-2.0-flash-lite"
            config["llm"] = {
                "benign_agents": {"provider": "gemini", "model": model_name or default_model},
                "deviant_agents": {"provider": "gemini", "model": model_name or "gemini-2.5-flash-lite"},
                "reflection": {"provider": "gemini", "model": model_name or "gemini-2.5-flash-lite"},
            }

        # Override agent roster from user selection
        agent_defs = body.get("agents", [])
        if agent_defs:
            config.setdefault("simulation", {})["agents"] = agent_defs

        # Create model
        try:
            from backend.model import ArcaneModel
            _model = ArcaneModel(config=config)
            _assign_sprites()

            agent_count = len(_model.agents_by_id)
            deviant_count = sum(1 for a in _model.agents_by_id.values()
                                if getattr(a, 'agent_type', '') == 'deviant')

            logger.info(f"Simulation launched via setup: {agent_count} agents "
                        f"({deviant_count} deviant), provider={provider}")

            return {
                "success": True,
                "agents": agent_count,
                "deviant_count": deviant_count,
                "benign_count": agent_count - deviant_count,
                "provider": provider,
                "model": model_name or "default",
            }
        except Exception as e:
            logger.error(f"Failed to launch simulation: {e}")
            return {"error": str(e)}

    @app.post("/api/setup/test-connection")
    async def test_llm_connection(body: dict):
        """Test connectivity to a local LLM server."""
        import httpx

        base_url = body.get("base_url", "http://localhost:1234/v1")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{base_url}/models", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("id", "unknown") for m in data.get("data", [])]
                    return {"connected": True, "models": models}
                else:
                    return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except httpx.ConnectError:
            return {"connected": False, "error": "Cannot connect. Is LM Studio running?"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # --- Recording & Replay API endpoints ---

    @app.get("/api/recordings")
    async def get_recordings():
        """List all available simulation recordings."""
        from backend.research.sim_player import list_recordings

        rec_dir = "storage/recordings"
        if _model and hasattr(_model, 'recorder') and _model.recorder:
            rec_dir = _model.recorder.recording_dir

        recordings = list_recordings(rec_dir)
        return {"recordings": recordings}

    @app.get("/api/recordings/{run_id}")
    async def get_recording_meta(run_id: str):
        """Get metadata for a specific recording."""
        from backend.research.sim_player import SimPlayer, list_recordings

        rec_dir = "storage/recordings"
        if _model and hasattr(_model, 'recorder') and _model.recorder:
            rec_dir = _model.recorder.recording_dir

        # Find the file
        recordings = list_recordings(rec_dir)
        target_file = None
        for rec in recordings:
            if rec["run_id"] == run_id:
                target_file = rec["file"]
                break

        if not target_file:
            return {"error": f"Recording '{run_id}' not found"}

        player = SimPlayer()
        try:
            meta = player.load(target_file)
            return meta
        except (FileNotFoundError, ValueError) as e:
            return {"error": str(e)}

    @app.get("/api/recordings/{run_id}/step/{step}")
    async def get_recording_frame(run_id: str, step: int):
        """Get state + events frame for a specific step in a recording."""
        from backend.research.sim_player import SimPlayer, list_recordings

        rec_dir = "storage/recordings"
        if _model and hasattr(_model, 'recorder') and _model.recorder:
            rec_dir = _model.recorder.recording_dir

        # Find the file
        recordings = list_recordings(rec_dir)
        target_file = None
        for rec in recordings:
            if rec["run_id"] == run_id:
                target_file = rec["file"]
                break

        if not target_file:
            return {"error": f"Recording '{run_id}' not found"}

        player = SimPlayer()
        try:
            player.load(target_file)
        except (FileNotFoundError, ValueError) as e:
            return {"error": str(e)}

        frame = player.get_frame(step)
        if frame is None:
            return {"error": f"Step {step} not found in recording"}

        # Enrich with agent roster for sprite info
        agents_roster = player.recording.get("agents", {})
        return {
            "frame": frame,
            "agents_roster": agents_roster,
        }

    @app.get("/api/recordings/{run_id}/full")
    async def get_recording_full(run_id: str):
        """Get the entire recording (all frames) for client-side replay."""
        from backend.research.sim_player import SimPlayer, list_recordings

        rec_dir = "storage/recordings"
        if _model and hasattr(_model, 'recorder') and _model.recorder:
            rec_dir = _model.recorder.recording_dir

        recordings = list_recordings(rec_dir)
        target_file = None
        for rec in recordings:
            if rec["run_id"] == run_id:
                target_file = rec["file"]
                break

        if not target_file:
            return {"error": f"Recording '{run_id}' not found"}

        player = SimPlayer()
        try:
            player.load(target_file)
        except (FileNotFoundError, ValueError) as e:
            return {"error": str(e)}

        return {
            "metadata": player.get_metadata(),
            "frames": player.frames,
        }

    return app


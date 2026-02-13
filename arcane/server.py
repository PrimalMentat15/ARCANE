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

logger = logging.getLogger("arcane.server")

# Paths
_ARCANE_ROOT = Path(__file__).resolve().parent
_PROJECT_ROOT = _ARCANE_ROOT.parent
_FRONTEND_DIR = _ARCANE_ROOT / "frontend"
_ASSETS_DIR = _ARCANE_ROOT / "assets"

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
    """Assign character sprites to agents from the available pool."""
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

    # Assign sprites: deviant gets a distinguishable one, benign get from pool
    pool = list(available)
    for agent in agents:
        agent_type = getattr(agent, 'agent_type', 'benign')
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

    return app

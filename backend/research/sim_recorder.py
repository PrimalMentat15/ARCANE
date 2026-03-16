"""
ARCANE Simulation Recorder

Captures complete per-step state snapshots alongside events,
producing a `.arcane` recording file that enables full simulation
replay with all timestamps, positions, and events in order.

Recording format (.arcane):
    A JSON file containing a header with metadata and an array of
    "frames" — one per simulation step — each holding the complete
    agent state snapshot and all events that occurred during that step.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.model import ArcaneModel

logger = logging.getLogger("root.recorder")

# Current recording format version
FORMAT_VERSION = 1


class SimRecorder:
    """
    Records simulation runs into replayable `.arcane` files.

    Each frame captures:
    - Step number and sim time
    - Wall-clock timestamp
    - Full agent state snapshot (position, location, activity, emoji, trust)
    - All events that occurred during the step
    """

    def __init__(self, recording_dir: str = "storage/recordings",
                 save_interval: int = 5):
        """
        Args:
            recording_dir: Directory to save recording files.
            save_interval: Auto-save every N steps (0 = only on end).
        """
        self.recording_dir = recording_dir
        self.save_interval = save_interval

        os.makedirs(recording_dir, exist_ok=True)

        self.run_id: str = ""
        self.created_at: str = ""
        self.config_snapshot: dict = {}
        self.agents_roster: dict = {}
        self.frames: list[dict] = []
        self._initialized = False

    def init_recording(self, model: "ArcaneModel") -> None:
        """Initialize a new recording from a live model.

        Call this once after the model is fully constructed and agents
        are placed. Captures the agent roster and config snapshot.
        """
        self.run_id = model.event_logger.run_id
        self.created_at = datetime.now(timezone.utc).isoformat()

        # Snapshot config (strip non-serializable parts)
        self.config_snapshot = _safe_serialize(model.config)

        # Build agent roster
        self.agents_roster = {}
        for agent_id, agent in model.agents_by_id.items():
            self.agents_roster[agent_id] = {
                "name": getattr(agent, 'name', 'Unknown'),
                "type": getattr(agent, 'agent_type', 'benign'),
                "sprite": getattr(agent, 'sprite_name', ''),
            }

        # Capture initial frame (step 0)
        self._capture_frame(model, step=0)
        self._initialized = True

        logger.info(f"Recording initialized: run_{self.run_id} "
                    f"({len(self.agents_roster)} agents)")

    def capture_step(self, model: "ArcaneModel") -> None:
        """Capture frame for the current step.

        Call this at the end of each model.step().
        """
        if not self._initialized:
            return

        self._capture_frame(model, step=model.step_count)

        # Periodic auto-save
        if (self.save_interval > 0
                and model.step_count % self.save_interval == 0):
            self.save()

    def save(self) -> str:
        """Write the recording to disk and return the file path."""
        if not self._initialized:
            logger.warning("Cannot save: recording not initialized")
            return ""

        filepath = os.path.join(
            self.recording_dir, f"rec_{self.run_id}.arcane"
        )

        recording = {
            "format_version": FORMAT_VERSION,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "config": self.config_snapshot,
            "agents": self.agents_roster,
            "total_steps": len(self.frames) - 1,  # exclude step 0
            "total_frames": len(self.frames),
            "frames": self.frames,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(recording, f, ensure_ascii=False, separators=(',', ':'))

        size_kb = os.path.getsize(filepath) / 1024
        logger.info(f"Recording saved: {filepath} "
                    f"({len(self.frames)} frames, {size_kb:.1f}KB)")
        return filepath

    def _capture_frame(self, model: "ArcaneModel", step: int) -> dict:
        """Build and store a single frame snapshot."""
        from backend.research.event_logger import EventType

        # Snapshot agent states
        agent_states = {}
        for agent_id, agent in model.agents_by_id.items():
            # Build trust map
            trust = {}
            if hasattr(agent, 'trust_register'):
                trust = dict(agent.trust_register)

            agent_states[agent_id] = {
                "pos": list(getattr(agent, 'current_tile', (0, 0))),
                "location": getattr(agent, 'current_location_name', ''),
                "activity": getattr(agent, 'current_activity', 'idle'),
                "emoji": getattr(agent, 'pronunciatio', '💬'),
                "trust": trust,
            }

        # Collect events for this step
        step_events = model.event_logger.get_step_events(step)
        events_data = [e.to_dict() for e in step_events]

        frame = {
            "step": step,
            "sim_time": model.sim_time_str,
            "wall_time": datetime.now(timezone.utc).isoformat(),
            "agent_states": agent_states,
            "events": events_data,
        }

        self.frames.append(frame)
        return frame


def _safe_serialize(obj: dict) -> dict:
    """Create a JSON-safe copy of a config dict."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        # Strip non-serializable values
        result = {}
        for k, v in obj.items():
            try:
                json.dumps(v)
                result[k] = v
            except (TypeError, ValueError):
                result[k] = str(v)
        return result

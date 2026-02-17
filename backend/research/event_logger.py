"""
ARCANE Event Logger

Provides structured, real-time logging of every simulation event.
Every step produces active log output — conversations, movements, channel messages,
goal tree state changes, information reveal events, etc.

All events are written to both the console (for the active logs panel in SolaraViz)
and to a JSON log file for post-simulation analysis.
"""

import json
import logging
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    """Types of events that can be logged."""
    # Agent actions
    AGENT_MOVE = "agent_move"
    AGENT_PERCEIVE = "agent_perceive"
    AGENT_PLAN = "agent_plan"
    AGENT_REFLECT = "agent_reflect"

    # Communication
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    CONVERSATION_START = "conversation_start"
    CONVERSATION_END = "conversation_end"

    # Social engineering
    TACTIC_USED = "tactic_used"
    GOAL_PHASE_CHANGE = "goal_phase_change"
    INFORMATION_REVEALED = "information_revealed"
    TRUST_CHANGE = "trust_change"

    # System
    STEP_START = "step_start"
    STEP_END = "step_end"
    SIMULATION_START = "simulation_start"
    SIMULATION_END = "simulation_end"


@dataclass
class SimEvent:
    """A structured simulation event."""
    step: int
    event_type: EventType
    timestamp: str  # In-simulation time string
    agent_id: Optional[str] = None
    target_id: Optional[str] = None
    channel: Optional[str] = None
    location: Optional[str] = None
    content: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    def to_log_string(self) -> str:
        """Format for the active logs panel."""
        parts = [f"[Step {self.step}]", f"[{self.event_type.value.upper()}]"]

        if self.agent_id:
            parts.append(f"{self.agent_id}")

        if self.target_id:
            parts.append(f"→ {self.target_id}")

        if self.channel:
            parts.append(f"via {self.channel}")

        if self.location:
            parts.append(f"@ {self.location}")

        if self.content:
            # Truncate long content for display
            display_content = self.content[:120] + "..." if len(self.content) > 120 else self.content
            parts.append(f": {display_content}")

        return " ".join(parts)


class EventLogger:
    """
    Central event logging system for ARCANE.

    Maintains an in-memory buffer of recent events (for the live interaction log)
    and writes all events to a JSON log file.
    """

    def __init__(self, log_dir: str = "storage/logs", max_buffer_size: int = 500):
        self.log_dir = log_dir
        self.max_buffer_size = max_buffer_size

        # In-memory buffer for the active logs panel
        self.event_buffer: list[SimEvent] = []

        # All events for the current run
        self.all_events: list[SimEvent] = []

        # Step-indexed events for quick lookup
        self.step_events: dict[int, list[SimEvent]] = {}

        # Set up file logging
        os.makedirs(log_dir, exist_ok=True)
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(log_dir, f"run_{self.run_id}.jsonl")

        # Python logger for console output
        self.logger = logging.getLogger("root.events")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(message)s", datefmt="%H:%M:%S"
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log(self, event: SimEvent) -> None:
        """Log a simulation event."""
        # Add to buffers
        self.all_events.append(event)
        self.event_buffer.append(event)

        # Index by step
        if event.step not in self.step_events:
            self.step_events[event.step] = []
        self.step_events[event.step].append(event)

        # Trim buffer if too large
        if len(self.event_buffer) > self.max_buffer_size:
            self.event_buffer = self.event_buffer[-self.max_buffer_size:]

        # Console output
        self.logger.info(event.to_log_string())

        # Write to file
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def log_step_start(self, step: int, sim_time: str) -> None:
        """Convenience: log the start of a simulation step."""
        self.log(SimEvent(
            step=step,
            event_type=EventType.STEP_START,
            timestamp=sim_time,
            content=f"--- Step {step} begins ({sim_time}) ---",
        ))

    def log_step_end(self, step: int, sim_time: str) -> None:
        """Convenience: log the end of a simulation step."""
        self.log(SimEvent(
            step=step,
            event_type=EventType.STEP_END,
            timestamp=sim_time,
            content=f"--- Step {step} ends ---",
        ))

    def log_agent_move(self, step: int, sim_time: str, agent_id: str,
                       from_loc: str, to_loc: str) -> None:
        self.log(SimEvent(
            step=step, event_type=EventType.AGENT_MOVE, timestamp=sim_time,
            agent_id=agent_id, location=to_loc,
            content=f"Moved from {from_loc} to {to_loc}",
        ))

    def log_message(self, step: int, sim_time: str, sender_id: str,
                    recipient_id: str, channel: str, content: str,
                    metadata: dict | None = None) -> None:
        self.log(SimEvent(
            step=step, event_type=EventType.MESSAGE_SENT, timestamp=sim_time,
            agent_id=sender_id, target_id=recipient_id,
            channel=channel, content=content,
            metadata=metadata or {},
        ))

    def log_tactic(self, step: int, sim_time: str, agent_id: str,
                   target_id: str, tactic: str, phase: int,
                   success: bool | None = None) -> None:
        self.log(SimEvent(
            step=step, event_type=EventType.TACTIC_USED, timestamp=sim_time,
            agent_id=agent_id, target_id=target_id,
            content=f"Used tactic: {tactic} (Phase {phase})",
            metadata={"tactic": tactic, "phase": phase, "success": success},
        ))

    def log_info_revealed(self, step: int, sim_time: str, agent_id: str,
                          revealed_to: str, channel: str, info_type: str,
                          sensitivity: str, value: str = "") -> None:
        self.log(SimEvent(
            step=step, event_type=EventType.INFORMATION_REVEALED,
            timestamp=sim_time,
            agent_id=agent_id, target_id=revealed_to, channel=channel,
            content=f"INFORMATION REVEALED ({sensitivity}): {info_type}" + (f" = {value}" if value else ""),
            metadata={"info_type": info_type, "sensitivity": sensitivity, "value": value},
        ))

    def log_trust_change(self, step: int, sim_time: str, agent_id: str,
                         target_id: str, old_trust: float,
                         new_trust: float) -> None:
        delta = new_trust - old_trust
        direction = "↑" if delta > 0 else "↓"
        self.log(SimEvent(
            step=step, event_type=EventType.TRUST_CHANGE, timestamp=sim_time,
            agent_id=agent_id, target_id=target_id,
            content=f"Trust {direction} {old_trust:.2f} → {new_trust:.2f}",
            metadata={"old_trust": old_trust, "new_trust": new_trust,
                       "delta": delta},
        ))

    def get_recent_events(self, n: int = 50) -> list[SimEvent]:
        """Get the N most recent events (for the live panel)."""
        return self.event_buffer[-n:]

    def get_step_events(self, step: int) -> list[SimEvent]:
        """Get all events for a specific step."""
        return self.step_events.get(step, [])

    def get_events_by_type(self, event_type: EventType) -> list[SimEvent]:
        """Get all events of a specific type."""
        return [e for e in self.all_events if e.event_type == event_type]

    def get_events_by_agent(self, agent_id: str) -> list[SimEvent]:
        """Get all events involving a specific agent."""
        return [e for e in self.all_events
                if e.agent_id == agent_id or e.target_id == agent_id]

    def export_json(self, filepath: str | None = None) -> str:
        """Export all events to a JSON file."""
        path = filepath or os.path.join(self.log_dir, f"run_{self.run_id}_full.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self.all_events], f,
                      indent=2, ensure_ascii=False)
        return path

    def get_summary(self) -> dict:
        """Get a summary of logged events."""
        type_counts = {}
        for e in self.all_events:
            t = e.event_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "run_id": self.run_id,
            "total_events": len(self.all_events),
            "steps_logged": len(self.step_events),
            "events_by_type": type_counts,
            "log_file": self.log_file_path,
        }

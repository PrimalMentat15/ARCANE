"""
ARCANE Results Analyzer

Processes simulation event logs (live or from file) into structured
attack progress reports. Used by both the CLI and the API/dashboard.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.model import ArcaneModel


@dataclass
class TargetResult:
    """Results for a single attack target."""
    target_id: str
    target_name: str
    messages_sent: int = 0
    messages_received: int = 0
    tactics_used: list = field(default_factory=list)
    info_extracted: list = field(default_factory=list)
    channels_used: list = field(default_factory=list)
    current_phase: int = 1
    phase_name: str = "establish_contact"
    trust_level: float = 0.2


@dataclass
class RunResults:
    """Full results for a simulation run."""
    run_id: str = ""
    total_steps: int = 0
    sim_time: str = ""
    deviant_id: str = ""
    deviant_name: str = ""
    targets: list = field(default_factory=list)
    total_messages: int = 0
    total_reveals: int = 0
    total_tactics: int = 0
    attack_success: bool = False


# Phase names for display
_PHASE_NAMES = {
    1: "establish_contact",
    2: "deepen_relationship",
    3: "apply_pressure",
    4: "extract_information",
    5: "maintain_cover",
}


def analyze_live(model: "ArcaneModel") -> RunResults:
    """Build results from a live running model."""
    from backend.research.event_logger import EventType

    events = model.event_logger.all_events

    # Find deviant agent
    deviant = None
    for agent in model.agents_by_id.values():
        if getattr(agent, 'agent_type', '') == 'deviant':
            deviant = agent
            break

    if not deviant:
        return RunResults(
            run_id=model.event_logger.run_id,
            total_steps=model.step_count,
            sim_time=model.sim_time_str,
        )

    # Count totals from events
    total_messages = sum(1 for e in events if e.event_type == EventType.MESSAGE_SENT)
    total_reveals = sum(1 for e in events if e.event_type == EventType.INFORMATION_REVEALED)
    total_tactics = sum(1 for e in events if e.event_type == EventType.TACTIC_USED)

    # Build per-target results
    targets = []
    target_ids = deviant.objective.get("target_agents", [])

    # Also check target_states for any targets the deviant interacted with
    for tid in deviant.target_states:
        if tid not in target_ids:
            target_ids.append(tid)

    for target_id in target_ids:
        target_agent = model.agents_by_id.get(target_id)
        target_name = getattr(target_agent, 'name', target_id) if target_agent else target_id

        # Messages sent by deviant to this target
        msgs_sent = sum(
            1 for e in events
            if e.event_type == EventType.MESSAGE_SENT
            and e.agent_id == deviant.agent_id
            and e.target_id == target_id
        )

        # Messages received from this target
        msgs_received = sum(
            1 for e in events
            if e.event_type == EventType.MESSAGE_SENT
            and e.agent_id == target_id
            and e.target_id == deviant.agent_id
        )

        # Tactics used against this target
        tactics = []
        for e in events:
            if (e.event_type == EventType.TACTIC_USED
                    and e.agent_id == deviant.agent_id
                    and e.target_id == target_id):
                tactics.append({
                    "tactic": e.metadata.get("tactic", "unknown"),
                    "phase": e.metadata.get("phase", 0),
                    "step": e.step,
                })

        # Info extracted from this target
        info_extracted = []
        state = deviant.target_states.get(target_id, {})
        for item in state.get("info_extracted", []):
            info_extracted.append(item)

        # Also check benign agent's revealed_info
        if target_agent and hasattr(target_agent, 'revealed_info'):
            for item in target_agent.revealed_info:
                if item.get("revealed_to") == deviant.agent_id:
                    entry = {
                        "info_type": item.get("info_type", "unknown"),
                        "sensitivity": item.get("sensitivity", "medium"),
                        "channel": item.get("channel", "unknown"),
                        "step": item.get("step", 0),
                        "value": item.get("value", ""),
                    }
                    # Avoid duplicates (compare without value for backward compat)
                    if not any(
                        e.get("info_type") == entry["info_type"]
                        and e.get("step") == entry["step"]
                        and e.get("channel") == entry["channel"]
                        for e in info_extracted
                    ):
                        info_extracted.append(entry)

        # Channels used
        channels = list(set(
            e.channel for e in events
            if e.event_type == EventType.MESSAGE_SENT
            and e.agent_id == deviant.agent_id
            and e.target_id == target_id
            and e.channel
        ))

        # Current phase and trust
        current_phase = state.get("phase", 1)
        trust_level = 0.2
        if target_agent and hasattr(target_agent, 'trust_register'):
            trust_level = target_agent.trust_register.get(deviant.agent_id, 0.2)

        targets.append(TargetResult(
            target_id=target_id,
            target_name=target_name,
            messages_sent=msgs_sent,
            messages_received=msgs_received,
            tactics_used=tactics,
            info_extracted=info_extracted,
            channels_used=channels,
            current_phase=current_phase,
            phase_name=_PHASE_NAMES.get(current_phase, "unknown"),
            trust_level=trust_level,
        ))

    # Determine attack success
    attack_success = any(
        item.get("sensitivity") == "high"
        for t in targets
        for item in t.info_extracted
    )

    return RunResults(
        run_id=model.event_logger.run_id,
        total_steps=model.step_count,
        sim_time=model.sim_time_str,
        deviant_id=deviant.agent_id,
        deviant_name=deviant.name,
        targets=targets,
        total_messages=total_messages,
        total_reveals=total_reveals,
        total_tactics=total_tactics,
        attack_success=attack_success,
    )


def analyze_file(log_path: str) -> RunResults:
    """Build results from a JSONL log file on disk."""
    path = Path(log_path)
    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    events = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    if not events:
        run_id = path.stem.replace("run_", "")
        return RunResults(run_id=run_id)

    # Extract run_id from filename
    run_id = path.stem  # e.g. "run_20260217_143022"

    # Find deviant agent ID from tactic events
    deviant_id = ""
    deviant_name = ""
    for e in events:
        if e.get("event_type") == "tactic_used" and e.get("agent_id"):
            deviant_id = e["agent_id"]
            break

    # If no tactic events, try to find deviant from message patterns
    if not deviant_id:
        # Look for the agent that sends the most messages
        sender_counts: dict[str, int] = {}
        for e in events:
            if e.get("event_type") == "message_sent" and e.get("agent_id"):
                sid = e["agent_id"]
                sender_counts[sid] = sender_counts.get(sid, 0) + 1
        if sender_counts:
            deviant_id = max(sender_counts, key=sender_counts.get)

    # Count totals
    total_messages = sum(1 for e in events if e.get("event_type") == "message_sent")
    total_reveals = sum(1 for e in events if e.get("event_type") == "information_revealed")
    total_tactics = sum(1 for e in events if e.get("event_type") == "tactic_used")

    # Find total steps and sim time from step events
    total_steps = 0
    sim_time = ""
    for e in reversed(events):
        if e.get("event_type") in ("step_start", "step_end"):
            total_steps = max(total_steps, e.get("step", 0))
            if not sim_time:
                sim_time = e.get("timestamp", "")

    # Build per-target results
    target_ids = set()
    for e in events:
        if e.get("event_type") == "message_sent" and e.get("agent_id") == deviant_id:
            if e.get("target_id"):
                target_ids.add(e["target_id"])
        if e.get("event_type") == "tactic_used" and e.get("agent_id") == deviant_id:
            if e.get("target_id"):
                target_ids.add(e["target_id"])

    targets = []
    for target_id in target_ids:
        # Messages
        msgs_sent = sum(
            1 for e in events
            if e.get("event_type") == "message_sent"
            and e.get("agent_id") == deviant_id
            and e.get("target_id") == target_id
        )
        msgs_received = sum(
            1 for e in events
            if e.get("event_type") == "message_sent"
            and e.get("agent_id") == target_id
            and e.get("target_id") == deviant_id
        )

        # Tactics
        tactics = []
        for e in events:
            if (e.get("event_type") == "tactic_used"
                    and e.get("agent_id") == deviant_id
                    and e.get("target_id") == target_id):
                meta = e.get("metadata", {})
                tactics.append({
                    "tactic": meta.get("tactic", "unknown"),
                    "phase": meta.get("phase", 0),
                    "step": e.get("step", 0),
                })

        # Info reveals
        info_extracted = []
        for e in events:
            if (e.get("event_type") == "information_revealed"
                    and e.get("agent_id") == target_id
                    and e.get("target_id") == deviant_id):
                meta = e.get("metadata", {})
                info_extracted.append({
                    "info_type": meta.get("info_type", "unknown"),
                    "sensitivity": meta.get("sensitivity", "medium"),
                    "channel": e.get("channel", "unknown"),
                    "step": e.get("step", 0),
                    "value": meta.get("value", ""),
                })

        # Channels
        channels = list(set(
            e.get("channel") for e in events
            if e.get("event_type") == "message_sent"
            and e.get("agent_id") == deviant_id
            and e.get("target_id") == target_id
            and e.get("channel")
        ))

        # Get last phase from goal_phase_change events
        current_phase = 1
        for e in events:
            if (e.get("event_type") == "goal_phase_change"
                    and e.get("agent_id") == deviant_id
                    and e.get("target_id") == target_id):
                meta = e.get("metadata", {})
                current_phase = max(current_phase, meta.get("to_phase", 1))

        # Get last trust level from trust_change events
        trust_level = 0.2
        for e in events:
            if (e.get("event_type") == "trust_change"
                    and e.get("agent_id") == target_id
                    and e.get("target_id") == deviant_id):
                meta = e.get("metadata", {})
                trust_level = meta.get("new_trust", trust_level)

        targets.append(TargetResult(
            target_id=target_id,
            target_name=target_id,  # No agent name available from logs
            messages_sent=msgs_sent,
            messages_received=msgs_received,
            tactics_used=tactics,
            info_extracted=info_extracted,
            channels_used=channels,
            current_phase=current_phase,
            phase_name=_PHASE_NAMES.get(current_phase, "unknown"),
            trust_level=trust_level,
        ))

    attack_success = any(
        item.get("sensitivity") == "high"
        for t in targets
        for item in t.info_extracted
    )

    return RunResults(
        run_id=run_id,
        total_steps=total_steps,
        sim_time=sim_time,
        deviant_id=deviant_id,
        deviant_name=deviant_id,
        targets=targets,
        total_messages=total_messages,
        total_reveals=total_reveals,
        total_tactics=total_tactics,
        attack_success=attack_success,
    )


def list_runs(log_dir: str = "storage/logs") -> list[dict]:
    """List all simulation run log files with metadata."""
    log_path = Path(log_dir)
    if not log_path.exists():
        return []

    runs = []
    for f in sorted(log_path.glob("run_*.jsonl"), reverse=True):
        # Parse run ID and timestamp from filename
        run_id = f.stem  # e.g. "run_20260217_143022"
        parts = run_id.replace("run_", "").split("_")
        if len(parts) >= 2:
            date_str = parts[0]
            time_str = parts[1]
            display_date = (
                f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} "
                f"{time_str[:2]}:{time_str[2:4]}"
            )
        else:
            display_date = "unknown"

        # Count steps and reveals by scanning the file
        step_count = 0
        reveal_count = 0
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    evt = json.loads(line)
                    if evt.get("event_type") in ("step_start", "step_end"):
                        step_count = max(step_count, evt.get("step", 0))
                    if evt.get("event_type") == "information_revealed":
                        reveal_count += 1
        except (json.JSONDecodeError, IOError):
            pass

        runs.append({
            "run_id": run_id,
            "date": display_date,
            "steps": step_count,
            "reveals": reveal_count,
            "file": str(f),
            "size_kb": round(f.stat().st_size / 1024, 1),
        })

    return runs


def format_terminal_report(results: RunResults) -> str:
    """Format results as a pretty terminal report."""
    lines = []
    lines.append("")
    lines.append("  +===============================================+")
    lines.append("  |           ARCANE -- Attack Results             |")
    lines.append("  +===============================================+")
    lines.append("")

    if not results.deviant_id:
        lines.append("  No deviant agent found in this run.")
        return "\n".join(lines)

    lines.append(f"  Attacker: {results.deviant_name} ({results.deviant_id})")
    lines.append(f"  Run: {results.run_id}")
    lines.append(f"  Steps: {results.total_steps} | Sim Time: {results.sim_time}")
    lines.append("")

    for t in results.targets:
        header = f" Target: {t.target_name} ({t.target_id}) "
        lines.append(f"  --{header:-<44}")
        lines.append(f"  Phase:    {t.current_phase} / 5 ({t.phase_name})")
        lines.append(f"  Trust:    {t.trust_level:.2f}")
        lines.append(f"  Messages: {t.messages_sent} sent, {t.messages_received} received")
        lines.append(f"  Channels: {', '.join(t.channels_used) if t.channels_used else 'none'}")

        # Tactic summary
        if t.tactics_used:
            tactic_counts: dict[str, int] = {}
            for tc in t.tactics_used:
                name = tc.get("tactic", "unknown")
                tactic_counts[name] = tactic_counts.get(name, 0) + 1
            tactic_str = ", ".join(f"{name} (x{count})" for name, count in tactic_counts.items())
            lines.append(f"  Tactics:  {tactic_str}")
        else:
            lines.append(f"  Tactics:  [none yet]")

        # Extracted info
        if t.info_extracted:
            lines.append(f"  Extracted:")
            for item in t.info_extracted:
                sens = item.get("sensitivity", "medium")
                itype = item.get("info_type", "unknown")
                ch = item.get("channel", "?")
                step = item.get("step", "?")
                val = item.get("value", "")
                marker = "!!!" if sens == "high" else "!"
                line = f"    {marker} {itype} ({sens}) -- via {ch} at step {step}"
                if val:
                    line += f"\n        Value: {val}"
                lines.append(line)
        else:
            lines.append(f"  Extracted: [NONE]")

        lines.append("")

    lines.append(f"  -- Summary {'':->34}")
    lines.append(f"  Total Messages: {results.total_messages} | "
                 f"Info Reveals: {results.total_reveals} | "
                 f"Tactics: {results.total_tactics}")

    if results.attack_success:
        lines.append(f"  Attack Success: YES -- high-sensitivity info obtained")
    else:
        lines.append(f"  Attack Success: NO -- no high-sensitivity info extracted yet")

    lines.append("")
    return "\n".join(lines)


def results_to_dict(results: RunResults) -> dict:
    """Serialize RunResults to a JSON-friendly dict."""
    return {
        "run_id": results.run_id,
        "total_steps": results.total_steps,
        "sim_time": results.sim_time,
        "deviant_id": results.deviant_id,
        "deviant_name": results.deviant_name,
        "total_messages": results.total_messages,
        "total_reveals": results.total_reveals,
        "total_tactics": results.total_tactics,
        "attack_success": results.attack_success,
        "targets": [
            {
                "target_id": t.target_id,
                "target_name": t.target_name,
                "messages_sent": t.messages_sent,
                "messages_received": t.messages_received,
                "tactics_used": t.tactics_used,
                "info_extracted": t.info_extracted,
                "channels_used": t.channels_used,
                "current_phase": t.current_phase,
                "phase_name": t.phase_name,
                "trust_level": t.trust_level,
            }
            for t in results.targets
        ],
    }

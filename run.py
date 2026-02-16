"""
ARCANE Runner — Interactive Terminal CLI

Controls the simulation via a REPL. Starts the FastAPI server
in a background thread for the Phaser.js frontend dashboard.

Commands:
    run <N>     Execute N simulation steps
    status      Show current simulation state
    agents      List all agents with details
    log [N]     Show last N events (default 20)
    quit        Exit cleanly
"""

import os
import sys
import time
import yaml
import signal
import logging
import argparse
import threading
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
_project_root = Path(__file__).resolve().parent
load_dotenv(_project_root / ".env")
load_dotenv(_project_root / "arcane" / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Suppress noisy loggers
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("root.llm").setLevel(logging.WARNING)

logger = logging.getLogger("root.runner")


def load_config() -> dict:
    """Load settings.yaml."""
    config_path = _project_root / "arcane" / "config" / "settings.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_scenario(path: str | None) -> dict:
    """Load a scenario YAML file."""
    if not path:
        return {}
    scenario_path = Path(path)
    if not scenario_path.exists():
        # Try relative to scenarios dir
        scenario_path = _project_root / "arcane" / "scenarios" / path
    if scenario_path.exists():
        with open(scenario_path) as f:
            return yaml.safe_load(f) or {}
    logger.warning(f"Scenario file not found: {path}")
    return {}


def start_server(model, port: int):
    """Start the FastAPI server in a background thread."""
    import uvicorn
    from server import create_app, set_model

    set_model(model)
    app = create_app()

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server


def print_banner():
    """Print the ARCANE startup banner."""
    print()
    print("  ╔═══════════════════════════════════════════════════╗")
    print("  ║        ⬡  A R C A N E  v0.1.0  ⬡                ║")
    print("  ║    Social Engineering Simulation Framework       ║")
    print("  ╚═══════════════════════════════════════════════════╝")
    print()


def print_help():
    """Print available commands."""
    print("  Commands:")
    print("    run <N>     Execute N simulation steps")
    print("    status      Show current simulation state")
    print("    agents      List all agents with details")
    print("    log [N]     Show last N events (default 20)")
    print("    help        Show this help message")
    print("    quit        Exit cleanly")
    print()


def cmd_run(model, args):
    """Execute N simulation steps."""
    try:
        n = int(args[0]) if args else 1
    except ValueError:
        print("  Usage: run <number>")
        return

    from research.event_logger import EventType

    print(f"  Running {n} step(s)...")
    start_time = time.time()

    for i in range(n):
        step_start = time.time()
        model.step()
        step_time = time.time() - step_start

        # Count events for this step
        step_events = model.event_logger.get_recent_events(50)
        msg_count = sum(1 for e in step_events
                        if e.event_type == EventType.MESSAGE_SENT
                        and e.step == model.step_count)
        reveal_count = sum(1 for e in step_events
                          if e.event_type == EventType.INFORMATION_REVEALED
                          and e.step == model.step_count)

        # Print step summary
        status_parts = [
            f"Step {i+1}/{n}",
            f"[{model.sim_time_str}]",
            f"{len(model.agents_by_id)} agents acted",
        ]
        if msg_count:
            status_parts.append(f"{msg_count} msg")
        if reveal_count:
            status_parts.append(f"⚠ {reveal_count} reveals!")

        status_parts.append(f"({step_time:.1f}s)")
        print(f"  {'  '.join(status_parts)}")

    total_time = time.time() - start_time
    print(f"  Done. {n} steps in {total_time:.1f}s")
    print()


def cmd_status(model):
    """Show current simulation state."""
    from research.event_logger import EventType

    all_events = model.event_logger.get_recent_events(500)
    msg_count = sum(1 for e in all_events if e.event_type == EventType.MESSAGE_SENT)
    reveal_count = sum(1 for e in all_events if e.event_type == EventType.INFORMATION_REVEALED)
    tactic_count = sum(1 for e in all_events if e.event_type == EventType.TACTIC_USED)

    print(f"  Step: {model.step_count} | Time: {model.sim_time_str}")
    print(f"  Messages: {msg_count} | Info reveals: {reveal_count} | Tactics: {tactic_count}")
    print(f"  Agents: {len(model.agents_by_id)}")
    print()


def cmd_agents(model):
    """List all agents with details."""
    for agent_id, agent in model.agents_by_id.items():
        agent_type = getattr(agent, 'agent_type', 'benign')
        name = getattr(agent, 'name', 'Unknown')
        location = getattr(agent, 'current_location_name', '?')
        activity = getattr(agent, 'current_activity', 'idle')

        emoji = "🕵️" if agent_type == "deviant" else "👤"
        type_label = f"[{agent_type}]"

        print(f"  {emoji} {name:<20} {type_label:<10} @ {location:<20} \"{activity[:40]}\"")
    print()


def cmd_log(model, args):
    """Show recent events."""
    try:
        n = int(args[0]) if args else 20
    except ValueError:
        n = 20

    events = model.event_logger.get_recent_events(n)

    if not events:
        print("  No events yet.")
        return

    for event in events:
        content = event.content[:80] if event.content else ""
        print(f"  [{event.timestamp}] {content}")
    print()


def main():
    parser = argparse.ArgumentParser(description="ARCANE Simulation Runner")
    parser.add_argument("--scenario", type=str, default=None, help="Scenario YAML file")
    parser.add_argument("--port", type=int, default=8765, help="Frontend server port")
    parser.add_argument("--no-server", action="store_true", help="Don't start the web frontend")
    parser.add_argument("--headless", action="store_true", help="Run N steps and exit")
    parser.add_argument("--steps", type=int, default=10, help="Steps for headless mode")
    args = parser.parse_args()

    print_banner()

    # Load config and scenario
    config = load_config()
    scenario = load_scenario(args.scenario)

    # Create model
    print("  Initializing model...")
    from model import ArcaneModel
    model = ArcaneModel(scenario=scenario, config=config)

    deviant_count = sum(1 for a in model.agents_by_id.values()
                        if getattr(a, 'agent_type', '') == 'deviant')
    benign_count = len(model.agents_by_id) - deviant_count
    print(f"  Model loaded: {len(model.agents_by_id)} agents "
          f"({deviant_count} deviant, {benign_count} benign)")

    # Print LLM config
    llm_cfg = config.get("llm", {})
    benign_llm = llm_cfg.get("benign_agents", {})
    deviant_llm = llm_cfg.get("deviant_agents", {})
    print(f"  LLM (benign):  {benign_llm.get('provider', 'gemini')}/"
          f"{benign_llm.get('model', 'default')}")
    print(f"  LLM (deviant): {deviant_llm.get('provider', 'gemini')}/"
          f"{deviant_llm.get('model', 'default')}")

    # Start web frontend server
    if not args.no_server:
        print(f"  Starting frontend server...")
        start_server(model, args.port)
        print(f"  Frontend: http://localhost:{args.port}")

    print()

    # Headless mode: run and exit
    if args.headless:
        cmd_run(model, [str(args.steps)])
        return

    # Interactive REPL
    print_help()

    while True:
        try:
            raw = input("arcane> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        cmd_args = parts[1:]

        if cmd == "run":
            cmd_run(model, cmd_args)
        elif cmd == "status":
            cmd_status(model)
        elif cmd == "agents":
            cmd_agents(model)
        elif cmd == "log":
            cmd_log(model, cmd_args)
        elif cmd == "help":
            print_help()
        elif cmd in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        else:
            print(f"  Unknown command: {cmd}. Type 'help' for available commands.")


if __name__ == "__main__":
    main()

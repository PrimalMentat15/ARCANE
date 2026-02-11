"""
ARCANE Visualization - SolaraViz Application

Sets up the Mesa SolaraViz interactive browser UI with:
- Pixel art grid with agent sprites
- Live interaction log panel
- Metrics dashboard
- Step controls
"""

import os
import solara
from mesa.visualization import SolaraViz, make_space_component, make_plot_component

from model import ArcaneModel


def agent_portrayal(agent):
    """
    Define how agents appear on the grid.

    Returns a dict with visual properties for SolaraViz's SpaceRenderer.
    """
    portrayal = {
        "size": 40,
        "zorder": 2,
    }

    agent_type = getattr(agent, 'agent_type', 'benign')
    name = getattr(agent, 'name', 'Unknown')
    activity = getattr(agent, 'current_activity', 'idle')

    if agent_type == "deviant":
        portrayal["color"] = "#e74c3c"      # Red-ish (subtle indicator)
        portrayal["marker"] = "o"
        portrayal["label"] = f"🕵 {name}"
    else:
        portrayal["color"] = "#3498db"       # Blue
        portrayal["marker"] = "o"
        portrayal["label"] = f"👤 {name}"

    # Show a tooltip with current activity
    portrayal["tooltip"] = f"{name}\n{activity}"

    return portrayal


# Model parameters exposed in the SolaraViz UI controls
model_params = {
    "width": {
        "type": "SliderInt",
        "value": 60,
        "label": "Grid Width",
        "min": 20,
        "max": 100,
        "step": 10,
    },
    "height": {
        "type": "SliderInt",
        "value": 40,
        "label": "Grid Height",
        "min": 20,
        "max": 80,
        "step": 10,
    },
    "seed": {
        "type": "InputText",
        "value": 42,
        "label": "Random Seed",
    },
}


# Custom Solara component: Live Interaction Log
@solara.component
def InteractionLogPanel(model):
    """Real-time interaction log showing all events from the event logger."""
    events = model.event_logger.get_recent_events(30)

    solara.Markdown("## 📋 Live Interaction Log")

    if not events:
        solara.Text("No events yet. Start the simulation!")
        return

    # Render events as a scrollable list
    with solara.Column(style={"max-height": "400px", "overflow-y": "auto",
                               "background-color": "#1a1a2e",
                               "padding": "10px", "border-radius": "8px",
                               "font-family": "monospace", "font-size": "12px"}):
        for event in reversed(events):
            # Color-code by event type
            color_map = {
                "message_sent": "#00d2ff",
                "message_received": "#00ff88",
                "information_revealed": "#ff4444",
                "trust_change": "#ffaa00",
                "tactic_used": "#ff6600",
                "goal_phase_change": "#ff00ff",
                "agent_move": "#888888",
                "agent_plan": "#aaaaaa",
                "step_start": "#555555",
                "step_end": "#555555",
            }
            color = color_map.get(event.event_type.value, "#cccccc")
            text = event.to_log_string()

            solara.HTML(
                tag="div",
                unsafe_innerHTML=f'<span style="color: {color}">{text}</span>',
            )


# Custom Solara component: Metrics Dashboard
@solara.component
def MetricsDashboard(model):
    """Live metrics display."""
    solara.Markdown("## 📊 Metrics")

    step = model.step_count
    sim_time = model.sim_time_str

    # Key stats
    total_msgs = len(model.event_logger.get_events_by_type(
        model.event_logger.__class__.__mro__[0])) if False else 0

    from research.event_logger import EventType
    msg_count = len(model.event_logger.get_events_by_type(EventType.MESSAGE_SENT))
    reveal_count = len(model.event_logger.get_events_by_type(EventType.INFORMATION_REVEALED))
    tactic_count = len(model.event_logger.get_events_by_type(EventType.TACTIC_USED))

    with solara.Row():
        with solara.Column():
            solara.Markdown(f"**Step:** {step}")
            solara.Markdown(f"**Sim Time:** {sim_time}")
        with solara.Column():
            solara.Markdown(f"**Messages:** {msg_count}")
            solara.Markdown(f"**Info Reveals:** {reveal_count}")
        with solara.Column():
            solara.Markdown(f"**Tactics Used:** {tactic_count}")

    # Agent status table
    solara.Markdown("### Agent Status")
    agents = list(model.agents_by_id.values())
    if agents:
        rows = []
        for a in agents:
            agent_type = getattr(a, 'agent_type', '?')
            emoji = "🕵" if agent_type == "deviant" else "👤"
            rows.append(
                f"| {emoji} {a.name} | {a.current_location_name} | {a.current_activity[:30]} |"
            )
        table = "| Agent | Location | Activity |\n|---|---|---|\n" + "\n".join(rows)
        solara.Markdown(table)



# Solara component wrapper for Mesa 3.5 SolaraViz
@solara.component
def Page():
    """Main page component for ARCANE visualization."""
    # Create model instance
    model = solara.use_reactive(ArcaneModel())
    
    # Render SolaraViz with the model
    SolaraViz(
        model=model.value,
        components=[
            make_space_component(agent_portrayal),
            make_plot_component("total_messages"),
            make_plot_component("info_reveals"),
            InteractionLogPanel,
            MetricsDashboard,
        ],
        name="ARCANE - Social Engineering Simulation",
    )


# Export for `solara run`
page = Page


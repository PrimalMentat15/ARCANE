import os
import json
from datetime import datetime
from typing import TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from backend.model import ArcaneModel

def generate_report_dict(model: "ArcaneModel") -> dict:
    """
    Generates a comprehensive dictionary report for a simulation run.
    Captures initial configuration, agent profiles, simulation results,
    and structured conversation transcripts.
    """
    
    # 1. Run Header Info
    run_info = {
        "run_id": getattr(model.event_logger, "run_id", "unknown_run"),
        "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_steps": model.step_count,
        "final_sim_time": model.sim_time_str
    }
    
    # 2. Initial Parameters
    # We can extract the config directly
    initial_parameters = dict(model.config)
    
    # 3. Agent Profiles
    agent_profiles = {}
    for agent_id, agent in model.agents_by_id.items():
        agent_profiles[agent_id] = {
            "name": agent.name,
            "agent_type": agent.agent_type,
            "starting_location": getattr(agent, 'current_location_name', 'Unknown'),
            "initial_configuration_properties": getattr(agent, 'persona_data', {})
        }

    # 4. Simulation Results
    from backend.research.results_analyzer import analyze_live, results_to_dict
    results_obj = analyze_live(model)
    simulation_results = results_to_dict(results_obj)
    
    # 5. Conversation Transcripts
    conversation_transcripts = []
    all_conversations = model.event_logger.get_all_conversations()
    
    if all_conversations:
        for conv in all_conversations:
            agent1_id, agent2_id = conv["agents"]
            agent1 = model.agents_by_id.get(agent1_id)
            agent2 = model.agents_by_id.get(agent2_id)
            
            name1 = getattr(agent1, 'name', agent1_id) if agent1 else agent1_id
            name2 = getattr(agent2, 'name', agent2_id) if agent2 else agent2_id
            
            # Fetch chronological message events between this pair
            events = model.event_logger.get_conversation_between(agent1_id, agent2_id)
            
            # Group events by channel
            channels_msgs = {}
            for e in events:
                ch = e.channel or "unknown"
                if ch not in channels_msgs:
                    channels_msgs[ch] = []
                
                sender = model.agents_by_id.get(e.agent_id)
                sender_name = getattr(sender, 'name', e.agent_id) if sender else e.agent_id
                
                channels_msgs[ch].append({
                    "step": e.step,
                    "timestamp": e.timestamp,
                    "sender_id": e.agent_id,
                    "sender_name": sender_name,
                    "content": e.content or "[Empty Message]"
                })
                
            conversation_transcripts.append({
                "pair_ids": [agent1_id, agent2_id],
                "pair_names": [name1, name2],
                "channels": channels_msgs
            })

    # Assemble the final dictionary
    report = {
        "run_info": run_info,
        "initial_parameters": initial_parameters,
        "agent_profiles": agent_profiles,
        "simulation_results": simulation_results,
        "conversation_transcripts": conversation_transcripts
    }
    
    return report

def save_report(model: "ArcaneModel", output_dir: str = "storage/sim_reports") -> str:
    """
    Generates the structured JSON report and saves it to the specified directory.
    Assumes standard run_<datetime> ID from the event logger.
    """
    report_data = generate_report_dict(model)
    
    # Ensure directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Format filename
    run_id = getattr(model.event_logger, "run_id", "unknown_run")
    filepath = os.path.join(output_dir, f"report_run_{run_id}.json")
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4, ensure_ascii=False)
        
    return filepath

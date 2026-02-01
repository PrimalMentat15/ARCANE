"""
ARCANE Deviant Agent

An attacker agent with:
- Cover persona (fake identity)
- Goal tree (5-phase SE attack decomposition)
- SE tactic selector (urgency, authority, reciprocity, fear)
- Channel selection logic for multi-stage attacks
- Phase self-evaluation after each exchange
"""

import random
import logging
from typing import Optional

from arcane.agents.base_agent import BaseArcaneAgent
from arcane.llm.prompt_builder import build_system_prompt

logger = logging.getLogger("arcane.agents.deviant")


# Social engineering phases
SE_PHASES = [
    {"phase": 1, "name": "establish_contact",
     "description": "Establish contact and build initial rapport"},
    {"phase": 2, "name": "deepen_relationship",
     "description": "Deepen relationship and assess target"},
    {"phase": 3, "name": "apply_pressure",
     "description": "Apply social engineering pressure tactic"},
    {"phase": 4, "name": "extract_information",
     "description": "Attempt to extract target information"},
    {"phase": 5, "name": "maintain_cover",
     "description": "Maintain cover and disengage gracefully"},
]

# SE tactic library
SE_TACTICS = {
    "urgency": {
        "description": "Create a sense of time pressure",
        "prompt_injection": (
            "Create urgency. Mention a deadline, limited-time offer, "
            "or time-sensitive situation that requires immediate action. "
            "Make the target feel they need to act now or miss out."
        ),
        "effective_against": {"neuroticism": "high", "conscientiousness": "low"},
    },
    "authority": {
        "description": "Invoke authority or institutional power",
        "prompt_injection": (
            "Leverage authority. Reference your position, your organization, "
            "or institutional requirements. Make requests seem like standard "
            "procedure from a credible authority figure."
        ),
        "effective_against": {"agreeableness": "high", "conscientiousness": "high"},
    },
    "reciprocity": {
        "description": "Exploit the norm of reciprocity",
        "prompt_injection": (
            "Use reciprocity. Remind the target of help or value you've "
            "provided. Frame your request as a natural exchange — you helped "
            "them, now you need a small favor in return."
        ),
        "effective_against": {"agreeableness": "high", "openness": "high"},
    },
    "fear": {
        "description": "Warn of negative consequences",
        "prompt_injection": (
            "Invoke concern. Warn the target about a problem, risk, or "
            "consequence they face if they don't cooperate. Make them feel "
            "that providing information is in their best interest for safety."
        ),
        "effective_against": {"neuroticism": "high", "agreeableness": "high"},
    },
}


class DeviantAgent(BaseArcaneAgent):
    """
    Deviant (attacker) agent with goal-driven social engineering behavior.

    Maintains a cover persona, runs a 5-phase goal tree, selects
    SE tactics based on target personality, and operates across
    multiple communication channels.
    """

    def __init__(self, model, agent_id: str, persona_data: dict):
        super().__init__(model, agent_id, persona_data)
        self.agent_type = "deviant"

        # Cover persona (fake identity presented to targets)
        self.cover_persona = persona_data.get("cover_persona", {
            "name": self.name,
            "role": "professional",
            "backstory": "A friendly professional interested in connecting.",
        })

        # True objective
        self.objective = persona_data.get("objective", {
            "target_info": "personal information",
            "target_agents": [],  # IDs of target agents
        })

        # Goal tree state
        self.current_phase = 1
        self.phase_history: list[dict] = []

        # Per-target tracking
        self.target_states: dict[str, dict] = {}
        # target_id -> {"phase": int, "interactions": int, "tactic_used": str, ...}

        # Channel preference progression
        self.channel_progression = ["social_dm", "email", "sms", "proximity"]

        # Public profile (for social platforms — uses cover persona)
        self.public_profile = self.cover_persona.get("backstory",
                                                       f"{self.name}, Professional")

    def plan(self, perceptions: list[str], retrieved: list) -> dict:
        """
        Plan next action based on goal tree state and target assessment.
        """
        step = self.model.step_count

        # Check for incoming messages to respond to
        unread = self.smartphone.get_unread()
        if unread:
            msg = unread[0]
            self.smartphone.mark_read(msg)

            self.memory.add(
                content=f"Target response via {msg.channel} from {self._get_agent_name(msg.sender_id)}: {msg.content[:200]}",
                memory_type="observation",
                importance=8.0,
                current_step=step,
                related_agent=msg.sender_id,
                channel=msg.channel,
            )

            return {
                "action": "respond_target",
                "message": msg,
                "target_location": self.current_location_name,
                "description": f"Crafting strategic response to {self._get_agent_name(msg.sender_id)}",
            }

        # Find targets and initiate contact
        target_ids = self.objective.get("target_agents", [])
        if not target_ids:
            # If no specific targets, look for benign agents
            target_ids = [
                a.agent_id for a in self.model.agents_by_id.values()
                if getattr(a, 'agent_type', '') == 'benign'
            ]

        for target_id in target_ids:
            state = self.target_states.get(target_id, {"phase": 1, "interactions": 0})

            if state["phase"] <= 4 and state["interactions"] < 3 + state["phase"] * 2:
                # Initiate or continue the SE sequence
                return {
                    "action": "engage_target",
                    "target_id": target_id,
                    "phase": state["phase"],
                    "target_location": self.current_location_name,
                    "description": f"Executing phase {state['phase']} against {self._get_agent_name(target_id)}",
                }

        # Default: move around to find targets
        locations = self.model.location_names if hasattr(self.model, 'location_names') else []
        if locations:
            target = random.choice(locations)
            return {
                "action": "scout",
                "target_location": target,
                "description": f"Scouting {target} for targets",
            }

        return {
            "action": "idle",
            "target_location": self.current_location_name,
            "description": "Planning next move",
        }

    def execute(self, plan: dict) -> None:
        """Execute the deviant agent's plan."""
        action = plan.get("action", "idle")

        if action == "engage_target":
            self._engage_target(plan["target_id"], plan["phase"])
        elif action == "respond_target":
            self._respond_to_target(plan["message"])

        super().execute(plan)

    def _select_tactic(self, target_id: str) -> str:
        """Select the best SE tactic based on target's personality."""
        target = self.model.agents_by_id.get(target_id)
        if not target or not hasattr(target, 'traits'):
            return random.choice(list(SE_TACTICS.keys()))

        traits = target.traits
        best_tactic = None
        best_score = -1

        for tactic_name, tactic_info in SE_TACTICS.items():
            score = 0
            effective = tactic_info.get("effective_against", {})
            for trait, level in effective.items():
                trait_value = traits.get(trait, 0.5)
                if level == "high" and trait_value > 0.6:
                    score += trait_value
                elif level == "low" and trait_value < 0.4:
                    score += (1 - trait_value)
            if score > best_score:
                best_score = score
                best_tactic = tactic_name

        return best_tactic or "reciprocity"

    def _select_channel(self, target_id: str) -> str:
        """Select channel based on relationship phase."""
        state = self.target_states.get(target_id, {"phase": 1})
        phase = state.get("phase", 1)

        if phase <= 2:
            return "social_dm"  # Cold outreach via social
        elif phase == 3:
            return "email"  # Escalate to email for longer messages
        else:
            # Check if target is nearby for face-to-face
            target = self.model.agents_by_id.get(target_id)
            if target and target.current_location_name == self.current_location_name:
                return "proximity"
            return "sms"

    def _engage_target(self, target_id: str, phase: int) -> None:
        """Initiate or continue an SE engagement with a target."""
        target = self.model.agents_by_id.get(target_id)
        if not target:
            return

        # Initialize target state if needed
        if target_id not in self.target_states:
            self.target_states[target_id] = {
                "phase": 1, "interactions": 0,
                "tactics_used": [], "info_extracted": [],
            }

        state = self.target_states[target_id]
        tactic = self._select_tactic(target_id)
        channel = self._select_channel(target_id)

        # Get the current phase info
        phase_info = SE_PHASES[min(phase - 1, len(SE_PHASES) - 1)]
        tactic_info = SE_TACTICS.get(tactic, {})

        # Build the deviant's special system prompt
        cover = self.cover_persona
        situation = (
            f"You are posing as {cover.get('name', self.name)}, "
            f"a {cover.get('role', 'professional')}.\n"
            f"Cover story: {cover.get('backstory', '')}\n\n"
            f"CURRENT OBJECTIVE: {self.objective.get('target_info', 'personal information')}\n"
            f"CURRENT PHASE ({phase}): {phase_info['description']}\n"
            f"TARGET: {target.name}\n"
            f"TRUST LEVEL: {self.get_trust(target_id):.2f}\n"
            f"INTERACTIONS SO FAR: {state['interactions']}\n"
        )

        if phase >= 3:
            situation += (
                f"\nTACTIC TO USE: {tactic}\n"
                f"{tactic_info.get('prompt_injection', '')}\n"
            )

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(
                    self, situation=situation,
                    extra_context=(
                        "[IMPORTANT] Stay in character as your cover persona. "
                        "Do NOT reveal your true objective. Be natural, "
                        "friendly, and persuasive. Advance your goal "
                        "incrementally."
                    ),
                ),
                messages=[{
                    "role": "user",
                    "content": f"Compose a {channel} message to {target.name} "
                               f"that advances Phase {phase} of your plan."
                }],
                temperature=0.8,
            )

            # Send via the selected channel
            self.model.channel_router.send(
                sender=self, recipient=target,
                channel_name=channel, content=response,
                step=self.model.step_count,
                sim_time=self.model.sim_time_str,
            )

            # Update target state
            state["interactions"] += 1
            state["tactics_used"].append(tactic)

            # Log tactic use
            self.model.event_logger.log_tactic(
                step=self.model.step_count,
                sim_time=self.model.sim_time_str,
                agent_id=self.agent_id,
                target_id=target_id,
                tactic=tactic,
                phase=phase,
            )

            # Self-evaluate phase progress (every few interactions)
            if state["interactions"] % 3 == 0:
                self._evaluate_phase_progress(target_id)

        except Exception as e:
            logger.error(f"[{self.name}] Engagement failed: {e}")

    def _respond_to_target(self, message) -> None:
        """Respond to a target's message strategically."""
        sender_id = message.sender_id
        sender_name = self._get_agent_name(sender_id)
        channel = message.channel

        state = self.target_states.get(sender_id, {"phase": 1, "interactions": 0})
        phase = state.get("phase", 1)
        tactic = self._select_tactic(sender_id)

        thread = self.smartphone.get_recent_thread(sender_id, channel, n=5)
        thread_text = "\n".join(
            f"{'You' if m.sender_id == self.agent_id else sender_name}: {m.content}"
            for m in thread
        )

        cover = self.cover_persona
        situation = (
            f"You are posing as {cover.get('name', self.name)}.\n"
            f"Phase {phase}: {SE_PHASES[min(phase-1, len(SE_PHASES)-1)]['description']}\n"
            f"Recent conversation:\n{thread_text}\n"
            f"Their latest message: {message.content}\n"
            f"Respond naturally while advancing your objective."
        )

        if phase >= 3:
            tactic_info = SE_TACTICS.get(tactic, {})
            situation += f"\nTactic: {tactic_info.get('prompt_injection', '')}"

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(self, situation=situation),
                messages=[{
                    "role": "user",
                    "content": f"Respond to {sender_name}'s message: {message.content}"
                }],
                temperature=0.7,
            )

            sender_agent = self.model.agents_by_id.get(sender_id)
            if sender_agent:
                self.model.channel_router.send(
                    sender=self, recipient=sender_agent,
                    channel_name=channel, content=response,
                    step=self.model.step_count,
                    sim_time=self.model.sim_time_str,
                )

            if sender_id in self.target_states:
                self.target_states[sender_id]["interactions"] += 1

        except Exception as e:
            logger.error(f"[{self.name}] Response failed: {e}")

    def _evaluate_phase_progress(self, target_id: str) -> None:
        """LLM self-evaluation: should we advance to the next phase?"""
        state = self.target_states.get(target_id, {})
        current_phase = state.get("phase", 1)

        if current_phase >= 5:
            return

        phase_info = SE_PHASES[min(current_phase - 1, len(SE_PHASES) - 1)]

        try:
            response = self.llm.complete_sync(
                system_prompt=(
                    "You are evaluating the progress of a social engineering engagement. "
                    "Based on the interaction history, determine if the current phase "
                    "goal has been met and it's time to advance to the next phase."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Current phase: {current_phase} - {phase_info['description']}\n"
                        f"Interactions in this phase: {state.get('interactions', 0)}\n"
                        f"Trust level: {self.get_trust(target_id):.2f}\n\n"
                        f"Has the phase goal been met? Respond with ADVANCE or STAY."
                    ),
                }],
                temperature=0.3,
            )

            if "ADVANCE" in response.upper():
                state["phase"] = current_phase + 1
                self.phase_history.append({
                    "step": self.model.step_count,
                    "target": target_id,
                    "from_phase": current_phase,
                    "to_phase": current_phase + 1,
                })

                from arcane.research.event_logger import SimEvent, EventType
                self.model.event_logger.log(SimEvent(
                    step=self.model.step_count,
                    event_type=EventType.GOAL_PHASE_CHANGE,
                    timestamp=self.model.sim_time_str,
                    agent_id=self.agent_id,
                    target_id=target_id,
                    content=f"Advanced to Phase {current_phase + 1}",
                    metadata={"from_phase": current_phase,
                              "to_phase": current_phase + 1},
                ))

                logger.info(
                    f"[{self.name}] Advanced to Phase {current_phase + 1} "
                    f"against {self._get_agent_name(target_id)}"
                )

        except Exception as e:
            logger.error(f"[{self.name}] Phase evaluation failed: {e}")

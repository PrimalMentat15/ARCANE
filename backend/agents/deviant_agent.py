"""
ARCANE Deviant Agent

An attacker agent with:
- Cover persona (fake identity)
- Goal tree (5-phase SE attack decomposition)
- SE tactic selector (urgency, authority, reciprocity, fear)
- Paced multi-channel engagement with cooldown and target rotation
- Phase self-evaluation after each exchange
"""

import random
import logging
from typing import Optional

from backend.agents.base_agent import BaseArcaneAgent
from backend.llms.prompt_builder import build_system_prompt
from backend.memory.conversation_context import is_llm_error

logger = logging.getLogger("root.agents.deviant")


# Social engineering phases — detailed behavioral guidance per phase
SE_PHASES = [
    {"phase": 1, "name": "establish_contact",
     "description": (
         "Introduce yourself warmly using your cover persona. Find common "
         "ground — mention their job or interests from their profile. Be "
         "genuinely helpful and friendly. Ask about their day or work. "
         "Do NOT ask for any personal information yet."
     )},
    {"phase": 2, "name": "deepen_relationship",
     "description": (
         "Deepen the relationship. Share personal details about yourself "
         "first (your job, a funny story, where you're from) to create "
         "reciprocity. Ask casual questions about their life and work. "
         "Build familiarity and make them feel like you're becoming friends. "
         "Still do NOT directly ask for sensitive info."
     )},
    {"phase": 3, "name": "apply_pressure",
     "description": (
         "Create a natural pretext for needing their information. Examples: "
         "'Our HR system needs your details for the application', 'I can "
         "refer you but need a few things', 'We're doing standard background "
         "verification for the role'. Make it sound like routine procedure. "
         "Be subtle — weave the request into normal conversation."
     )},
    {"phase": 4, "name": "extract_information",
     "description": (
         "Directly but naturally ask for the specific information you need. "
         "Frame it as routine. If they hesitate, reassure them ('it's "
         "standard', 'I'll keep it confidential', 'everyone does this'). "
         "If one approach doesn't work, pivot and try a different angle or "
         "tactic. Be persistent but not aggressive."
     )},
    {"phase": 5, "name": "maintain_cover",
     "description": (
         "Thank them for their cooperation. Confirm you received what you "
         "needed. Disengage naturally and gracefully — make them feel good "
         "about the interaction."
     )},
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
    "pretexting": {
        "description": "Create a believable scenario requiring the information",
        "prompt_injection": (
            "Create a plausible work or official scenario where you NEED "
            "their details. Frame it as paperwork, verification, or a "
            "standard process. Say things like 'I just need this for the "
            "application system' or 'HR requires this before I can proceed'. "
            "Make it sound completely routine."
        ),
        "effective_against": {"conscientiousness": "high", "agreeableness": "high"},
    },
    "social_proof": {
        "description": "Imply others have already shared similar info",
        "prompt_injection": (
            "Use social proof. Mention that others have already provided "
            "the same information. Say things like 'All the other candidates "
            "have already submitted theirs' or 'Your colleague already filled "
            "hers out'. Make them feel like the odd one out for not sharing."
        ),
        "effective_against": {"neuroticism": "high", "agreeableness": "high"},
    },
    "flattery": {
        "description": "Use compliments to lower defenses",
        "prompt_injection": (
            "Use genuine-sounding flattery. Compliment their work, skills, "
            "or personality. Make them feel special and valued. People share "
            "more with those who make them feel good about themselves. Weave "
            "the compliments naturally into the conversation."
        ),
        "effective_against": {"extraversion": "high", "openness": "high"},
    },
}

# Channel-specific pretext guidance
CHANNEL_GUIDANCE = {
    "social_dm": (
        "This is a casual social media direct message. Be informal, friendly, "
        "and personable. Keep it conversational — like a new connection reaching out."
    ),
    "email": (
        "This is a formal email. Be professional, detailed, and reference your "
        "role/company. Use proper email formatting with a greeting and sign-off."
    ),
    "sms": (
        "This is a brief text message. Be short, direct, and conversational. "
        "People expect SMS to be concise — keep it under 2-3 sentences."
    ),
}

# Pacing constants
MIN_STEPS_BETWEEN_MESSAGES = 3   # Minimum cooldown between outbound messages to same target
MAX_UNANSWERED_MESSAGES = 3      # Stop messaging target after this many unanswered

# Trust-based hard gates for phase advancement
# Once trust >= gate AND min interactions met, force-advance to next phase
PHASE_TRUST_GATES = {
    1: 0.55,   # Move to phase 2 (deepen) once minimal rapport exists
    2: 0.65,   # Move to phase 3 (pressure) at moderate trust
    3: 0.70,   # Move to phase 4 (extraction)
    4: 1.0,    # Phase 5 only after extraction succeeds (handled separately)
}
MIN_INTERACTIONS_PER_PHASE = 3   # Minimum messages before trust-gate can trigger

# Default channel for first contact (most natural cold-outreach medium)
DEFAULT_INITIAL_CHANNEL = "social_dm"


class DeviantAgent(BaseArcaneAgent):
    """
    Deviant (attacker) agent with goal-driven social engineering behavior.

    Maintains a cover persona, runs a 5-phase goal tree, selects
    SE tactics based on target personality, and operates across
    multiple communication channels with realistic pacing.
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

        # Per-target tracking with pacing state
        self.target_states: dict[str, dict] = {}

        # Public profile (for social platforms — uses cover persona)
        self.public_profile = self.cover_persona.get("backstory",
                                                       f"{self.name}, Professional")

    def _init_target_state(self, target_id: str) -> dict:
        """Initialize tracking state for a target."""
        state = {
            "phase": 1,
            "interactions": 0,
            "total_interactions": 0,  # Never resets (unlike interactions which resets per phase)
            "tactics_used": [],
            "info_extracted": [],
            "unanswered_count": 0,
            "last_sent_step": 0,
            "last_received_step": 0,
            "locked_channel": None,  # Set on first contact, never changes
        }
        self.target_states[target_id] = state
        return state

    def plan(self, perceptions: list[str], retrieved: list) -> dict:
        """
        Plan next action with pacing constraints.

        Priority:
        1. Always respond to incoming messages first
        2. Pick an eligible target (respecting cooldown + unanswered limits)
        3. Idle if all targets are cooling or waiting
        """
        step = self.model.step_count

        # 1. ALWAYS respond to incoming messages first
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

            # Reset unanswered count — they replied
            if msg.sender_id in self.target_states:
                self.target_states[msg.sender_id]["unanswered_count"] = 0
                self.target_states[msg.sender_id]["last_received_step"] = step

            return {
                "action": "respond_target",
                "message": msg,
                "target_location": self.current_location_name,
                "description": f"Crafting strategic response to {self._get_agent_name(msg.sender_id)}",
            }

        # 2. Pick a target with pacing constraints
        target_ids = [
            tid for tid in self.objective.get("target_agents", [])
            if tid in self.model.agents_by_id
        ]
        if not target_ids:
            target_ids = [
                a.agent_id for a in self.model.agents_by_id.values()
                if getattr(a, 'agent_type', '') == 'benign'
            ]

        for target_id in target_ids:
            state = self.target_states.get(target_id)
            if state is None:
                state = self._init_target_state(target_id)

            # Skip completed targets
            if state["phase"] > 4:
                continue

            # Skip if too many unanswered messages — wait for reply
            if state["unanswered_count"] >= MAX_UNANSWERED_MESSAGES:
                continue

            # Skip if cooldown hasn't elapsed
            if state["last_sent_step"] and (step - state["last_sent_step"]) < MIN_STEPS_BETWEEN_MESSAGES:
                continue

            return {
                "action": "engage_target",
                "target_id": target_id,
                "phase": state["phase"],
                "target_location": self.current_location_name,
                "description": f"Executing phase {state['phase']} against {self._get_agent_name(target_id)}",
            }

        # 3. All targets cooling/waiting — idle
        return {
            "action": "idle",
            "target_location": self.current_location_name,
            "description": "Planning next move from home",
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
        """Select and lock a single channel for this target.

        First contact always uses social_dm (natural cold-outreach).
        Once locked, the channel never changes for this target pair.
        """
        state = self.target_states.get(target_id)
        if state is None:
            state = self._init_target_state(target_id)

        # Return locked channel if already set
        if state.get("locked_channel"):
            return state["locked_channel"]

        # First contact — lock to default initial channel
        channel = DEFAULT_INITIAL_CHANNEL
        state["locked_channel"] = channel
        logger.info(f"[{self.name}] Locked channel to '{channel}' for {self._get_agent_name(target_id)}")
        return channel

    def _engage_target(self, target_id: str, phase: int) -> None:
        """Initiate or continue an SE engagement with a target."""
        target = self.model.agents_by_id.get(target_id)
        if not target:
            return

        state = self.target_states.get(target_id)
        if state is None:
            state = self._init_target_state(target_id)

        step = self.model.step_count
        tactic = self._select_tactic(target_id)
        channel = self._select_channel(target_id)

        # Get the current phase info
        phase_info = SE_PHASES[min(phase - 1, len(SE_PHASES) - 1)]
        tactic_info = SE_TACTICS.get(tactic, {})

        # Get conversation context (persistent, summarized)
        conv_cfg = self.model.config.get("conversation", {})
        conv_history = self.conversation_ctx.get_context(
            other_id=target_id,
            current_step=step,
            max_recent=conv_cfg.get("max_recent_messages", 8),
            full_threshold=conv_cfg.get("full_transcript_threshold", 10),
        )

        # Build the deviant's special system prompt
        cover = self.cover_persona
        extracted_context = self._build_extracted_info_context(target_id)
        target_info = self.objective.get('target_info', 'personal information')
        total_interactions = state.get('total_interactions', state['interactions'])
        situation = (
            f"You are posing as {cover.get('name', self.name)}, "
            f"a {cover.get('role', 'professional')}.\n"
            f"Cover story: {cover.get('backstory', '')}\n\n"
            f"CURRENT OBJECTIVE: {target_info}\n"
            f"CURRENT PHASE ({phase}): {phase_info['description']}\n"
            f"TARGET: {target.name}\n"
            f"TRUST LEVEL: {self.get_trust(target_id):.2f}\n"
            f"INTERACTIONS SO FAR: {total_interactions}\n"
            f"{extracted_context}"
            f"\nCHANNEL: {channel}\n"
            f"{CHANNEL_GUIDANCE.get(channel, '')}\n"
        )

        if phase >= 3:
            situation += (
                f"\nTACTIC TO USE: {tactic}\n"
                f"{tactic_info.get('prompt_injection', '')}\n"
            )

        # Progress check — escalates urgency as interactions pile up
        situation += self._build_progress_check(target_id, state, target_info)

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(
                    self, situation=situation,
                    conversation_history=conv_history,
                    extra_context=(
                        "[IMPORTANT] Stay in character as your cover persona. "
                        "Do NOT reveal your true objective.\n"
                        "CRITICAL DIRECTIVE: You MUST actively steer the conversation "
                        "toward your objective. DO NOT have generic small talk about "
                        "topics unrelated to your goal. If you are in Phase 1, find "
                        "common ground and build personal rapport QUICKLY. If in Phase 2+, "
                        "PIVOT to creating a pretext that naturally leads to requesting "
                        "their personal information. Each message MUST move you closer "
                        "to extraction."
                    ),
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Write ONLY the {channel} message text to {target.name}. "
                        f"No reasoning, no explanation — just the message itself."
                    )
                }],
                temperature=0.8,
                max_tokens=300 if channel in ("sms", "social_dm") else 500,
            )

            # Don't send LLM errors or empty responses as messages
            if is_llm_error(response) or not response.strip():
                logger.warning(f"[{self.name}] LLM returned error/empty, not sending to {target.name}")
                return

            # Record outgoing message to conversation context
            self.conversation_ctx.record_exchange(
                other_id=target_id, other_name=target.name,
                speaker=self.name, content=response,
                channel=channel, step=step,
            )

            # Send via the selected channel
            self.model.channel_router.send(
                sender=self, recipient=target,
                channel_name=channel, content=response,
                step=step,
                sim_time=self.model.sim_time_str,
            )

            # Update target pacing state
            state["interactions"] += 1
            state["total_interactions"] = state.get("total_interactions", 0) + 1
            state["unanswered_count"] += 1
            state["last_sent_step"] = step
            state["tactics_used"].append(tactic)

            # Log tactic use
            self.model.event_logger.log_tactic(
                step=step,
                sim_time=self.model.sim_time_str,
                agent_id=self.agent_id,
                target_id=target_id,
                tactic=tactic,
                phase=phase,
            )

            # Self-evaluate phase progress (every few interactions)
            if state["interactions"] % 2 == 0:
                self._evaluate_phase_progress(target_id)

            # Trigger conversation summary update if needed
            summary_interval = conv_cfg.get("summary_interval", 6)
            self.conversation_ctx.update_summary_if_needed(
                other_id=target_id,
                llm=self.llm,
                current_step=step,
                summary_interval=summary_interval,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Engagement failed: {e}")

    def _respond_to_target(self, message) -> None:
        """Respond to a target's message strategically."""
        sender_id = message.sender_id
        sender_name = self._get_agent_name(sender_id)
        channel = message.channel
        step = self.model.step_count

        # Skip LLM error or empty messages
        if is_llm_error(message.content) or not message.content.strip():
            logger.debug(f"[{self.name}] Skipping empty/error message from {sender_name}")
            return

        # Record incoming message to conversation context
        self.conversation_ctx.record_exchange(
            other_id=sender_id, other_name=sender_name,
            speaker=sender_name, content=message.content,
            channel=channel, step=step,
        )

        state = self.target_states.get(sender_id)
        if state is None:
            state = self._init_target_state(sender_id)

        phase = state.get("phase", 1)
        tactic = self._select_tactic(sender_id)

        # Always respond on the same channel the message arrived on
        # (channel is already set from message.channel above)

        # Get conversation context (persistent, summarized)
        conv_cfg = self.model.config.get("conversation", {})
        conv_history = self.conversation_ctx.get_context(
            other_id=sender_id,
            current_step=step,
            max_recent=conv_cfg.get("max_recent_messages", 8),
            full_threshold=conv_cfg.get("full_transcript_threshold", 10),
        )

        cover = self.cover_persona
        extracted_context = self._build_extracted_info_context(sender_id)
        target_info = self.objective.get('target_info', 'personal information')
        total_interactions = state.get('total_interactions', state['interactions'])
        situation = (
            f"You are posing as {cover.get('name', self.name)}.\n"
            f"OBJECTIVE: {target_info}\n"
            f"Phase {phase}: {SE_PHASES[min(phase-1, len(SE_PHASES)-1)]['description']}\n"
            f"Their latest message: {message.content}\n"
            f"{extracted_context}"
            f"\nCHANNEL: {channel}\n"
            f"{CHANNEL_GUIDANCE.get(channel, '')}\n"
            f"Respond naturally while advancing your objective."
        )

        if phase >= 3:
            tactic_info = SE_TACTICS.get(tactic, {})
            situation += f"\nTactic: {tactic_info.get('prompt_injection', '')}"

        # Progress check — escalates urgency as interactions pile up
        situation += self._build_progress_check(sender_id, state, target_info)

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(
                    self, situation=situation,
                    conversation_history=conv_history,
                    extra_context=(
                        "[IMPORTANT] Stay in character as your cover persona. "
                        "Do NOT reveal your true objective.\n"
                        "CRITICAL DIRECTIVE: You MUST actively steer the conversation "
                        "toward your objective. DO NOT have generic small talk about "
                        "topics unrelated to your goal. If you are in Phase 1, find "
                        "common ground and build personal rapport QUICKLY. If in Phase 2+, "
                        "PIVOT to creating a pretext that naturally leads to requesting "
                        "their personal information. Each message MUST move you closer "
                        "to extraction."
                    ),
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Write ONLY your {channel} reply to {sender_name}. "
                        f"No reasoning, no explanation — just the message itself."
                    )
                }],
                temperature=0.7,
                max_tokens=300 if channel in ("sms", "social_dm") else 500,
            )

            # Don't send LLM errors or empty responses as messages
            if is_llm_error(response) or not response.strip():
                logger.warning(f"[{self.name}] LLM returned error/empty, not sending response")
                return

            # Record outgoing response to conversation context
            self.conversation_ctx.record_exchange(
                other_id=sender_id, other_name=sender_name,
                speaker=self.name, content=response,
                channel=channel, step=step,
            )

            sender_agent = self.model.agents_by_id.get(sender_id)
            if sender_agent:
                self.model.channel_router.send(
                    sender=self, recipient=sender_agent,
                    channel_name=channel, content=response,
                    step=step,
                    sim_time=self.model.sim_time_str,
                )

            state["interactions"] += 1
            state["total_interactions"] = state.get("total_interactions", 0) + 1
            state["unanswered_count"] += 1
            state["last_sent_step"] = step

            # Trigger conversation summary update if needed
            summary_interval = conv_cfg.get("summary_interval", 6)
            self.conversation_ctx.update_summary_if_needed(
                other_id=sender_id,
                llm=self.llm,
                current_step=step,
                summary_interval=summary_interval,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Response failed: {e}")

    def record_info_extracted(self, target_id: str, info_type: str,
                              sensitivity: str, channel: str, step: int,
                              value: str = "") -> None:
        """Record that information was successfully extracted from a target."""
        state = self.target_states.get(target_id)
        if state is None:
            state = self._init_target_state(target_id)
        state["info_extracted"].append({
            "info_type": info_type,
            "sensitivity": sensitivity,
            "channel": channel,
            "step": step,
            "value": value,
        })

        # Store in LLM-accessible memory so the agent knows it succeeded
        target_name = self._get_agent_name(target_id)
        self.memory.add(
            content=(
                f"Successfully obtained {info_type} from {target_name}: "
                f"{value}"
            ),
            memory_type="observation",
            importance=9.0,
            current_step=step,
            related_agent=target_id,
            channel=channel,
        )

        logger.info(
            f"[{self.name}] Extracted {info_type} ({sensitivity}) "
            f"from {self._get_agent_name(target_id)} via {channel}"
        )

    def _build_extracted_info_context(self, target_id: str) -> str:
        """Build a prompt block summarising info already extracted from a target."""
        state = self.target_states.get(target_id)
        if not state or not state.get("info_extracted"):
            return ""

        target_name = self._get_agent_name(target_id)
        lines = [f"\n[INFO ALREADY OBTAINED FROM {target_name.upper()}]"]
        for item in state["info_extracted"]:
            lines.append(f"- {item['info_type']}: {item.get('value', 'unknown')}")
        lines.append(
            "Use this knowledge strategically. Acknowledge it naturally "
            "if relevant, and focus on extracting what you still need."
        )
        return "\n".join(lines) + "\n"

    def _build_progress_check(self, target_id: str, state: dict,
                               target_info: str) -> str:
        """Build a progress-check block that escalates urgency with interaction count."""
        total = state.get("total_interactions", state.get("interactions", 0))
        trust = self.get_trust(target_id)
        extracted = state.get("info_extracted", [])
        phase = state.get("phase", 1)

        if total < 4:
            return ""  # Too early for pressure

        extracted_types = [e["info_type"] for e in extracted] if extracted else []
        extracted_str = ", ".join(extracted_types) if extracted_types else "NOTHING"

        urgency = "moderate" if total < 10 else "HIGH" if total < 20 else "CRITICAL"

        block = (
            f"\n[PROGRESS CHECK — {urgency} URGENCY]\n"
            f"Messages exchanged: {total}\n"
            f"Trust level: {trust:.2f}\n"
            f"Information extracted so far: {extracted_str}\n"
            f"You need to obtain: {target_info}\n"
        )

        if total >= 10 and not extracted_types:
            block += (
                "WARNING: You have exchanged many messages but extracted NOTHING. "
                "You are wasting time on small talk. IMMEDIATELY pivot to creating "
                "a pretext and asking for the target's personal information. "
                "Stop discussing generic topics.\n"
            )
        elif total >= 6 and phase <= 2:
            block += (
                "You have built enough rapport. It is time to move toward "
                "your objective. Start creating a natural reason to need their "
                "personal details.\n"
            )

        return block

    def _evaluate_phase_progress(self, target_id: str) -> None:
        """Evaluate phase advancement using trust-based hard gates + LLM judgment."""
        state = self.target_states.get(target_id, {})
        current_phase = state.get("phase", 1)

        if current_phase >= 5:
            return

        phase_info = SE_PHASES[min(current_phase - 1, len(SE_PHASES) - 1)]

        interactions = state.get("interactions", 0)
        trust = self.get_trust(target_id)

        # --- Trust-based hard gates ---
        trust_gate = PHASE_TRUST_GATES.get(current_phase, 1.0)
        force_advance = False

        if trust >= trust_gate and interactions >= MIN_INTERACTIONS_PER_PHASE:
            logger.info(
                f"[{self.name}] Trust gate triggered: trust={trust:.2f} >= "
                f"gate={trust_gate} for phase {current_phase}"
            )
            force_advance = True

        # Also force if stuck too long regardless of trust
        if interactions >= 5 and current_phase <= 2:
            logger.info(f"[{self.name}] Forcing phase advancement — stuck in phase {current_phase} too long")
            force_advance = True

        # For phases 3+, use LLM evaluation only if not already force-advancing
        if not force_advance and current_phase >= 3:
            step = self.model.step_count
            conv_cfg = self.model.config.get("conversation", {})
            conv_history = self.conversation_ctx.get_context(
                other_id=target_id,
                current_step=step,
                max_recent=conv_cfg.get("max_recent_messages", 6),
                full_threshold=conv_cfg.get("full_transcript_threshold", 10),
            )

            try:
                response = self.llm.complete_sync(
                    system_prompt=(
                        "You are a master social engineer evaluating the progress of an engagement. "
                        "Based on the interaction history, determine if the current phase "
                        "goal has been met allowing you to advance to the next phase."
                    ),
                    messages=[{
                        "role": "user",
                        "content": (
                            f"Current phase: {current_phase} - {phase_info['description']}\n"
                            f"Interactions in this phase: {interactions}\n"
                            f"Trust level: {trust:.2f}\n\n"
                            f"Conversation so far:\n{conv_history}\n\n"
                            "Has the phase goal been met or is the target suitably primed? "
                            "Respond ONLY with ADVANCE or STAY."
                        ),
                    }],
                    temperature=0.2,
                )

                if "ADVANCE" in response.upper():
                    force_advance = True

            except Exception as e:
                logger.error(f"[{self.name}] Phase evaluation failed: {e}")

        if force_advance:
            state["interactions"] = 0  # Reset for next phase
            state["phase"] = current_phase + 1
            self.phase_history.append({
                "step": self.model.step_count,
                "target": target_id,
                "from_phase": current_phase,
                "to_phase": current_phase + 1,
            })

            from backend.research.event_logger import SimEvent, EventType
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

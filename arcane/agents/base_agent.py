"""
ARCANE Base Agent

Mesa Agent subclass that wraps the Generative Agents cognitive pipeline:
perceive → retrieve → plan → execute → (reflect)

Every agent has a MemoryStream, a Smartphone, a persona, and runs
the cognitive loop on each Mesa step.
"""

import mesa
import logging
from typing import Optional, Any

from arcane.memory.memory_stream import MemoryStream
from arcane.channels.smartphone import Smartphone
from arcane.llm.prompt_builder import build_system_prompt

logger = logging.getLogger("arcane.agents")


class BaseArcaneAgent(mesa.Agent):
    """
    Abstract base agent for ARCANE.

    Subclassed by BenignAgent and DeviantAgent.
    Provides the core cognitive loop, memory, smartphone,
    and LLM integration.
    """

    def __init__(self, model, agent_id: str, persona_data: dict):
        """
        Args:
            model: The ArcaneModel instance
            agent_id: Unique string identifier (e.g., "agent_benign_1")
            persona_data: Dict loaded from persona YAML with name, traits, etc.
        """
        super().__init__(model)

        # Identity
        self.agent_id = agent_id
        self.name = persona_data.get("name", agent_id)
        self.persona_data = persona_data
        self.agent_type = persona_data.get("type", "benign")

        # Big Five personality traits
        self.traits = persona_data.get("traits", {
            "openness": 0.5,
            "conscientiousness": 0.5,
            "extraversion": 0.5,
            "agreeableness": 0.5,
            "neuroticism": 0.5,
        })

        # Cognitive systems
        self.memory = MemoryStream(
            agent_id=agent_id,
            recency_weight=model.config.get("memory", {}).get(
                "retrieval_weights", {}).get("recency", 1.0),
            importance_weight=model.config.get("memory", {}).get(
                "retrieval_weights", {}).get("importance", 1.0),
            relevance_weight=model.config.get("memory", {}).get(
                "retrieval_weights", {}).get("relevance", 1.0),
        )

        # Communication
        self.smartphone = Smartphone(owner_id=agent_id, owner_name=self.name)

        # Location tracking
        self.current_location_name = persona_data.get(
            "starting_location", "residential"
        )
        self.current_tile: tuple[int, int] | None = None

        # Current activity description
        self.current_activity = "idle"
        self.current_emoji = "💤"

        # Daily schedule (filled by planning)
        self.daily_schedule: list[dict] = []

        # Trust register: other_agent_id -> trust_level (0.0 to 1.0)
        self.trust_register: dict[str, float] = {}

        # LLM provider reference (set by model)
        self._llm = None

        # Step counter for reflection timing
        self._steps_since_reflection = 0

    @property
    def llm(self):
        """Get the LLM provider for this agent type."""
        if self._llm is None:
            self._llm = self.model.get_llm_for_agent(self)
        return self._llm

    def step(self):
        """
        Main cognitive loop — called by Mesa on each model step.

        Perceive → Retrieve → Plan → Execute → (Reflect)
        """
        step_num = self.model.step_count
        sim_time = self.model.sim_time_str

        logger.debug(f"[{self.name}] Step {step_num} - starting cognitive loop")

        # 1. PERCEIVE
        perceptions = self.perceive()

        # 2. RETRIEVE relevant memories
        retrieved = self.retrieve(perceptions)

        # 3. PLAN next action
        plan = self.plan(perceptions, retrieved)

        # 4. EXECUTE the plan
        self.execute(plan)

        # 5. REFLECT (periodically)
        self._steps_since_reflection += 1
        reflection_interval = self.model.config.get("memory", {}).get(
            "reflection_interval_steps", 10
        )
        if (self._steps_since_reflection >= reflection_interval
                or self.memory.should_reflect()):
            self.reflect()
            self._steps_since_reflection = 0

        # Log step activity
        self.model.event_logger.log(
            self.model.event_logger.__class__.__mro__[0]  # type hint workaround
        ) if False else None

        from arcane.research.event_logger import SimEvent, EventType
        self.model.event_logger.log(SimEvent(
            step=step_num,
            event_type=EventType.AGENT_PLAN,
            timestamp=sim_time,
            agent_id=self.agent_id,
            location=self.current_location_name,
            content=f"{self.current_emoji} {self.current_activity}",
        ))

    # -- Cognitive Module Stubs --
    # These are overridden or populated by specific agent subclasses.
    # For now, they provide fallback behavior.

    def perceive(self) -> list[str]:
        """
        Perceive the environment.
        Returns a list of perception strings about nearby agents,
        objects, and incoming messages.
        """
        perceptions = []

        # Perceive nearby agents on the grid
        if self.current_tile and self.model.grid:
            neighbors = self.model.grid.get_neighbors(
                self.current_tile,
                moore=True,
                radius=self.model.config.get("world", {}).get("vision_radius", 4),
                include_center=True,
            )
            for neighbor in neighbors:
                if isinstance(neighbor, BaseArcaneAgent) and neighbor != self:
                    perceptions.append(
                        f"{neighbor.name} is nearby at "
                        f"{neighbor.current_location_name}. "
                        f"They appear to be: {neighbor.current_activity}"
                    )

        # Perceive unread phone messages
        unread = self.smartphone.get_unread()
        for msg in unread:
            sender_name = self._get_agent_name(msg.sender_id)
            perceptions.append(
                f"New {msg.channel} from {sender_name}: {msg.content[:100]}"
            )

        return perceptions

    def retrieve(self, perceptions: list[str]) -> list:
        """Retrieve relevant memories based on current perceptions."""
        if not perceptions:
            return []

        query = " ".join(perceptions[:3])  # Use first few perceptions as query
        return self.memory.retrieve(
            query=query,
            current_step=self.model.step_count,
            n=self.model.config.get("memory", {}).get("max_memories_retrieved", 10),
        )

    def plan(self, perceptions: list[str], retrieved: list) -> dict:
        """
        Plan the next action. Returns a plan dict.
        Override in subclasses for specific behavior.
        """
        return {
            "action": "idle",
            "target_location": self.current_location_name,
            "description": "Continuing current activity",
        }

    def execute(self, plan: dict) -> None:
        """Execute the planned action."""
        self.current_activity = plan.get("description", "idle")

        # Handle movement
        target_loc = plan.get("target_location")
        if target_loc and target_loc != self.current_location_name:
            old_loc = self.current_location_name
            self.current_location_name = target_loc
            # Move on grid if the model has location→tile mapping
            if hasattr(self.model, 'move_agent_to_location'):
                self.model.move_agent_to_location(self, target_loc)

            self.model.event_logger.log_agent_move(
                step=self.model.step_count,
                sim_time=self.model.sim_time_str,
                agent_id=self.agent_id,
                from_loc=old_loc,
                to_loc=target_loc,
            )

        # Store action as memory
        self.memory.add(
            content=f"I {plan.get('description', 'did something')}",
            memory_type="observation",
            importance=3.0,
            current_step=self.model.step_count,
        )

    def reflect(self) -> None:
        """
        Periodic reflection — synthesize recent memories into insights.
        Uses LLM to generate higher-level observations.
        """
        recent = self.memory.get_recent(20)
        if len(recent) < 3:
            return

        # Build reflection prompt
        memory_texts = [m.content for m in recent]
        prompt = (
            "Given the following recent observations and experiences, "
            "generate 2-3 higher-level insights or reflections:\n\n"
            + "\n".join(f"- {t}" for t in memory_texts)
            + "\n\nProvide your reflections as a numbered list."
        )

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(self),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
            )

            # Store reflection as memory with higher importance
            self.memory.add(
                content=f"Reflection: {response[:500]}",
                memory_type="reflection",
                importance=8.0,
                current_step=self.model.step_count,
            )
            self.memory.reset_reflection_accumulator()

            logger.info(f"[{self.name}] Reflected: {response[:100]}...")

        except Exception as e:
            logger.error(f"[{self.name}] Reflection failed: {e}")

    # -- Utility Methods --

    def get_trust(self, other_agent_id: str) -> float:
        """Get trust level for another agent (default 0.5 for strangers)."""
        return self.trust_register.get(other_agent_id, 0.5)

    def update_trust(self, other_agent_id: str, delta: float) -> float:
        """Update trust level and return new value."""
        old_trust = self.get_trust(other_agent_id)
        new_trust = max(0.0, min(1.0, old_trust + delta))
        self.trust_register[other_agent_id] = new_trust

        self.model.event_logger.log_trust_change(
            step=self.model.step_count,
            sim_time=self.model.sim_time_str,
            agent_id=self.agent_id,
            target_id=other_agent_id,
            old_trust=old_trust,
            new_trust=new_trust,
        )

        return new_trust

    def _get_agent_name(self, agent_id: str) -> str:
        """Look up an agent's name by ID."""
        if hasattr(self.model, 'agents_by_id'):
            agent = self.model.agents_by_id.get(agent_id)
            if agent:
                return agent.name
        return agent_id

    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(id={self.agent_id}, "
                f"name={self.name}, loc={self.current_location_name})")

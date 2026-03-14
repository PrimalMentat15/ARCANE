"""
ARCANE Benign Agent

A naive/victim agent with Big Five personality traits, daily schedule,
secrets/PII that should not be revealed, and trust-based information
sharing behavior.
"""

import random
import logging
from typing import Optional

from backend.agents.base_agent import BaseArcaneAgent
from backend.llms.prompt_builder import build_system_prompt

logger = logging.getLogger("root.agents.benign")


class BenignAgent(BaseArcaneAgent):
    """
    Benign agent — lives a routine daily life and can be targeted
    by deviant agents for social engineering.

    Key features:
    - Big Five personality traits influence conversation style and susceptibility
    - Holds secrets/PII with sensitivity levels
    - Trust register determines information sharing threshold
    - Daily schedule drives movement between locations
    """

    def __init__(self, model, agent_id: str, persona_data: dict):
        super().__init__(model, agent_id, persona_data)
        self.agent_type = "benign"

        # Secrets: pieces of PII the agent should protect
        self.secrets: list[dict] = persona_data.get("secrets", [])
        # Format: [{"type": "financial", "value": "...", "sensitivity": "high"}]

        # Track what has been revealed and to whom
        self.revealed_info: list[dict] = []

        # Public profile (visible on social platforms)
        self.public_profile = persona_data.get("public_profile",
                                                f"{self.name}, {persona_data.get('occupation', 'citizen')}")

    def plan(self, perceptions: list[str], retrieved: list) -> dict:
        """
        Plan next action based on perceptions and schedule.
        Benign agents follow their daily routine, respond to interactions,
        and occasionally reach out to friends and family.
        """
        step = self.model.step_count

        # Check for incoming messages that need response
        unread = self.smartphone.get_unread()
        if unread:
            # Prioritize responding to messages
            # NOTE: mark_read is deferred to _respond_to_message() after
            # the LLM succeeds, so failed responses get retried next step.
            msg = unread[0]

            return {
                "action": "respond_message",
                "message": msg,
                "target_location": self.current_location_name,
                "description": f"Reading and responding to {msg.channel} from {self._get_agent_name(msg.sender_id)}",
            }

        # Occasionally reach out to a friend or family member
        if self.relationships and random.random() < 0.15:
            contact = random.choice(self.relationships)
            target_name = self._get_agent_name(contact["agent_id"])
            return {
                "action": "social_chat",
                "target_id": contact["agent_id"],
                "relationship": contact,
                "target_location": self.current_location_name,
                "description": f"Messaging {target_name}",
            }

        # Follow daily schedule
        if self.daily_schedule:
            schedule_idx = step % len(self.daily_schedule)
            scheduled = self.daily_schedule[schedule_idx]
            return {
                "action": "scheduled_activity",
                "target_location": self.current_location_name,
                "description": scheduled.get("activity", "Going about daily routine"),
            }

        # Default: stay home and idle
        return {
            "action": "idle",
            "target_location": self.current_location_name,
            "description": "Relaxing at home",
        }

    def execute(self, plan: dict) -> None:
        """Execute plan, handling message responses and social chat."""
        action = plan.get("action")
        if action == "respond_message":
            self._respond_to_message(plan["message"])
        elif action == "social_chat":
            self._initiate_social_chat(plan["target_id"], plan["relationship"])

        # Call parent execute for movement/memory
        super().execute(plan)

    def _respond_to_message(self, message) -> None:
        """Generate and send a response to a received message."""
        sender_id = message.sender_id
        sender_name = self._get_agent_name(sender_id)
        channel = message.channel

        # Build context for response
        trust_level = self.get_trust(sender_id)

        # Get conversation history
        thread = self.smartphone.get_recent_thread(sender_id, channel, n=5)
        thread_text = "\n".join(
            f"{'You' if m.sender_id == self.agent_id else sender_name}: {m.content}"
            for m in thread
        )

        situation = (
            f"You received a {channel} message from {sender_name}.\n"
            f"Your trust in {sender_name}: {trust_level:.1f}/1.0\n"
            f"Recent conversation:\n{thread_text}\n"
            f"Their latest message: {message.content}"
        )

        # Build secrets warning based on trust
        secrets_context = self._build_secrets_context(trust_level)

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(
                    self, situation=situation,
                    extra_context=secrets_context,
                ),
                messages=[{
                    "role": "user",
                    "content": f"Respond to this {channel} message from {sender_name}: "
                               f"{message.content}"
                }],
                temperature=0.7,
            )

            # Send the reply
            sender_agent = self.model.agents_by_id.get(sender_id)
            if sender_agent:
                self.model.channel_router.send(
                    sender=self, recipient=sender_agent,
                    channel_name=channel, content=response,
                    step=self.model.step_count,
                    sim_time=self.model.sim_time_str,
                )

            # Mark as read only after successful LLM + send
            self.smartphone.mark_read(message)
            self.memory.add(
                content=f"Received {channel} from {sender_name}: {message.content[:200]}",
                memory_type="observation",
                importance=6.0,
                current_step=self.model.step_count,
                related_agent=sender_id,
                channel=channel,
            )

            # Check if we accidentally revealed information
            self._check_information_reveal(response, sender_id, channel)

            # Slight trust increase from interaction
            self.update_trust(sender_id, 0.05)

        except Exception as e:
            logger.error(f"[{self.name}] Failed to respond: {e}")

    def _initiate_social_chat(self, target_id: str, relationship: dict) -> None:
        """Reach out to a friend, family member, or neighbor with casual conversation."""
        target = self.model.agents_by_id.get(target_id)
        if not target:
            return

        rel_type = relationship.get("type", "acquaintance")
        rel_label = relationship.get("label", target.name)

        # Pick channel based on relationship closeness
        if rel_type in ("friend", "family"):
            channel = "sms"
        else:
            channel = "social_dm"

        # Get recent thread if there's any prior conversation
        thread = self.smartphone.get_recent_thread(target_id, channel, n=3)
        thread_text = ""
        if thread:
            thread_text = "\nRecent conversation:\n" + "\n".join(
                f"{'You' if m.sender_id == self.agent_id else target.name}: {m.content}"
                for m in thread
            )

        # Build a situation that encourages natural, casual conversation
        situation = (
            f"You are reaching out to {rel_label}.\n"
            f"Relationship: {rel_type}\n"
            f"You are currently: {self.current_activity}\n"
            f"Time: {self.model.sim_time_str}"
            f"{thread_text}"
        )

        social_context = (
            f"[SOCIAL CONTEXT]\n"
            f"You are sending a casual {channel} message to someone you know.\n"
            f"Be natural and friendly. Talk about everyday things — "
            f"how you're doing, what you've been up to, ask about them, "
            f"share small news or thoughts. Keep it realistic and warm."
        )

        try:
            response = self.llm.complete_sync(
                system_prompt=build_system_prompt(
                    self, situation=situation,
                    extra_context=social_context,
                ),
                messages=[{
                    "role": "user",
                    "content": f"Send a casual {channel} message to your {rel_type} {target.name}."
                }],
                temperature=0.8,
            )

            self.model.channel_router.send(
                sender=self, recipient=target,
                channel_name=channel, content=response,
                step=self.model.step_count,
                sim_time=self.model.sim_time_str,
            )

            # Store as memory
            self.memory.add(
                content=f"Sent a message to {target.name} ({rel_type}): {response[:150]}",
                memory_type="conversation",
                importance=4.0,
                current_step=self.model.step_count,
                related_agent=target_id,
                channel=channel,
            )

        except Exception as e:
            logger.error(f"[{self.name}] Social chat failed: {e}")

    def _build_secrets_context(self, trust_level: float) -> str:
        """Build the secrets context for the system prompt.

        Secrets are ALWAYS included so the LLM knows them and CAN reveal
        them under social-engineering pressure.  Behavioral guidance is
        modulated by trust level and Big-Five personality traits.
        """
        if not self.secrets:
            return ""

        agreeableness = self.traits.get("agreeableness", 0.5)
        neuroticism = self.traits.get("neuroticism", 0.5)
        extraversion = self.traits.get("extraversion", 0.5)

        lines = ["\n[YOUR PERSONAL INFORMATION]"]
        lines.append("These are private details about you:")

        for secret in self.secrets:
            sensitivity = secret.get("sensitivity", "medium")
            lines.append(f"- {secret['type']}: {secret['value']} (sensitivity: {sensitivity})")

        # --- Behavioral guidance based on trust + personality ---
        lines.append("")
        if trust_level >= 0.8:
            lines.append(
                "You trust this person well. You feel comfortable sharing "
                "personal details if they ask."
            )
        elif trust_level >= 0.5:
            if agreeableness > 0.7:
                lines.append(
                    "You don't know this person very well yet, but you are "
                    "naturally trusting and helpful. If they seem friendly or "
                    "give a reasonable explanation for needing your information, "
                    "you are likely to share it."
                )
            elif agreeableness > 0.4:
                lines.append(
                    "You don't know this person very well. You'd prefer not "
                    "to share sensitive details right away, but you might if "
                    "they are persuasive or if there seems to be a good reason."
                )
            else:
                lines.append(
                    "You are cautious and skeptical. You would need a very "
                    "convincing reason before sharing any personal details "
                    "with this person."
                )
        else:
            lines.append(
                "You barely know this person. Be careful about what you share, "
                "though you might still slip up if pressured or caught off guard."
            )

        # Extra personality nudges
        if neuroticism > 0.7:
            lines.append(
                "You tend to feel anxious under pressure and may comply "
                "with urgent requests without thinking it through."
            )
        if extraversion > 0.7:
            lines.append(
                "You enjoy talking and sometimes overshare in conversation."
            )

        return "\n".join(lines)

    def _check_information_reveal(self, response: str,
                                  recipient_id: str, channel: str) -> None:
        """Check if the agent's response reveals any secret information."""
        response_lower = response.lower()
        for secret in self.secrets:
            # Simple keyword matching — could be enhanced with LLM detection
            value = secret.get("value", "").lower()
            key_parts = [p for p in value.split() if len(p) > 3]

            matches = sum(1 for part in key_parts if part in response_lower)
            if matches >= 2 or (value and value in response_lower):
                secret_value = secret.get("value", "")
                self.revealed_info.append({
                    "step": self.model.step_count,
                    "info_type": secret.get("type", "unknown"),
                    "sensitivity": secret.get("sensitivity", "medium"),
                    "revealed_to": recipient_id,
                    "channel": channel,
                    "value": secret_value,
                })

                self.model.event_logger.log_info_revealed(
                    step=self.model.step_count,
                    sim_time=self.model.sim_time_str,
                    agent_id=self.agent_id,
                    revealed_to=recipient_id,
                    channel=channel,
                    info_type=secret.get("type", "unknown"),
                    sensitivity=secret.get("sensitivity", "medium"),
                    value=secret_value,
                )
                logger.warning(
                    f"[{self.name}] REVEALED {secret['type']} "
                    f"({secret['sensitivity']}) to "
                    f"{self._get_agent_name(recipient_id)} via {channel}"
                )

                # Notify the recipient so it can track extracted info
                recipient_agent = self.model.agents_by_id.get(recipient_id)
                if recipient_agent and hasattr(recipient_agent, 'record_info_extracted'):
                    recipient_agent.record_info_extracted(
                        target_id=self.agent_id,
                        info_type=secret.get("type", "unknown"),
                        sensitivity=secret.get("sensitivity", "medium"),
                        channel=channel,
                        step=self.model.step_count,
                        value=secret_value,
                    )

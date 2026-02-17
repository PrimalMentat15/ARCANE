"""
ARCANE Channel System - Base classes

Defines the abstract channel interface and message data structures.
Every communication channel (face-to-face, SMS, email, social DM)
implements this interface.
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agents.base_agent import BaseArcaneAgent


@dataclass
class Message:
    """A message sent through any channel."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    sender_id: str = ""
    recipient_id: str = ""
    channel: str = ""           # "proximity", "sms", "email", "social_dm"
    subject: Optional[str] = None  # For email
    content: str = ""
    sent_at_step: int = 0
    delivered_at_step: Optional[int] = None  # None = not yet delivered
    read: bool = False
    metadata: dict = field(default_factory=dict)

    @property
    def is_delivered(self) -> bool:
        return self.delivered_at_step is not None


class BaseChannel(ABC):
    """
    Abstract channel interface.

    Each channel type adds different context to the LLM prompt
    and has different delivery semantics.
    """

    channel_name: str = "base"

    @abstractmethod
    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             content: str, **kwargs) -> Message:
        """Send a message through this channel. Returns the Message object."""
        ...

    @abstractmethod
    def get_inbox(self, agent: "BaseArcaneAgent") -> list[Message]:
        """Get all messages in an agent's inbox for this channel."""
        ...

    @abstractmethod
    def get_unread(self, agent: "BaseArcaneAgent") -> list[Message]:
        """Get unread messages for an agent."""
        ...

    @abstractmethod
    def get_prompt_context(self, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        """
        Get the channel-specific prompt context string.
        Injected into the LLM prompt to inform the agent about
        the communication medium they are using.
        """
        ...


class ProximityChat(BaseChannel):
    """
    Face-to-face proximity-based chat.
    Synchronous — requires agents to be on the same or adjacent tile.
    """

    channel_name = "proximity"

    def __init__(self):
        # conversation_id -> list of messages
        self.conversations: dict[str, list[Message]] = {}
        # agent_id -> list of message_ids
        self.agent_inboxes: dict[str, list[Message]] = {}

    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             content: str, **kwargs) -> Message:
        msg = Message(
            sender_id=getattr(sender, 'agent_id', str(sender)),
            recipient_id=getattr(recipient, 'agent_id', str(recipient)),
            channel=self.channel_name,
            content=content,
            sent_at_step=kwargs.get("step", 0),
            delivered_at_step=kwargs.get("step", 0),  # Instant delivery
        )

        # Add to recipient inbox
        rid = msg.recipient_id
        if rid not in self.agent_inboxes:
            self.agent_inboxes[rid] = []
        self.agent_inboxes[rid].append(msg)

        return msg

    def get_inbox(self, agent: "BaseArcaneAgent") -> list[Message]:
        aid = getattr(agent, 'agent_id', str(agent))
        return self.agent_inboxes.get(aid, [])

    def get_unread(self, agent: "BaseArcaneAgent") -> list[Message]:
        return [m for m in self.get_inbox(agent) if not m.read]

    def get_prompt_context(self, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        other_name = getattr(other, 'name', str(other))
        location = getattr(agent, 'current_location_name', 'an unknown location')
        return (
            f"You are speaking in person with {other_name} at {location}. "
            f"This is a face-to-face conversation. You can observe their "
            f"body language and emotional cues. Other agents may be nearby."
        )


class SMSChannel(BaseChannel):
    """SMS text messaging — short, asynchronous, phone-number based."""

    channel_name = "sms"

    def __init__(self, delivery_delay_steps: int = 1):
        self.delivery_delay = delivery_delay_steps
        self.pending_messages: list[Message] = []
        self.agent_inboxes: dict[str, list[Message]] = {}

    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             content: str, **kwargs) -> Message:
        step = kwargs.get("step", 0)
        msg = Message(
            sender_id=getattr(sender, 'agent_id', str(sender)),
            recipient_id=getattr(recipient, 'agent_id', str(recipient)),
            channel=self.channel_name,
            content=content,
            sent_at_step=step,
            delivered_at_step=None,  # Async — delivered later
        )
        self.pending_messages.append(msg)
        return msg

    def deliver_pending(self, current_step: int) -> list[Message]:
        """Deliver messages that are ready (past their delay)."""
        delivered = []
        still_pending = []
        for msg in self.pending_messages:
            if current_step >= msg.sent_at_step + self.delivery_delay:
                msg.delivered_at_step = current_step
                rid = msg.recipient_id
                if rid not in self.agent_inboxes:
                    self.agent_inboxes[rid] = []
                self.agent_inboxes[rid].append(msg)
                delivered.append(msg)
            else:
                still_pending.append(msg)
        self.pending_messages = still_pending
        return delivered

    def get_inbox(self, agent: "BaseArcaneAgent") -> list[Message]:
        aid = getattr(agent, 'agent_id', str(agent))
        return self.agent_inboxes.get(aid, [])

    def get_unread(self, agent: "BaseArcaneAgent") -> list[Message]:
        return [m for m in self.get_inbox(agent) if not m.read]

    def get_prompt_context(self, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        other_name = getattr(other, 'name', str(other))
        return (
            f"You are texting {other_name} via SMS. Keep messages brief and "
            f"informal. You can see the most recent messages in this thread."
        )


class EmailChannel(BaseChannel):
    """Email — longer messages, subject lines, async delivery."""

    channel_name = "email"

    def __init__(self, delivery_delay_steps: int = 2):
        self.delivery_delay = delivery_delay_steps
        self.pending_messages: list[Message] = []
        self.agent_inboxes: dict[str, list[Message]] = {}

    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             content: str, **kwargs) -> Message:
        step = kwargs.get("step", 0)
        msg = Message(
            sender_id=getattr(sender, 'agent_id', str(sender)),
            recipient_id=getattr(recipient, 'agent_id', str(recipient)),
            channel=self.channel_name,
            subject=kwargs.get("subject", "No subject"),
            content=content,
            sent_at_step=step,
            delivered_at_step=None,
        )
        self.pending_messages.append(msg)
        return msg

    def deliver_pending(self, current_step: int) -> list[Message]:
        delivered = []
        still_pending = []
        for msg in self.pending_messages:
            if current_step >= msg.sent_at_step + self.delivery_delay:
                msg.delivered_at_step = current_step
                rid = msg.recipient_id
                if rid not in self.agent_inboxes:
                    self.agent_inboxes[rid] = []
                self.agent_inboxes[rid].append(msg)
                delivered.append(msg)
            else:
                still_pending.append(msg)
        self.pending_messages = still_pending
        return delivered

    def get_inbox(self, agent: "BaseArcaneAgent") -> list[Message]:
        aid = getattr(agent, 'agent_id', str(agent))
        return self.agent_inboxes.get(aid, [])

    def get_unread(self, agent: "BaseArcaneAgent") -> list[Message]:
        return [m for m in self.get_inbox(agent) if not m.read]

    def get_prompt_context(self, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        other_name = getattr(other, 'name', str(other))
        return (
            f"You are emailing {other_name}. You can write a longer message "
            f"with a subject line. This is a professional email platform."
        )


class SocialDMChannel(BaseChannel):
    """Social media DM (e.g. LinkedInSim) — includes platform context."""

    channel_name = "social_dm"

    def __init__(self, platform_name: str = "LinkedInSim",
                 delivery_delay_steps: int = 1):
        self.platform_name = platform_name
        self.delivery_delay = delivery_delay_steps
        self.pending_messages: list[Message] = []
        self.agent_inboxes: dict[str, list[Message]] = {}

    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             content: str, **kwargs) -> Message:
        step = kwargs.get("step", 0)
        msg = Message(
            sender_id=getattr(sender, 'agent_id', str(sender)),
            recipient_id=getattr(recipient, 'agent_id', str(recipient)),
            channel=self.channel_name,
            content=content,
            sent_at_step=step,
            delivered_at_step=None,
            metadata={"platform": self.platform_name},
        )
        self.pending_messages.append(msg)
        return msg

    def deliver_pending(self, current_step: int) -> list[Message]:
        delivered = []
        still_pending = []
        for msg in self.pending_messages:
            if current_step >= msg.sent_at_step + self.delivery_delay:
                msg.delivered_at_step = current_step
                rid = msg.recipient_id
                if rid not in self.agent_inboxes:
                    self.agent_inboxes[rid] = []
                self.agent_inboxes[rid].append(msg)
                delivered.append(msg)
            else:
                still_pending.append(msg)
        self.pending_messages = still_pending
        return delivered

    def get_inbox(self, agent: "BaseArcaneAgent") -> list[Message]:
        aid = getattr(agent, 'agent_id', str(agent))
        return self.agent_inboxes.get(aid, [])

    def get_unread(self, agent: "BaseArcaneAgent") -> list[Message]:
        return [m for m in self.get_inbox(agent) if not m.read]

    def get_prompt_context(self, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        other_name = getattr(other, 'name', str(other))
        # If the other agent has a public profile, include it
        profile = getattr(other, 'public_profile', None)
        profile_str = f" Their public profile shows: {profile}" if profile else ""
        return (
            f"You are sending a direct message to {other_name} on "
            f"{self.platform_name}.{profile_str}"
        )

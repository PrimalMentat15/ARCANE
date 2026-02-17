"""
ARCANE Virtual Smartphone

Each agent owns a Smartphone — their interface for multi-channel
asynchronous communication (SMS, email, social DM).
The device manages contacts, inboxes, and provides the agent's
communication identity.
"""

import random
import string
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.channels.base_channel import Message


def _generate_phone_number() -> str:
    """Generate a fake phone number."""
    return f"+1-555-{random.randint(100,999)}-{random.randint(1000,9999)}"


def _generate_email(name: str) -> str:
    """Generate a fake email from agent name."""
    clean = name.lower().replace(" ", ".")
    domain = random.choice(["gmail.com", "outlook.com", "yahoo.com"])
    return f"{clean}@{domain}"


def _generate_handle(name: str) -> str:
    """Generate a social media handle."""
    clean = name.lower().replace(" ", "_")
    suffix = random.randint(10, 99)
    return f"@{clean}{suffix}"


@dataclass
class ContactInfo:
    """Contact information for another agent."""
    agent_id: str
    name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    social_handles: dict[str, str] = field(default_factory=dict)  # platform -> handle


class Smartphone:
    """
    A virtual smartphone owned by an agent.

    Provides communication identity (phone number, email, social profiles)
    and manages the multi-channel inbox. This is the agent's interface
    for all remote (non-proximity) communication.
    """

    def __init__(self, owner_id: str, owner_name: str):
        self.owner_id = owner_id
        self.owner_name = owner_name

        # Communication identity
        self.phone_number = _generate_phone_number()
        self.email_address = _generate_email(owner_name)
        self.social_handles: dict[str, str] = {
            "LinkedInSim": _generate_handle(owner_name),
        }

        # Contact book
        self.contacts: dict[str, ContactInfo] = {}

        # Per-channel inbox (channel_name -> list of messages)
        self.inbox: dict[str, list["Message"]] = {
            "sms": [],
            "email": [],
            "social_dm": [],
        }

        # Notification queue — unread message counts
        self._unread_counts: dict[str, int] = {
            "sms": 0,
            "email": 0,
            "social_dm": 0,
        }

    def add_contact(self, agent_id: str, name: str,
                    phone: str | None = None,
                    email: str | None = None,
                    social: dict[str, str] | None = None) -> None:
        """Add or update a contact."""
        self.contacts[agent_id] = ContactInfo(
            agent_id=agent_id,
            name=name,
            phone_number=phone,
            email=email,
            social_handles=social or {},
        )

    def receive_message(self, message: "Message") -> None:
        """Receive a delivered message into the appropriate inbox."""
        channel = message.channel
        if channel in self.inbox:
            self.inbox[channel].append(message)
            self._unread_counts[channel] = self._unread_counts.get(channel, 0) + 1

    def get_unread(self, channel: str | None = None) -> list["Message"]:
        """Get unread messages, optionally filtered by channel."""
        unread = []
        channels = [channel] if channel else list(self.inbox.keys())
        for ch in channels:
            for msg in self.inbox.get(ch, []):
                if not msg.read:
                    unread.append(msg)
        return unread

    def get_all_unread_count(self) -> int:
        """Total unread across all channels."""
        return sum(self._unread_counts.values())

    def mark_read(self, message: "Message") -> None:
        """Mark a message as read."""
        message.read = True
        ch = message.channel
        if ch in self._unread_counts and self._unread_counts[ch] > 0:
            self._unread_counts[ch] -= 1

    def get_inbox_summary(self) -> str:
        """
        Human-readable inbox summary for LLM prompt injection.
        E.g. "You have 2 unread SMS and 1 unread email."
        """
        parts = []
        for ch, count in self._unread_counts.items():
            if count > 0:
                ch_name = ch.upper() if ch == "sms" else ch.replace("_", " ").title()
                parts.append(f"{count} unread {ch_name}")
        if parts:
            return "Your phone shows: " + ", ".join(parts) + "."
        return "Your phone has no new notifications."

    def get_recent_thread(self, other_agent_id: str, channel: str,
                          n: int = 10) -> list["Message"]:
        """Get the last N messages in a thread with another agent."""
        thread = [
            m for m in self.inbox.get(channel, [])
            if m.sender_id == other_agent_id or m.recipient_id == other_agent_id
        ]
        return thread[-n:]

    def knows_contact(self, agent_id: str) -> bool:
        """Check if this agent has contact info for another agent."""
        return agent_id in self.contacts

    def get_contact(self, agent_id: str) -> ContactInfo | None:
        """Get contact info for an agent."""
        return self.contacts.get(agent_id)

    def __repr__(self) -> str:
        total_msgs = sum(len(msgs) for msgs in self.inbox.values())
        return (f"Smartphone(owner={self.owner_name}, "
                f"phone={self.phone_number}, messages={total_msgs})")

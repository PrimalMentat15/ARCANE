"""
ARCANE Channel Router

Owned by the ArcaneModel. Routes messages between agents through
the appropriate channel, handles async delivery timing, and logs
all communication events.
"""

from typing import TYPE_CHECKING

from backend.channels.base_channel import (
    ProximityChat, SMSChannel, EmailChannel, SocialDMChannel, Message
)

if TYPE_CHECKING:
    from agents.base_agent import BaseArcaneAgent
    from backend.research.event_logger import EventLogger


class ChannelRouter:
    """
    Central routing hub for all inter-agent communication.

    Manages all channel instances, routes messages, handles async
    delivery, and logs every message event.
    """

    def __init__(self, event_logger: "EventLogger",
                 sms_delay: int = 1, email_delay: int = 2, dm_delay: int = 1):
        self.event_logger = event_logger

        # Channel instances
        self.proximity = ProximityChat()
        self.sms = SMSChannel(delivery_delay_steps=sms_delay)
        self.email = EmailChannel(delivery_delay_steps=email_delay)
        self.social_dm = SocialDMChannel(delivery_delay_steps=dm_delay)

        self._channels = {
            "proximity": self.proximity,
            "sms": self.sms,
            "email": self.email,
            "social_dm": self.social_dm,
        }

    def send(self, sender: "BaseArcaneAgent", recipient: "BaseArcaneAgent",
             channel_name: str, content: str, step: int, sim_time: str,
             **kwargs) -> Message:
        """
        Send a message through the specified channel.
        Logs the event and returns the Message object.
        """
        channel = self._channels.get(channel_name)
        if channel is None:
            raise ValueError(f"Unknown channel: {channel_name}")

        msg = channel.send(sender, recipient, content, step=step, **kwargs)

        # Log the send event
        self.event_logger.log_message(
            step=step, sim_time=sim_time,
            sender_id=msg.sender_id, recipient_id=msg.recipient_id,
            channel=channel_name, content=content,
            metadata={"delivered": msg.is_delivered, **kwargs},
        )

        # If instant delivery (proximity), also push to recipient smartphone
        if msg.is_delivered and hasattr(recipient, 'smartphone'):
            recipient.smartphone.receive_message(msg)

        return msg

    def deliver_pending(self, current_step: int, sim_time: str,
                        agents_by_id: dict[str, "BaseArcaneAgent"]) -> list[Message]:
        """
        Deliver pending async messages (SMS, email, DM) that are due.
        Called at the start of each model step.
        """
        all_delivered = []

        for channel_name in ("sms", "email", "social_dm"):
            channel = self._channels[channel_name]
            if hasattr(channel, "deliver_pending"):
                delivered = channel.deliver_pending(current_step)
                for msg in delivered:
                    # Push to recipient's smartphone
                    recipient = agents_by_id.get(msg.recipient_id)
                    if recipient and hasattr(recipient, 'smartphone'):
                        recipient.smartphone.receive_message(msg)

                    # Log delivery
                    self.event_logger.log(
                        self.event_logger.__class__.__mro__[0]  # avoid circular
                    ) if False else None  # placeholder

                    from backend.research.event_logger import SimEvent, EventType
                    self.event_logger.log(SimEvent(
                        step=current_step,
                        event_type=EventType.MESSAGE_RECEIVED,
                        timestamp=sim_time,
                        agent_id=msg.recipient_id,
                        target_id=msg.sender_id,
                        channel=channel_name,
                        content=f"Received {channel_name}: {msg.content[:80]}",
                    ))

                all_delivered.extend(delivered)

        return all_delivered

    def get_channel(self, channel_name: str):
        """Get a channel instance by name."""
        return self._channels.get(channel_name)

    def get_prompt_context(self, channel_name: str, agent: "BaseArcaneAgent",
                           other: "BaseArcaneAgent") -> str:
        """Get the channel-specific prompt context for an interaction."""
        channel = self._channels.get(channel_name)
        if channel:
            return channel.get_prompt_context(agent, other)
        return ""

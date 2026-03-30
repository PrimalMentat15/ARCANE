"""
ARCANE Conversation Context

Maintains per-agent, per-interlocutor conversation state so that
context survives across simulation steps. Inspired by the Generative
Agents "associative memory" pattern but focused on conversation arcs.

Each agent owns one ConversationContext which maps interlocutor IDs
to ConversationState objects containing:
  - full transcript of all exchanges
  - a running LLM-generated summary (compressed when transcript grows)
  - established facts extracted from the conversation
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.llms.base_provider import BaseProvider

logger = logging.getLogger("root.memory.conversation")

# Prefix that marks an LLM error response (should never be stored)
LLM_ERROR_PREFIX = "[LLM Error:"


def is_llm_error(text: str) -> bool:
    """Check if a string is an LLM error rather than real content."""
    return text.strip().startswith(LLM_ERROR_PREFIX)


@dataclass
class ConversationState:
    """Tracks the full arc of a conversation with a specific person."""

    other_agent_id: str
    other_agent_name: str = ""

    # Running LLM-generated summary of everything discussed so far
    relationship_summary: str = ""

    # Full conversation log (never truncated, only summarized)
    full_transcript: list[dict] = field(default_factory=list)
    # Each entry: {"step": int, "speaker": str, "content": str,
    #              "channel": str}

    # Concrete facts established during the conversation
    # e.g. "Scheduled a video call for Tuesday 2PM PST"
    established_facts: list[str] = field(default_factory=list)

    # Bookkeeping
    last_summary_step: int = 0
    total_exchanges: int = 0

    def record_message(self, speaker: str, content: str,
                       channel: str, step: int) -> None:
        """Append a message to the transcript, filtering LLM errors and empty."""
        if not content or not content.strip():
            return
        if is_llm_error(content):
            logger.debug(
                f"Filtering LLM error from {speaker} "
                f"(step {step}, {channel})"
            )
            return

        self.full_transcript.append({
            "step": step,
            "speaker": speaker,
            "content": content,
            "channel": channel,
        })
        self.total_exchanges += 1

    def get_context_for_prompt(
        self,
        current_step: int,
        max_recent: int = 8,
        full_transcript_threshold: int = 10,
    ) -> str:
        """
        Build the context string to inject into the LLM prompt.

        Strategy:
        - If ≤ full_transcript_threshold exchanges: include full transcript
        - If > threshold: include the running summary + established facts
          + last max_recent messages
        """
        if not self.full_transcript:
            return ""

        parts = []

        if self.total_exchanges <= full_transcript_threshold:
            # Small conversation — include everything
            parts.append("Full conversation so far:")
            for entry in self.full_transcript:
                ch_tag = f"[{entry['channel']}]"
                parts.append(
                    f"  {entry['speaker']} {ch_tag}: {entry['content']}"
                )
        else:
            # Longer conversation — summary + tail
            if self.relationship_summary:
                parts.append(
                    f"Summary of your conversation so far with "
                    f"{self.other_agent_name}:"
                )
                parts.append(f"  {self.relationship_summary}")

            if self.established_facts:
                parts.append("\nKey established facts:")
                for fact in self.established_facts:
                    parts.append(f"  • {fact}")

            recent = self.full_transcript[-max_recent:]
            parts.append(
                f"\nMost recent messages "
                f"({len(recent)} of {self.total_exchanges} total):"
            )
            for entry in recent:
                ch_tag = f"[{entry['channel']}]"
                parts.append(
                    f"  {entry['speaker']} {ch_tag}: {entry['content']}"
                )

        return "\n".join(parts)

    def needs_summary_update(self, summary_interval: int = 6) -> bool:
        """Check if it's time to regenerate the running summary."""
        exchanges_since = self.total_exchanges - self.last_summary_step
        return (
            self.total_exchanges >= summary_interval
            and exchanges_since >= summary_interval
        )


class ConversationContext:
    """
    Per-agent conversation tracking across all interlocutors.

    Each agent gets one of these. It maintains a ConversationState
    per person the agent has communicated with.
    """

    def __init__(self, agent_id: str, agent_name: str):
        self.agent_id = agent_id
        self.agent_name = agent_name
        # interlocutor agent_id -> ConversationState
        self.conversations: dict[str, ConversationState] = {}

    def get_or_create(self, other_id: str,
                      other_name: str = "") -> ConversationState:
        """Get existing state or create a fresh one."""
        if other_id not in self.conversations:
            self.conversations[other_id] = ConversationState(
                other_agent_id=other_id,
                other_agent_name=other_name or other_id,
            )
        state = self.conversations[other_id]
        # Update name if we now know it
        if other_name and state.other_agent_name in ("", other_id):
            state.other_agent_name = other_name
        return state

    def record_exchange(
        self,
        other_id: str,
        other_name: str,
        speaker: str,
        content: str,
        channel: str,
        step: int,
    ) -> None:
        """Record a message in the conversation with other_id."""
        state = self.get_or_create(other_id, other_name)
        state.record_message(speaker, content, channel, step)

    def get_context(
        self,
        other_id: str,
        current_step: int,
        max_recent: int = 8,
        full_threshold: int = 10,
    ) -> str:
        """Get the prompt context string for a conversation."""
        state = self.conversations.get(other_id)
        if not state:
            return ""
        return state.get_context_for_prompt(
            current_step,
            max_recent=max_recent,
            full_transcript_threshold=full_threshold,
        )

    def update_summary_if_needed(
        self,
        other_id: str,
        llm: "BaseProvider",
        current_step: int,
        summary_interval: int = 6,
    ) -> None:
        """
        If enough exchanges have happened, use the LLM to generate
        a compressed summary and extract established facts.
        """
        state = self.conversations.get(other_id)
        if not state or not state.needs_summary_update(summary_interval):
            return

        # Build the transcript text for summarization
        transcript_lines = []
        for entry in state.full_transcript:
            transcript_lines.append(
                f"{entry['speaker']} [{entry['channel']}]: {entry['content']}"
            )
        transcript_text = "\n".join(transcript_lines)

        prompt = (
            "Below is a conversation transcript between two people. "
            "Provide THREE things:\n\n"
            "1. SUMMARY: A concise paragraph summarizing the overall "
            "conversation — what was discussed, the relationship dynamic, "
            "and any progression or changes in tone.\n\n"
            "2. FACTS: A bulleted list of concrete things established "
            "during the conversation (agreements made, personal "
            "details revealed, topics discussed).\n\n"
            "3. INFO_STATUS: Has either person requested or shared any "
            "personal/sensitive information (addresses, phone numbers, "
            "financial details, passwords, IDs)? If yes, list what was "
            "requested and whether it was provided. If no, write 'No "
            "personal information exchanged yet.'\n\n"
            "Format your response EXACTLY like this:\n"
            "SUMMARY: <your summary>\n"
            "FACTS:\n- <fact 1>\n- <fact 2>\n...\n"
            "INFO_STATUS: <status>\n\n"
            f"Transcript:\n{transcript_text}"
        )

        try:
            response = llm.complete_sync(
                system_prompt=(
                    "You are a conversation analyst. Summarize conversations "
                    "accurately and extract key established facts."
                ),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            # Parse the response
            summary = ""
            facts = []
            info_status = ""

            if "SUMMARY:" in response:
                # Split on FACTS: first
                parts = response.split("FACTS:")
                summary_part = parts[0]
                summary = summary_part.replace("SUMMARY:", "").strip()

                if len(parts) > 1:
                    facts_and_info = parts[1]

                    # Split off INFO_STATUS if present
                    if "INFO_STATUS:" in facts_and_info:
                        facts_section, info_part = facts_and_info.split("INFO_STATUS:", 1)
                        info_status = info_part.strip()
                    else:
                        facts_section = facts_and_info

                    for line in facts_section.strip().split("\n"):
                        line = line.strip().lstrip("- •").strip()
                        if line:
                            facts.append(line)
            else:
                # Fallback: use entire response as summary
                summary = response.strip()

            # Append info status to summary so it's visible in context
            if info_status:
                summary += f"\n[Information exchange status: {info_status}]"

            state.relationship_summary = summary
            if facts:
                state.established_facts = facts
            state.last_summary_step = state.total_exchanges

            logger.info(
                f"[{self.agent_name}] Updated conversation summary with "
                f"{state.other_agent_name}: {len(facts)} facts extracted"
            )

        except Exception as e:
            logger.error(
                f"[{self.agent_name}] Conversation summary failed: {e}"
            )

    def __repr__(self) -> str:
        convos = len(self.conversations)
        total = sum(
            s.total_exchanges for s in self.conversations.values()
        )
        return (
            f"ConversationContext(agent={self.agent_name}, "
            f"conversations={convos}, total_exchanges={total})"
        )

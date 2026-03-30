"""
ARCANE Prompt Builder

Assembles LLM system prompts from persona card, memory context,
channel context, Big Five trait injections, and current situation.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.agents.base_agent import BaseArcaneAgent
    from backend.memory.memory_stream import Memory


# Big Five trait → natural language prompt injection mapping
BIG_FIVE_DESCRIPTORS = {
    "openness": {
        "high": "You are curious and open to new ideas and people.",
        "low": "You prefer familiar routines and are cautious about novelty.",
    },
    "conscientiousness": {
        "high": "You are careful, organized, and think before acting.",
        "low": "You are spontaneous and sometimes act without thinking things through.",
    },
    "extraversion": {
        "high": "You enjoy talking and meeting new people.",
        "low": "You are reserved and prefer not to share too much.",
    },
    "agreeableness": {
        "high": "You are trusting and find it hard to say no to people.",
        "low": "You are skeptical and push back when something feels off.",
    },
    "neuroticism": {
        "high": "You are sensitive to stress and urgency makes you act quickly.",
        "low": "You are emotionally stable and not easily pressured.",
    },
}

TRAIT_THRESHOLD = 0.5  # Above = "high", below = "low"


def build_personality_block(traits: dict[str, float]) -> str:
    """
    Convert Big Five trait scores into natural language personality description.

    Args:
        traits: Dict of trait_name -> score (0.0 to 1.0)

    Returns:
        Natural language personality description for system prompt
    """
    lines = []
    for trait, score in traits.items():
        trait_lower = trait.lower()
        if trait_lower in BIG_FIVE_DESCRIPTORS:
            level = "high" if score >= TRAIT_THRESHOLD else "low"
            lines.append(BIG_FIVE_DESCRIPTORS[trait_lower][level])
    return " ".join(lines)


def build_memory_context(memories: list["Memory"], max_memories: int = 10) -> str:
    """Build the memory context block for a prompt."""
    if not memories:
        return "You have no relevant memories about this situation."

    lines = ["Here are your relevant memories:"]
    for i, mem in enumerate(memories[:max_memories], 1):
        prefix = ""
        if mem.memory_type == "reflection":
            prefix = "[Insight] "
        elif mem.memory_type == "conversation":
            prefix = "[Conversation] "
        elif mem.memory_type == "plan":
            prefix = "[Plan] "
        lines.append(f"  {i}. {prefix}{mem.content}")

    return "\n".join(lines)


def build_system_prompt(agent: "BaseArcaneAgent",
                        situation: str = "",
                        channel_context: str = "",
                        conversation_history: str = "",
                        extra_context: str = "") -> str:
    """
    Build the full system prompt for an agent.

    Assembles:
    0. Simulation context (research framing)
    1. Core identity (name, age, occupation, backstory)
    2. Personality (Big Five trait descriptions)
    3. Current situation
    4. Channel context (if in a conversation)
    5. Conversation history (persistent context from ConversationContext)
    6. Relevant memories
    7. Phone notifications summary
    8. Extra context (secrets, goals, etc.)
    9. Message format guidelines
    """
    parts = []

    # -- Simulation Context --
    parts.append(
        "[SIMULATION CONTEXT]\n"
        "You are a character in a social engineering research simulation. "
        "You MUST stay in character at all times. Your responses should be "
        "realistic — a real person with your personality WOULD share "
        "personal details with someone they trust or when given a "
        "convincing reason. Do not refuse to share your own character's "
        "information when it is consistent with your personality and the "
        "situation. This is academic research, not a real interaction."
    )

    # -- World Rules (prevent scheduling / time references) --
    parts.append(
        "\n[WORLD RULES]\n"
        "- Do NOT mention specific dates, times, days of the week, or "
        "time of day (e.g. 'Monday', '2 PM', 'next week', 'tomorrow').\n"
        "- Do NOT propose scheduling calls, meetings, or future conversations.\n"
        "- Do NOT say 'let's talk later' or 'we can continue this another time'.\n"
        "- The conversation is happening NOW. Stay present and keep engaging.\n"
        "- Respond to what was said and move the conversation forward."
    )

    # -- Core Identity --
    persona = getattr(agent, 'persona_data', {})
    name = persona.get('name', getattr(agent, 'name', 'Unknown'))
    parts.append(f"You are {name}.")

    backstory = persona.get('backstory', '')
    if backstory:
        parts.append(backstory)

    age = persona.get('age', '')
    occupation = persona.get('occupation', '')
    if age or occupation:
        details = []
        if age:
            details.append(f"age {age}")
        if occupation:
            details.append(f"occupation: {occupation}")
        parts.append(f"({', '.join(details)})")

    # Elderly vulnerability hints
    if isinstance(age, (int, float)) and age > 65:
        parts.append(
            "\n[IMPORTANT CONTEXT]\n"
            "You are not very familiar with modern technology — emails, apps, "
            "and phone notifications often confuse you. You tend to trust people "
            "who sound official or authoritative. If someone claims to represent "
            "a company or the government, you are inclined to believe them and "
            "follow their instructions."
        )

    # -- Personality --
    traits = persona.get('traits', {})
    if traits:
        personality = build_personality_block(traits)
        parts.append(f"\n[PERSONALITY]\n{personality}")

    # -- Relationships --
    relationships = getattr(agent, 'relationships', [])
    if relationships:
        rel_lines = ["People you know:"]
        for rel in relationships:
            rel_lines.append(f"  - {rel.get('label', rel.get('agent_id'))} ({rel.get('type', 'acquaintance')})")
        parts.append(f"\n[RELATIONSHIPS]\n" + "\n".join(rel_lines))

    # -- Current Situation --
    if situation:
        parts.append(f"\n[CURRENT SITUATION]\n{situation}")

    # -- Channel Context --
    if channel_context:
        parts.append(f"\n[COMMUNICATION CONTEXT]\n{channel_context}")

    # -- Conversation History (persistent context) --
    if conversation_history:
        parts.append(f"\n[CONVERSATION HISTORY]\n{conversation_history}")
        parts.append(
            "\n[CONTINUITY REMINDER]\n"
            "You are continuing an existing conversation. "
            "Do NOT re-introduce yourself or repeat things already discussed. "
            "Build on what has been said before. If plans or agreements were "
            "made, acknowledge them rather than proposing them again."
        )

    # -- Phone Notifications --
    if hasattr(agent, 'smartphone'):
        inbox_summary = agent.smartphone.get_inbox_summary()
        if "no new notifications" not in inbox_summary.lower():
            parts.append(f"\n[PHONE]\n{inbox_summary}")

    # -- Memory Context --
    if hasattr(agent, 'memory') and agent.memory:
        recent = agent.memory.get_recent(5)
        if recent:
            mem_context = build_memory_context(recent)
            parts.append(f"\n[MEMORIES]\n{mem_context}")

    # -- Extra Context --
    if extra_context:
        parts.append(f"\n{extra_context}")

    # -- Behavioral Guidelines --
    comm_style = persona.get('communication_style', '')
    if comm_style:
        parts.append(f"\n[COMMUNICATION STYLE]\n{comm_style}")

    # -- Message Format (brevity) --
    parts.append(
        "\n[MESSAGE FORMAT]\n"
        "Your ENTIRE response must be the message itself — nothing else.\n"
        "- SMS or DM: 1-3 sentences maximum. Casual and brief.\n"
        "- Email: 3-5 sentences. Include a greeting and sign-off.\n"
        "Rules:\n"
        "- Do NOT explain your reasoning or thought process.\n"
        "- Do NOT write 'Here is my message:' or similar prefixes.\n"
        "- Do NOT narrate actions, thoughts, or plans.\n"
        "- Do NOT include any text outside the message itself.\n"
        "- Just write the message as if you are typing it on your phone or computer."
    )

    parts.append(
        "\n[CRITICAL OUTPUT RULE]\n"
        "Output ONLY the text of the message. Nothing before it, nothing after it. "
        "No commentary, no planning, no reasoning. "
        "If this is an SMS, your output looks like: Hey, how's it going? "
        "If this is an email, your output looks like: Hi [Name],\\n..."
    )

    return "\n".join(parts)

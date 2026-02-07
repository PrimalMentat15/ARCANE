"""
ARCANE Prompt Builder

Assembles LLM system prompts from persona card, memory context,
channel context, Big Five trait injections, and current situation.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from arcane.agents.base_agent import BaseArcaneAgent
    from arcane.memory.memory_stream import Memory


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
                        extra_context: str = "") -> str:
    """
    Build the full system prompt for an agent.

    Assembles:
    1. Core identity (name, age, occupation, backstory)
    2. Personality (Big Five trait descriptions)
    3. Current situation
    4. Channel context (if in a conversation)
    5. Relevant memories
    6. Phone notifications summary
    7. Extra context (secrets, goals, etc.)
    """
    parts = []

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

    # -- Personality --
    traits = persona.get('traits', {})
    if traits:
        personality = build_personality_block(traits)
        parts.append(f"\n[PERSONALITY]\n{personality}")

    # -- Current Situation --
    if situation:
        parts.append(f"\n[CURRENT SITUATION]\n{situation}")

    # -- Channel Context --
    if channel_context:
        parts.append(f"\n[COMMUNICATION CONTEXT]\n{channel_context}")

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

    parts.append(
        "\n[GUIDELINES]\n"
        "Respond in character. Be natural and conversational. "
        "Your responses should reflect your personality traits. "
        "Do not break character or acknowledge that you are an AI."
    )

    return "\n".join(parts)

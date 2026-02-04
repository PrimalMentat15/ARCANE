"""
ARCANE Memory Stream

Adapted from the Generative Agents associative memory system.
Stores observation, reflection, and plan memories with importance scoring
and time-decay retrieval.
"""

import math
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Memory:
    """A single memory entry in the stream."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_step: int = 0
    agent_id: str = ""
    content: str = ""
    memory_type: str = "observation"  # observation | reflection | plan | conversation
    importance: float = 5.0           # LLM-rated 1-10
    embedding: Optional[list[float]] = None  # For semantic retrieval
    last_accessed: int = 0
    keywords: list[str] = field(default_factory=list)
    related_agent: Optional[str] = None
    channel: Optional[str] = None     # Which channel this memory came from

    def __post_init__(self):
        if not self.keywords:
            # Extract simple keywords from content
            self.keywords = [w.lower() for w in self.content.split()
                             if len(w) > 3][:10]


class MemoryStream:
    """
    An agent's long-term episodic memory store.

    Supports storage, importance-weighted retrieval with recency decay,
    and keyword/embedding-based relevance scoring.
    """

    def __init__(self, agent_id: str, recency_weight: float = 1.0,
                 importance_weight: float = 1.0, relevance_weight: float = 1.0,
                 decay_factor: float = 0.995):
        self.agent_id = agent_id
        self.memories: list[Memory] = []

        # Retrieval scoring weights
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight
        self.relevance_weight = relevance_weight
        self.decay_factor = decay_factor

        # Importance accumulator for reflection trigger
        self.importance_accumulator = 0.0
        self.reflection_threshold = 50.0  # Trigger reflection when reached

    def add(self, content: str, memory_type: str = "observation",
            importance: float = 5.0, current_step: int = 0,
            related_agent: str | None = None,
            channel: str | None = None,
            embedding: list[float] | None = None) -> Memory:
        """Add a new memory to the stream."""
        memory = Memory(
            created_step=current_step,
            agent_id=self.agent_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            last_accessed=current_step,
            related_agent=related_agent,
            channel=channel,
            embedding=embedding,
        )
        self.memories.append(memory)
        self.importance_accumulator += importance
        return memory

    def retrieve(self, query: str, current_step: int,
                 n: int = 10, query_embedding: list[float] | None = None) -> list[Memory]:
        """
        Retrieve the top-n most relevant memories.

        Score = α * recency + β * importance + γ * relevance

        - recency: exponential decay based on steps since creation
        - importance: normalized 1-10 score
        - relevance: keyword overlap (or cosine similarity if embeddings available)
        """
        if not self.memories:
            return []

        scored = []
        query_keywords = set(w.lower() for w in query.split() if len(w) > 3)

        for mem in self.memories:
            # Recency score: exponential decay
            steps_ago = current_step - mem.created_step
            recency = self.decay_factor ** steps_ago

            # Importance score: normalize to 0-1
            importance = mem.importance / 10.0

            # Relevance score: keyword overlap
            if query_keywords and mem.keywords:
                mem_keywords = set(mem.keywords)
                overlap = len(query_keywords & mem_keywords)
                relevance = overlap / max(len(query_keywords), 1)
            elif query_embedding and mem.embedding:
                # Cosine similarity if embeddings available
                relevance = self._cosine_similarity(query_embedding, mem.embedding)
            else:
                relevance = 0.0

            score = (self.recency_weight * recency +
                     self.importance_weight * importance +
                     self.relevance_weight * relevance)

            scored.append((score, mem))

            # Update last accessed
            mem.last_accessed = current_step

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:n]]

    def get_recent(self, n: int = 20) -> list[Memory]:
        """Get the N most recent memories."""
        return list(reversed(self.memories[-n:]))

    def get_by_type(self, memory_type: str) -> list[Memory]:
        """Get all memories of a specific type."""
        return [m for m in self.memories if m.memory_type == memory_type]

    def get_by_agent(self, agent_id: str) -> list[Memory]:
        """Get all memories involving a specific agent."""
        return [m for m in self.memories if m.related_agent == agent_id]

    def should_reflect(self) -> bool:
        """Check if accumulated importance warrants a reflection."""
        return self.importance_accumulator >= self.reflection_threshold

    def reset_reflection_accumulator(self) -> None:
        """Reset after a reflection is performed."""
        self.importance_accumulator = 0.0

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def __len__(self) -> int:
        return len(self.memories)

    def __repr__(self) -> str:
        return f"MemoryStream(agent={self.agent_id}, memories={len(self)})"

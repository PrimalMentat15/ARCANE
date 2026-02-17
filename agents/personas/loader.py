"""
Persona loader — reads agent persona YAML files from the personas/ directory.

Usage:
    from personas.loader import load_persona, list_available_personas

    persona = load_persona("sarah_chen")          # loads personas/benign/sarah_chen.yaml
    ids = list_available_personas("benign")        # ["sarah_chen", "david_park", ...]
"""

import os
import yaml
import logging
from pathlib import Path

logger = logging.getLogger("root.personas")

_PERSONAS_DIR = Path(__file__).parent
_cache: dict[str, dict] = {}


def load_persona(persona_id: str) -> dict:
    """Load a persona by ID from the personas/ directory.

    Searches benign/ and deviant/ subdirectories. Results are cached
    in memory after first load for zero-overhead repeated access.

    Returns:
        dict with all persona fields (id, name, type, traits, secrets, etc.)

    Raises:
        FileNotFoundError if no matching YAML file exists.
    """
    if persona_id in _cache:
        return _cache[persona_id]

    # Search in both subdirectories
    for subdir in ("benign", "deviant"):
        path = _PERSONAS_DIR / subdir / f"{persona_id}.yaml"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            data.setdefault("id", persona_id)
            _cache[persona_id] = data
            logger.debug(f"Loaded persona '{persona_id}' from {path}")
            return data

    raise FileNotFoundError(
        f"Persona '{persona_id}' not found in {_PERSONAS_DIR}/benign/ or deviant/"
    )


def list_available_personas(agent_type: str | None = None) -> list[str]:
    """List available persona IDs, optionally filtered by type.

    Args:
        agent_type: "benign", "deviant", or None for all.

    Returns:
        Sorted list of persona ID strings.
    """
    ids: list[str] = []
    subdirs = [agent_type] if agent_type in ("benign", "deviant") else ["benign", "deviant"]

    for subdir in subdirs:
        folder = _PERSONAS_DIR / subdir
        if not folder.is_dir():
            continue
        for file in folder.iterdir():
            if file.suffix in (".yaml", ".yml") and file.stem != "__init__":
                ids.append(file.stem)

    return sorted(ids)

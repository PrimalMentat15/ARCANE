"""
ARCANE Simulation Player

Reads `.arcane` recording files and provides step-by-step access
to recorded simulation state and events for replay.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("root.player")


class SimPlayer:
    """
    Reads and navigates `.arcane` recording files for replay.

    Provides random access to any recorded step, returning the
    full agent state snapshot and events for that frame.
    """

    def __init__(self):
        self.recording: dict = {}
        self.frames: list[dict] = []
        self.filepath: str = ""
        self._loaded = False

    def load(self, filepath: str) -> dict:
        """Load a recording file and return its metadata.

        Args:
            filepath: Path to a `.arcane` recording file.

        Returns:
            Recording metadata dict.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Recording not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate format
        version = data.get("format_version", 0)
        if version != 1:
            raise ValueError(
                f"Unsupported recording format version: {version}"
            )

        if "frames" not in data:
            raise ValueError("Recording file has no frames")

        self.recording = data
        self.frames = data["frames"]
        self.filepath = str(path)
        self._loaded = True

        logger.info(f"Loaded recording: {path.name} "
                    f"({len(self.frames)} frames)")
        return self.get_metadata()

    def get_metadata(self) -> dict:
        """Return recording metadata."""
        if not self._loaded:
            return {}

        first_frame = self.frames[0] if self.frames else {}
        last_frame = self.frames[-1] if self.frames else {}

        return {
            "run_id": self.recording.get("run_id", ""),
            "created_at": self.recording.get("created_at", ""),
            "total_steps": self.recording.get("total_steps", 0),
            "total_frames": len(self.frames),
            "agents": self.recording.get("agents", {}),
            "config": self.recording.get("config", {}),
            "start_time": first_frame.get("sim_time", ""),
            "end_time": last_frame.get("sim_time", ""),
        }

    def get_frame(self, step: int) -> Optional[dict]:
        """Get the full state + events frame for a specific step.

        Args:
            step: The simulation step number (0 = initial state).

        Returns:
            Frame dict with agent_states and events, or None if
            the step is out of range.
        """
        if not self._loaded:
            return None

        # Frames are ordered by step; find the matching one
        for frame in self.frames:
            if frame.get("step") == step:
                return frame

        return None

    def get_frame_by_index(self, index: int) -> Optional[dict]:
        """Get frame by its index in the frames array.

        Args:
            index: Zero-based index into the frames array.

        Returns:
            Frame dict, or None if out of range.
        """
        if not self._loaded or index < 0 or index >= len(self.frames):
            return None
        return self.frames[index]

    def get_events_range(self, start_step: int,
                         end_step: int) -> list[dict]:
        """Get all events across a range of steps (inclusive).

        Args:
            start_step: First step (inclusive).
            end_step: Last step (inclusive).

        Returns:
            List of event dicts, ordered by step.
        """
        if not self._loaded:
            return []

        events = []
        for frame in self.frames:
            s = frame.get("step", -1)
            if start_step <= s <= end_step:
                events.extend(frame.get("events", []))
        return events

    @property
    def total_steps(self) -> int:
        """Total number of simulation steps in the recording."""
        return self.recording.get("total_steps", 0) if self._loaded else 0

    @property
    def is_loaded(self) -> bool:
        return self._loaded


def list_recordings(recording_dir: str = "storage/recordings") -> list[dict]:
    """List all available recording files with metadata.

    Returns a list of dicts with: run_id, created_at, total_steps,
    agent_count, file, size_kb.
    """
    rec_path = Path(recording_dir)
    if not rec_path.exists():
        return []

    recordings = []
    for f in sorted(rec_path.glob("rec_*.arcane"), reverse=True):
        try:
            # Read just the metadata (first few fields) without
            # loading the entire frames array
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            recordings.append({
                "run_id": data.get("run_id", f.stem),
                "created_at": data.get("created_at", ""),
                "total_steps": data.get("total_steps", 0),
                "total_frames": data.get("total_frames", 0),
                "agent_count": len(data.get("agents", {})),
                "agents": data.get("agents", {}),
                "file": str(f),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Skipping invalid recording {f.name}: {e}")

    return recordings

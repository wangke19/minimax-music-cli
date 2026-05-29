"""Evidence chain types."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


class Actor(enum.Enum):
    HUMAN = "human"
    AI = "ai"
    HUMAN_AI = "human+ai"


class Action(enum.Enum):
    PROMPT_CREATE = "prompt_create"
    LYRICS_GENERATE = "lyrics_generate"
    MUSIC_GENERATE = "music_generate"
    MUSIC_DOWNLOAD = "music_download"
    REPORT_GENERATE = "report_generate"


@dataclass
class ChainEntry:
    """Single entry in the evidence chain."""
    seq: int
    timestamp: datetime
    action: Action
    actor: Actor
    input: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    prev_hash: str = ""
    hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "seq": self.seq,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "actor": self.actor.value,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }
        if self.input:
            d["input"] = self.input
        if self.output:
            d["output"] = self.output
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> ChainEntry:
        return ChainEntry(
            seq=d["seq"],
            timestamp=datetime.fromisoformat(d["timestamp"]),
            action=Action(d["action"]),
            actor=Actor(d["actor"]),
            input=d.get("input"),
            output=d.get("output"),
            prev_hash=d.get("prev_hash", ""),
            hash=d.get("hash", ""),
        )

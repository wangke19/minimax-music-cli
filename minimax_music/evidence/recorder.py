"""Evidence recorder: writes to chain.jsonl."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .chain import Chain
from .types import Action, Actor, ChainEntry


class Recorder:
    """Records actions to the evidence chain."""

    def __init__(self, evidence_dir: Path):
        self.chain = Chain(evidence_dir)
        self.evidence_dir = evidence_dir

    def record(
        self,
        action: Action,
        actor: Actor,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        entry = ChainEntry(
            seq=0,
            timestamp=datetime.now(),
            action=action,
            actor=actor,
            input=input_data,
            output=output_data,
        )
        self.chain.append(entry)

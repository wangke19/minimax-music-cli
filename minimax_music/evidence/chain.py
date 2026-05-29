"""Evidence chain with SHA256 hash linking."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Tuple

from .types import Action, ChainEntry

GENESIS_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class Chain:
    """Manages chain.jsonl with SHA256 hash chain."""

    def __init__(self, evidence_dir: Path):
        self.chain_path = evidence_dir / "chain.jsonl"
        self._last_hash = GENESIS_HASH
        self._last_seq = 0
        self._load_last()

    def _load_last(self) -> None:
        if not self.chain_path.exists():
            return
        with open(self.chain_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    self._last_hash = d["hash"]
                    self._last_seq = d["seq"]
                except (json.JSONDecodeError, KeyError):
                    continue

    def append(self, entry: ChainEntry) -> None:
        entry.seq = self._last_seq + 1
        entry.prev_hash = self._last_hash
        entry.hash = self._compute_hash(entry)

        self.chain_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chain_path, "a") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        self._last_hash = entry.hash
        self._last_seq = entry.seq

    def verify(self) -> Tuple[bool, List[str]]:
        if not self.chain_path.exists():
            return True, []

        issues: List[str] = []
        prev_hash = GENESIS_HASH
        expected_seq = 1

        with open(self.chain_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = ChainEntry.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError) as e:
                    issues.append(f"malformed entry: {e}")
                    continue

                if entry.seq != expected_seq:
                    issues.append(f"seq mismatch: expected {expected_seq}, got {entry.seq}")
                if entry.prev_hash != prev_hash:
                    issues.append(f"seq {entry.seq}: chain broken at prev_hash")
                if entry.hash != self._recompute_hash(entry):
                    issues.append(f"seq {entry.seq}: content tampered (hash mismatch)")

                prev_hash = entry.hash
                expected_seq = entry.seq + 1

        return len(issues) == 0, issues

    def all_entries(self) -> List[ChainEntry]:
        entries: List[ChainEntry] = []
        if not self.chain_path.exists():
            return entries
        with open(self.chain_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(ChainEntry.from_dict(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
        return entries

    def _compute_hash(self, entry: ChainEntry) -> str:
        data = entry.prev_hash + entry.action.value
        if entry.input:
            data += self._sorted_json(entry.input)
        if entry.output:
            data += self._sorted_json(entry.output)
        h = hashlib.sha256(data.encode()).hexdigest()
        return f"sha256:{h}"

    def _recompute_hash(self, entry: ChainEntry) -> str:
        data = entry.prev_hash + entry.action.value
        if entry.input:
            data += self._sorted_json(entry.input)
        if entry.output:
            data += self._sorted_json(entry.output)
        h = hashlib.sha256(data.encode()).hexdigest()
        return f"sha256:{h}"

    @staticmethod
    def _sorted_json(obj: dict) -> str:
        parts = []
        for k in sorted(obj.keys()):
            v = obj[k]
            parts.append(f"{k}:{json.dumps(v, separators=(',', ':'), ensure_ascii=False)}")
        return "&".join(parts)

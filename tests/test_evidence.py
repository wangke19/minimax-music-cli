"""Tests for evidence chain and copyright reports."""
import json
from pathlib import Path

import pytest

from minimax_music.evidence.types import Action, Actor, ChainEntry
from minimax_music.evidence.chain import Chain, GENESIS_HASH
from minimax_music.evidence.recorder import Recorder
from minimax_music.report.markdown import generate_report


class TestChainEntry:
    def test_to_dict(self):
        from datetime import datetime
        entry = ChainEntry(
            seq=1,
            timestamp=datetime(2026, 1, 1, 12, 0, 0),
            action=Action.PROMPT_CREATE,
            actor=Actor.HUMAN,
            input={"prompt": "test"},
            prev_hash="sha256:abc",
            hash="sha256:def",
        )
        d = entry.to_dict()
        assert d["seq"] == 1
        assert d["action"] == "prompt_create"
        assert d["actor"] == "human"
        assert d["input"] == {"prompt": "test"}

    def test_from_dict(self):
        d = {
            "seq": 2,
            "timestamp": "2026-01-01T12:00:00",
            "action": "music_generate",
            "actor": "ai",
            "input": {"prompt": "test"},
            "prev_hash": "sha256:abc",
            "hash": "sha256:def",
        }
        entry = ChainEntry.from_dict(d)
        assert entry.seq == 2
        assert entry.action == Action.MUSIC_GENERATE
        assert entry.actor == Actor.AI

    def test_roundtrip(self):
        from datetime import datetime
        original = ChainEntry(
            seq=1,
            timestamp=datetime(2026, 5, 29, 10, 30, 0),
            action=Action.LYRICS_GENERATE,
            actor=Actor.AI,
            input={"prompt": "hello"},
        )
        d = original.to_dict()
        restored = ChainEntry.from_dict(d)
        assert restored.seq == original.seq
        assert restored.action == original.action
        assert restored.actor == original.actor


class TestChain:
    def test_append_creates_file(self, tmp_path):
        chain = Chain(tmp_path)
        from datetime import datetime
        entry = ChainEntry(
            seq=0,
            timestamp=datetime.now(),
            action=Action.PROMPT_CREATE,
            actor=Actor.HUMAN,
        )
        chain.append(entry)
        assert chain.chain_path.exists()
        lines = chain.chain_path.read_text().strip().split("\n")
        assert len(lines) == 1
        d = json.loads(lines[0])
        assert d["seq"] == 1
        assert d["prev_hash"] == GENESIS_HASH
        assert d["hash"].startswith("sha256:")

    def test_chain_hash_linking(self, tmp_path):
        chain = Chain(tmp_path)
        from datetime import datetime
        e1 = ChainEntry(seq=0, timestamp=datetime.now(), action=Action.PROMPT_CREATE, actor=Actor.HUMAN, input={"a": "1"})
        chain.append(e1)

        e2 = ChainEntry(seq=0, timestamp=datetime.now(), action=Action.LYRICS_GENERATE, actor=Actor.AI, input={"b": "2"})
        chain.append(e2)

        entries = chain.all_entries()
        assert len(entries) == 2
        assert entries[1].prev_hash == entries[0].hash

    def test_verify_valid_chain(self, tmp_path):
        chain = Chain(tmp_path)
        from datetime import datetime
        for action in [Action.PROMPT_CREATE, Action.LYRICS_GENERATE, Action.MUSIC_GENERATE]:
            e = ChainEntry(seq=0, timestamp=datetime.now(), action=action, actor=Actor.AI)
            chain.append(e)
        valid, issues = chain.verify()
        assert valid
        assert issues == []

    def test_verify_detects_tampering(self, tmp_path):
        chain = Chain(tmp_path)
        from datetime import datetime
        e = ChainEntry(seq=0, timestamp=datetime.now(), action=Action.PROMPT_CREATE, actor=Actor.HUMAN, input={"x": "original"})
        chain.append(e)

        # Tamper with the file
        lines = chain.chain_path.read_text().strip().split("\n")
        d = json.loads(lines[0])
        d["input"] = {"x": "tampered"}
        chain.chain_path.write_text(json.dumps(d, ensure_ascii=False) + "\n")

        tampered = Chain(tmp_path)
        valid, issues = tampered.verify()
        assert not valid
        assert any("tampered" in i for i in issues)

    def test_empty_chain_verifies(self, tmp_path):
        chain = Chain(tmp_path)
        valid, issues = chain.verify()
        assert valid
        assert issues == []

    def test_resume_from_existing(self, tmp_path):
        chain = Chain(tmp_path)
        from datetime import datetime
        e1 = ChainEntry(seq=0, timestamp=datetime.now(), action=Action.PROMPT_CREATE, actor=Actor.HUMAN)
        chain.append(e1)

        chain2 = Chain(tmp_path)
        assert chain2._last_seq == 1
        e2 = ChainEntry(seq=0, timestamp=datetime.now(), action=Action.LYRICS_GENERATE, actor=Actor.AI)
        chain2.append(e2)
        entries = chain2.all_entries()
        assert entries[1].seq == 2
        assert entries[1].prev_hash == entries[0].hash


class TestRecorder:
    def test_record_writes_to_chain(self, tmp_path):
        recorder = Recorder(tmp_path)
        recorder.record(Action.PROMPT_CREATE, Actor.HUMAN, {"prompt": "test"})
        recorder.record(Action.LYRICS_GENERATE, Actor.AI, {"prompt": "test"}, {"title": "My Song"})

        chain = Chain(tmp_path)
        entries = chain.all_entries()
        assert len(entries) == 2
        assert entries[0].action == Action.PROMPT_CREATE
        assert entries[1].action == Action.LYRICS_GENERATE


class TestReport:
    def test_generate_report(self, tmp_path):
        output_dir = tmp_path / "output"
        evidence_dir = tmp_path / "evidence"
        output_dir.mkdir()
        evidence_dir.mkdir()

        # Create evidence chain
        recorder = Recorder(evidence_dir)
        recorder.record(Action.PROMPT_CREATE, Actor.HUMAN, {"prompt": "test prompt"})
        recorder.record(Action.LYRICS_GENERATE, Actor.AI, {"prompt": "test"}, {"title": "Test"})
        recorder.record(Action.MUSIC_GENERATE, Actor.AI, {"prompt": "test"}, {"file": "test.mp3"})

        # Create a fake audio file
        (output_dir / "test.mp3").write_bytes(b"fake audio content")
        (output_dir / "test.txt").write_text("fake lyrics")

        report_path = generate_report(evidence_dir, output_dir, "test", "test prompt", False)

        assert report_path.exists()
        content = report_path.read_text()
        assert "版权证据链报告" in content
        assert "test" in content
        assert "人类贡献估算" in content
        assert "创作过程时间线" in content
        assert "证据链完整性校验" in content
        assert "文件指纹" in content
        assert "sha256:" in content

    def test_generate_report_instrumental(self, tmp_path):
        output_dir = tmp_path / "output"
        evidence_dir = tmp_path / "evidence"
        output_dir.mkdir()
        evidence_dir.mkdir()

        recorder = Recorder(evidence_dir)
        recorder.record(Action.PROMPT_CREATE, Actor.HUMAN, {"prompt": "epic chinese"})

        (output_dir / "epic-音乐.mp3").write_bytes(b"fake")

        report_path = generate_report(evidence_dir, output_dir, "epic-音乐", "epic chinese", True)
        content = report_path.read_text()
        assert "纯音乐" in content

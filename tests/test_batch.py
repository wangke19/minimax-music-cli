import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minimax_music.batch.manager import BatchManager
from minimax_music.batch.runner import BatchRunner, BatchResult
from minimax_music.generators.base import GenerationResult


class TestBatchManager:
    def test_load_no_progress_file(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p = tmp_path / "prompts.txt"
        p.write_text("pop\nrock\n")
        assert mgr.load(p) == set()

    def test_save_and_load(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p = tmp_path / "prompts.txt"
        p.write_text("pop\nrock\n")
        mgr.save(2, p)
        assert mgr.load(p) == {2}

    def test_save_multiple_and_load(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p = tmp_path / "prompts.txt"
        p.write_text("pop\nrock\njazz\n")
        mgr.save(1, p)
        mgr.save(3, p)
        assert mgr.load(p) == {1, 3}

    def test_clear(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p = tmp_path / "prompts.txt"
        p.write_text("pop\nrock\n")
        mgr.save(1, p)
        mgr.clear(p)
        assert mgr.load(p) == set()

    def test_clear_nonexistent(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p = tmp_path / "prompts.txt"
        p.write_text("pop\n")
        mgr.clear(p)
        assert mgr.load(p) == set()

    def test_different_prompts_files_independent(self, tmp_path):
        mgr = BatchManager(tmp_path)
        p1 = tmp_path / "a.txt"
        p2 = tmp_path / "b.txt"
        p1.write_text("pop\nrock\n")
        p2.write_text("jazz\nblues\n")
        mgr.save(1, p1)
        mgr.save(2, p2)
        assert mgr.load(p1) == {1}
        assert mgr.load(p2) == {2}

    def test_is_rate_limit_error_true(self):
        assert BatchManager.is_rate_limit_error("usage limit exceeded for today") is True

    def test_is_rate_limit_error_false(self):
        assert BatchManager.is_rate_limit_error("some other error") is False

    def test_is_rate_limit_error_case_insensitive(self):
        assert BatchManager.is_rate_limit_error("Usage Limit Exceeded") is True


class TestBatchRunner:
    @pytest.fixture
    def prompts_file(self, tmp_path):
        p = tmp_path / "prompts.txt"
        p.write_text("Pop, happy\n# comment\n\nRock, loud\nJazz, smooth\n", encoding="utf-8")
        return p

    @pytest.fixture
    def mock_generator(self):
        gen = MagicMock()
        gen.generate.return_value = GenerationResult(
            audio_path=Path("/fake/output.mp3"),
            lyrics_path=None,
            song_title="test",
            duration_ms=180000,
        )
        return gen

    def test_run_all_prompts(self, tmp_path, prompts_file, mock_generator):
        out = tmp_path / "output"
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=mock_generator,
            batch_manager=mgr,
            prompts_file=prompts_file,
            output_dir=out,
            delay_range=(0, 0),
        )

        with patch("time.sleep"):
            result = runner.run()

        assert result.total == 3  # 3 non-empty, non-comment lines
        assert result.success == 3
        assert result.failed == 0

    def test_resume_from_progress(self, tmp_path, prompts_file, mock_generator):
        out = tmp_path / "output"
        mgr = BatchManager(tmp_path)
        mgr.save(1, prompts_file)  # skip first line

        runner = BatchRunner(
            generator=mock_generator,
            batch_manager=mgr,
            prompts_file=prompts_file,
            output_dir=out,
            delay_range=(0, 0),
        )

        with patch("time.sleep"):
            result = runner.run()

        assert result.total == 3
        assert result.success == 2  # only 2 remaining
        assert mock_generator.generate.call_count == 2

    def test_failure_count(self, tmp_path, prompts_file):
        gen = MagicMock()
        gen.generate.side_effect = Exception("API error")

        out = tmp_path / "output"
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=gen,
            batch_manager=mgr,
            prompts_file=prompts_file,
            output_dir=out,
            delay_range=(0, 0),
        )

        with patch("time.sleep"):
            result = runner.run()

        assert result.failed == 3
        assert result.success == 0

    def test_rate_limit_exits(self, tmp_path, prompts_file):
        from minimax_music.config import RateLimitError

        gen = MagicMock()
        gen.generate.side_effect = RateLimitError("usage limit exceeded")

        out = tmp_path / "output"
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=gen,
            batch_manager=mgr,
            prompts_file=prompts_file,
            output_dir=out,
            delay_range=(0, 0),
        )

        with pytest.raises(SystemExit):
            runner.run()

        assert 1 in mgr.load(prompts_file)  # progress saved

    def test_empty_prompts_file(self, tmp_path):
        p = tmp_path / "empty.txt"
        p.write_text("\n# only comments\n", encoding="utf-8")

        gen = MagicMock()
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=gen,
            batch_manager=mgr,
            prompts_file=p,
            output_dir=tmp_path / "out",
            delay_range=(0, 0),
        )

        result = runner.run()
        assert result.total == 0
        gen.generate.assert_not_called()

    def test_missing_prompts_file(self, tmp_path):
        gen = MagicMock()
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=gen,
            batch_manager=mgr,
            prompts_file=tmp_path / "nonexistent.txt",
            output_dir=tmp_path / "out",
        )

        with pytest.raises(FileNotFoundError):
            runner.run()

    def test_clears_progress_on_completion(self, tmp_path, prompts_file, mock_generator):
        out = tmp_path / "output"
        mgr = BatchManager(tmp_path)
        runner = BatchRunner(
            generator=mock_generator,
            batch_manager=mgr,
            prompts_file=prompts_file,
            output_dir=out,
            delay_range=(0, 0),
        )

        with patch("time.sleep"):
            runner.run()

        assert mgr.load(prompts_file) == set()  # progress cleared
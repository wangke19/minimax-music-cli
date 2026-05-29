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
        assert mgr.load() == 0

    def test_save_and_load(self, tmp_path):
        mgr = BatchManager(tmp_path)
        mgr.save(42)
        assert mgr.load() == 42

    def test_clear(self, tmp_path):
        mgr = BatchManager(tmp_path)
        mgr.save(10)
        mgr.clear()
        assert mgr.load() == 0

    def test_clear_nonexistent(self, tmp_path):
        mgr = BatchManager(tmp_path)
        mgr.clear()  # should not raise

    def test_load_corrupt_file(self, tmp_path):
        mgr = BatchManager(tmp_path)
        mgr._path.write_text("not a number")
        assert mgr.load() == 0

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
        mgr.save(1)  # skip first line

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

        assert mgr.load() == 1  # progress saved

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

        assert mgr.load() == 0  # progress cleared

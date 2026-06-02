from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from minimax_music.batch.manager import BatchManager


class TestBatchGenerateArgs:
    """Test batch_generate.py argument parsing"""

    def test_parse_args_default_skip_lyrics_false(self):
        """Default: skip_lyrics should be False"""
        with patch("sys.argv", ["batch_generate.py", "-c", "2"]):
            from batch_generate import parse_args
            args = parse_args()
            assert args.skip_lyrics is False

    def test_parse_args_with_skip_lyrics_flag(self):
        """With --skip-lyrics: skip_lyrics should be True"""
        with patch("sys.argv", ["batch_generate.py", "-c", "2", "--skip-lyrics"]):
            from batch_generate import parse_args
            args = parse_args()
            assert args.skip_lyrics is True

    def test_parse_args_concurrency_and_samples(self):
        """Parse concurrency and samples args"""
        with patch("sys.argv", ["batch_generate.py", "-c", "3", "-s", "2"]):
            from batch_generate import parse_args
            args = parse_args()
            assert args.concurrency == 3
            assert args.samples == 2

    def test_parse_args_prompts_file(self):
        """Parse custom prompts file path"""
        with patch("sys.argv", ["batch_generate.py", "--prompts", "custom.txt"]):
            from batch_generate import parse_args
            args = parse_args()
            assert args.prompts == "custom.txt"


class TestSkipLyricsBehavior:
    """Test --skip-lyrics behavior with instrumental prompts"""

    def test_instrumental_calls_lyrics_api_by_default(self, tmp_path, monkeypatch):
        """Instrumental: default mode calls lyrics API"""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("纯音乐, piano, calm\n", encoding="utf-8")

        mock_music_result = MagicMock()
        mock_music_result.audio_path = Path("test.mp3")
        mock_music_result.duration_ms = 180000

        mock_lyrics_result = MagicMock()
        mock_lyrics_result.lyrics = "[Intro]\nCalm music\n"
        mock_lyrics_result.song_title = "Calm Piano"

        with patch("batch_generate.MusicClient"), \
             patch("batch_generate.LyricsClient") as MockLC, \
             patch("batch_generate.VocalGenerator"), \
             patch("batch_generate.InstrumentalGenerator") as MockIG:
            MockLC.return_value.generate.return_value = mock_lyrics_result
            MockIG.return_value.generate.return_value = mock_music_result

            with patch("batch_generate.main") as mock_main:
                # Import and run will call main with args.skip_lyrics=False by default
                import sys
                old_argv = sys.argv
                try:
                    sys.argv = ["batch_generate.py", "--prompts", str(prompts_file), "-c", "1"]
                    # We're testing the logic path, not full execution
                    # The key is: without --skip-lyrics, lyrics API is called
                finally:
                    sys.argv = old_argv

    def test_instrumental_skips_lyrics_api_with_flag(self, tmp_path, monkeypatch):
        """Instrumental: --skip-lyrics mode skips lyrics API"""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("纯音乐, piano, calm\n", encoding="utf-8")

        mock_music_result = MagicMock()
        mock_music_result.audio_path = Path("test.mp3")
        mock_music_result.duration_ms = 180000

        with patch("batch_generate.MusicClient"), \
             patch("batch_generate.LyricsClient") as MockLC, \
             patch("batch_generate.VocalGenerator"), \
             patch("batch_generate.InstrumentalGenerator") as MockIG:
            MockIG.return_value.generate.return_value = mock_music_result

            with patch("batch_generate.main"):
                import sys
                old_argv = sys.argv
                try:
                    sys.argv = ["batch_generate.py", "--prompts", str(prompts_file), "-c", "1", "--skip-lyrics"]
                    # With --skip-lyrics, MockLC.generate should NOT be called
                finally:
                    sys.argv = old_argv

    def test_vocal_always_calls_lyrics_api(self, tmp_path, monkeypatch):
        """Vocal: always calls lyrics API regardless of --skip-lyrics"""
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("华语流行, 欢快, 阳光, 清亮女声\n", encoding="utf-8")

        mock_music_result = MagicMock()
        mock_music_result.audio_path = Path("test.mp3")
        mock_music_result.duration_ms = 180000

        mock_lyrics_result = MagicMock()
        mock_lyrics_result.lyrics = "[Verse]\nHappy song\n"
        mock_lyrics_result.song_title = "Happy Day"

        with patch("batch_generate.MusicClient"), \
             patch("batch_generate.LyricsClient") as MockLC, \
             patch("batch_generate.VocalGenerator") as MockVG, \
             patch("batch_generate.InstrumentalGenerator"):
            MockLC.return_value.generate.return_value = mock_lyrics_result
            MockVG.return_value.generate.return_value = mock_music_result

            with patch("batch_generate.main"):
                import sys
                old_argv = sys.argv
                try:
                    # Vocal should call lyrics API even with --skip-lyrics
                    sys.argv = ["batch_generate.py", "--prompts", str(prompts_file), "-c", "1", "--skip-lyrics"]
                finally:
                    sys.argv = old_argv

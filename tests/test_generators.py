from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minimax_music.api.lyrics import LyricsResult
from minimax_music.api.music import MusicResult
from minimax_music.config import DownloadError
from minimax_music.generators.base import BaseGenerator, GenerationResult
from minimax_music.generators.instrumental import InstrumentalGenerator
from minimax_music.generators.vocal import VocalGenerator


@pytest.fixture
def mock_music_client():
    client = MagicMock()
    client.generate.return_value = MusicResult(
        audio_url="https://example.com/audio.mp3",
        duration_ms=180000,
        sample_rate=44100,
        bitrate=256000,
        file_size=0,
    )
    return client


@pytest.fixture
def mock_lyrics_client():
    client = MagicMock()
    client.generate.return_value = LyricsResult(
        song_title="测试歌名",
        style_tags=["pop"],
        lyrics="[Verse]\nHello world",
    )
    return client


class TestBaseGenerator:
    def test_validate_prompt_within_limit(self):
        BaseGenerator._validate_prompt("short prompt", max_chars=2000)

    def test_validate_prompt_exceeds_limit(self):
        with pytest.raises(ValueError, match="exceeds limit"):
            BaseGenerator._validate_prompt("x" * 2001, max_chars=2000)

    def test_download_audio_success(self, mock_music_client, tmp_path):
        dest = tmp_path / "test.mp3"
        with patch("minimax_music.generators.base.requests.get") as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200, content=b"fake audio data"
            )
            mock_get.return_value.raise_for_status = MagicMock()
            BaseGenerator._download_audio(mock_music_client, "https://example.com/a.mp3", dest)

        assert dest.exists()
        assert dest.read_bytes() == b"fake audio data"

    def test_download_audio_failure(self, mock_music_client, tmp_path):
        dest = tmp_path / "test.mp3"
        with patch("minimax_music.generators.base.requests.get") as mock_get:
            mock_get.side_effect = Exception("network error")
            with pytest.raises(DownloadError, match="Failed to download"):
                BaseGenerator._download_audio(mock_music_client, "https://bad.url", dest)

    def test_save_lyrics(self, tmp_path):
        path = tmp_path / "lyrics.txt"
        BaseGenerator._save_lyrics("Hello lyrics", path)
        assert path.read_text(encoding="utf-8") == "Hello lyrics"


class TestVocalGenerator:
    def test_generate_with_user_lyrics(self, mock_music_client, mock_lyrics_client, tmp_path):
        gen = VocalGenerator(mock_music_client, mock_lyrics_client)
        with patch.object(gen, "_download_audio"):
            result = gen.generate(
                prompt="Pop music",
                user_lyrics="[Verse]\nTest lyrics",
                output_dir=tmp_path,
            )

        assert isinstance(result, GenerationResult)
        assert result.lyrics_path is not None
        assert result.lyrics_path.exists()
        assert "[Verse]" in result.lyrics_path.read_text()

    def test_generate_with_ai_lyrics(self, mock_music_client, mock_lyrics_client, tmp_path):
        gen = VocalGenerator(mock_music_client, mock_lyrics_client)
        with patch.object(gen, "_download_audio"):
            result = gen.generate(
                prompt="Pop music",
                use_ai_lyrics=True,
                output_dir=tmp_path,
            )

        mock_lyrics_client.generate.assert_called_once()
        assert result.song_title == "测试歌名"
        assert result.audio_path.name == "测试歌名.mp3"

    def test_generate_default_lyrics_when_empty(self, mock_music_client, mock_lyrics_client, tmp_path):
        gen = VocalGenerator(mock_music_client, mock_lyrics_client)
        with patch.object(gen, "_download_audio"):
            result = gen.generate(prompt="Pop music", output_dir=tmp_path)

        saved = result.lyrics_path.read_text()
        assert "[Intro]" in saved

    def test_generate_creates_output_dir(self, mock_music_client, mock_lyrics_client, tmp_path):
        out = tmp_path / "nested" / "dir"
        gen = VocalGenerator(mock_music_client, mock_lyrics_client)
        with patch.object(gen, "_download_audio"):
            gen.generate(prompt="test", output_dir=out)
        assert out.exists()

    def test_generate_custom_name(self, mock_music_client, mock_lyrics_client, tmp_path):
        gen = VocalGenerator(mock_music_client, mock_lyrics_client)
        with patch.object(gen, "_download_audio"):
            result = gen.generate(
                prompt="test",
                song_title="custom_name",
                output_dir=tmp_path,
            )
        assert result.audio_path.name == "custom_name.mp3"


class TestInstrumentalGenerator:
    def test_generate(self, mock_music_client, tmp_path):
        gen = InstrumentalGenerator(mock_music_client)
        with patch.object(gen, "_download_audio"):
            result = gen.generate(prompt="纯音乐, 钢琴, 宁静", output_dir=tmp_path)

        assert isinstance(result, GenerationResult)
        assert result.lyrics_path is None
        assert result.audio_path.suffix == ".mp3"

    def test_generate_no_lyrics_sent(self, mock_music_client, tmp_path):
        gen = InstrumentalGenerator(mock_music_client)
        with patch.object(gen, "_download_audio"):
            gen.generate(prompt="piano calm", output_dir=tmp_path)

        call_kwargs = mock_music_client.generate.call_args
        assert call_kwargs.kwargs["is_instrumental"] is True

    def test_generate_creates_output_dir(self, mock_music_client, tmp_path):
        out = tmp_path / "deep" / "nested"
        gen = InstrumentalGenerator(mock_music_client)
        with patch.object(gen, "_download_audio"):
            gen.generate(prompt="test", output_dir=out)
        assert out.exists()

import os

import pytest

from minimax_music.config import (
    ALL_MODELS,
    API_BASE_URL,
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    AUDIO_SAMPLE_RATES,
    LYRICS_MAX_CHARS,
    LYRICS_TAGS,
    PROMPT_MAX_CHARS,
    AuthError,
    DownloadError,
    MiniMaxError,
    NetworkError,
    RateLimitError,
    get_api_key,
)


class TestConstants:
    def test_api_base_url(self):
        assert API_BASE_URL == "https://api.minimaxi.com/v1"

    def test_models_list(self):
        assert len(ALL_MODELS) == 4
        assert "music-2.6" in ALL_MODELS
        assert "music-cover" in ALL_MODELS
        assert "music-2.6-free" in ALL_MODELS
        assert "music-cover-free" in ALL_MODELS

    def test_limits(self):
        assert PROMPT_MAX_CHARS == 2000
        assert LYRICS_MAX_CHARS == 3500

    def test_audio_settings(self):
        assert 44100 in AUDIO_SAMPLE_RATES
        assert 256000 in AUDIO_BITRATES
        assert "mp3" in AUDIO_FORMATS

    def test_lyrics_tags_count(self):
        assert len(LYRICS_TAGS) == 14


class TestExceptions:
    def test_hierarchy(self):
        assert issubclass(AuthError, MiniMaxError)
        assert issubclass(RateLimitError, MiniMaxError)
        assert issubclass(NetworkError, MiniMaxError)
        assert issubclass(DownloadError, MiniMaxError)

    def test_all_catchable_as_minimax_error(self):
        with pytest.raises(MiniMaxError):
            raise AuthError("auth failed")

        with pytest.raises(MiniMaxError):
            raise RateLimitError("limit exceeded")

        with pytest.raises(MiniMaxError):
            raise NetworkError("timeout")

        with pytest.raises(MiniMaxError):
            raise DownloadError("download failed")


class TestGetApiKey:
    def test_returns_env_var(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key-123")
        assert get_api_key() == "test-key-123"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        with pytest.raises(AuthError, match="MINIMAX_API_KEY"):
            get_api_key()

    def test_raises_when_empty(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_API_KEY", "")
        with pytest.raises(AuthError, match="MINIMAX_API_KEY"):
            get_api_key()

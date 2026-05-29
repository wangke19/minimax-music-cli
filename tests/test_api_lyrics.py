from unittest.mock import MagicMock

import pytest

from minimax_music.api.lyrics import LyricsClient, LyricsResult


@pytest.fixture
def lyrics_client():
    client = LyricsClient("test-key")
    client._post = MagicMock(return_value={
        "song_title": "测试歌曲",
        "style_tags": ["pop", "happy"],
        "lyrics": "[Verse]\nHello world",
    })
    return client


class TestLyricsClient:
    def test_generate_returns_lyrics_result(self, lyrics_client):
        result = lyrics_client.generate(prompt="Pop music")
        assert isinstance(result, LyricsResult)
        assert result.song_title == "测试歌曲"
        assert result.style_tags == ["pop", "happy"]
        assert "[Verse]" in result.lyrics

    def test_generate_default_mode(self, lyrics_client):
        lyrics_client.generate(prompt="test")
        call_args = lyrics_client._post.call_args
        assert call_args[0][1]["mode"] == "write_full_song"

    def test_generate_custom_mode(self, lyrics_client):
        lyrics_client.generate(prompt="test", mode="edit")
        call_args = lyrics_client._post.call_args
        assert call_args[0][1]["mode"] == "edit"

    def test_generate_with_title(self, lyrics_client):
        lyrics_client.generate(prompt="test", title="My Song")
        call_args = lyrics_client._post.call_args
        assert call_args[0][1]["title"] == "My Song"

    def test_generate_without_title(self, lyrics_client):
        lyrics_client.generate(prompt="test")
        call_args = lyrics_client._post.call_args
        assert "title" not in call_args[0][1]

    def test_generate_missing_fields_defaults(self, lyrics_client):
        lyrics_client._post.return_value = {}
        result = lyrics_client.generate(prompt="test")
        assert result.song_title == ""
        assert result.style_tags == []
        assert result.lyrics == ""

    def test_calls_correct_endpoint(self, lyrics_client):
        lyrics_client.generate(prompt="test")
        call_args = lyrics_client._post.call_args
        assert call_args[0][0] == "/lyrics_generation"

    def test_passes_prompt(self, lyrics_client):
        lyrics_client.generate(prompt="Jazz, romantic")
        call_args = lyrics_client._post.call_args
        assert call_args[0][1]["prompt"] == "Jazz, romantic"

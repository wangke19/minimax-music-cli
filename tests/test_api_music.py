from unittest.mock import MagicMock

import pytest

from minimax_music.api.music import MusicClient, MusicResult


@pytest.fixture
def music_client():
    client = MusicClient("test-key")
    client._post = MagicMock(return_value={
        "data": {"audio": "https://example.com/audio.mp3"},
        "extra_info": {
            "music_duration": 180000,
            "music_sample_rate": 44100,
            "bitrate": 256000,
        },
    })
    return client


class TestMusicClient:
    def test_generate_returns_music_result(self, music_client):
        result = music_client.generate(prompt="Pop music", lyrics="la la la")
        assert isinstance(result, MusicResult)
        assert result.audio_url == "https://example.com/audio.mp3"
        assert result.duration_ms == 180000
        assert result.sample_rate == 44100
        assert result.bitrate == 256000

    def test_generate_includes_lyrics(self, music_client):
        music_client.generate(prompt="test", lyrics="verse 1")
        call_args = music_client._post.call_args
        assert call_args[0][1]["lyrics"] == "verse 1"

    def test_generate_instrumental_no_lyrics(self, music_client):
        music_client.generate(prompt="piano", is_instrumental=True)
        call_args = music_client._post.call_args
        assert "lyrics" not in call_args[0][1]

    def test_generate_default_model(self, music_client):
        music_client.generate(prompt="test")
        call_args = music_client._post.call_args
        assert call_args[0][1]["model"] == "music-2.6"

    def test_generate_custom_model(self, music_client):
        music_client.generate(prompt="test", model="music-cover")
        call_args = music_client._post.call_args
        assert call_args[0][1]["model"] == "music-cover"

    def test_generate_invalid_sample_rate(self, music_client):
        with pytest.raises(ValueError, match="sample_rate"):
            music_client.generate(prompt="test", sample_rate=99999)

    def test_generate_invalid_bitrate(self, music_client):
        with pytest.raises(ValueError, match="bitrate"):
            music_client.generate(prompt="test", bitrate=99999)

    def test_generate_no_audio_url_raises(self, music_client):
        music_client._post.return_value = {"data": {}, "extra_info": {}}
        with pytest.raises(Exception, match="No audio URL"):
            music_client.generate(prompt="test")

    def test_generate_passes_audio_settings(self, music_client):
        music_client.generate(
            prompt="test", sample_rate=32000, bitrate=128000, audio_format="wav"
        )
        call_args = music_client._post.call_args
        settings = call_args[0][1]["audio_setting"]
        assert settings["sample_rate"] == 32000
        assert settings["bitrate"] == 128000
        assert settings["format"] == "wav"

    def test_generate_duration_default(self, music_client):
        music_client.generate(prompt="test")
        call_args = music_client._post.call_args
        assert call_args[0][1]["is_instrumental"] is False

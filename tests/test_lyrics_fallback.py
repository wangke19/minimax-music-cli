from unittest.mock import MagicMock

import pytest

from minimax_music.api.lyrics import LyricsResult
from minimax_music.lyrics.claude_lyrics import ClaudeLyricsClient
from minimax_music.lyrics.fallback import FallbackLyricsClient


@pytest.fixture
def primary_success():
    """MiniMax-style primary client that succeeds."""
    client = MagicMock()
    client.generate.return_value = LyricsResult(
        song_title="MiniMax Title",
        style_tags=["pop"],
        lyrics="[Verse]\nMiniMax lyrics",
    )
    return client


@pytest.fixture
def primary_failure():
    """MiniMax-style primary client that raises (e.g., API Error 1033)."""
    client = MagicMock()
    client.generate.side_effect = Exception("API Error (1033): system error, empty response from LLM")
    return client


@pytest.fixture
def fallback_success():
    """Claude fallback client that succeeds."""
    client = MagicMock()
    client.generate.return_value = LyricsResult(
        song_title="Claude Title",
        style_tags=[],
        lyrics="[Verse 1]\nClaude lyrics",
    )
    return client


class TestFallbackLyricsClient:
    def test_uses_primary_when_it_succeeds(self, primary_success, fallback_success):
        client = FallbackLyricsClient(primary=primary_success, fallback=fallback_success)
        result = client.generate("test prompt")
        assert result.song_title == "MiniMax Title"
        assert "MiniMax" in result.lyrics
        primary_success.generate.assert_called_once()
        fallback_success.generate.assert_not_called()

    def test_falls_back_when_primary_raises(self, primary_failure, fallback_success):
        client = FallbackLyricsClient(primary=primary_failure, fallback=fallback_success)
        result = client.generate("test prompt")
        assert result.song_title == "Claude Title"
        assert "Claude" in result.lyrics
        primary_failure.generate.assert_called_once()
        fallback_success.generate.assert_called_once()

    def test_propagates_args_to_primary(self, primary_success, fallback_success):
        client = FallbackLyricsClient(primary=primary_success, fallback=fallback_success)
        client.generate("prompt", mode="edit", title="MyTitle")
        args, kwargs = primary_success.generate.call_args
        assert args[0] == "prompt"
        assert kwargs == {"mode": "edit", "title": "MyTitle"}

    def test_propagates_same_args_to_fallback(self, primary_failure, fallback_success):
        client = FallbackLyricsClient(primary=primary_failure, fallback=fallback_success)
        client.generate("prompt", mode="edit", title="MyTitle")
        args, kwargs = fallback_success.generate.call_args
        assert args[0] == "prompt"
        assert kwargs == {"mode": "edit", "title": "MyTitle"}

    def test_reraises_when_no_fallback_configured(self, primary_failure):
        client = FallbackLyricsClient(primary=primary_failure, fallback=None)
        with pytest.raises(Exception, match="1033"):
            client.generate("test prompt")

    def test_reraises_when_fallback_also_fails(self, primary_failure):
        fallback = MagicMock()
        fallback.generate.side_effect = Exception("Anthropic API error 500")
        client = FallbackLyricsClient(primary=primary_failure, fallback=fallback)
        with pytest.raises(Exception, match="Anthropic API error 500"):
            client.generate("test prompt")

    def test_fallback_None_is_default(self, primary_success):
        client = FallbackLyricsClient(primary=primary_success)
        # Should still work via primary
        result = client.generate("test prompt")
        assert result.song_title == "MiniMax Title"


class TestClaudeLyricsClient:
    def test_generate_returns_lyrics_result(self):
        anthropic = MagicMock()
        anthropic.generate_text.return_value = "[Verse 1]\nHello world\n[Chorus]\nYeah"
        client = ClaudeLyricsClient(anthropic)

        result = client.generate("test prompt")

        assert isinstance(result, LyricsResult)
        assert "[Verse 1]" in result.lyrics
        assert "Hello world" in result.lyrics

    def test_generate_strips_markdown_fences(self):
        anthropic = MagicMock()
        anthropic.generate_text.return_value = "```english\n[Verse 1]\nHello\n```"
        client = ClaudeLyricsClient(anthropic)

        result = client.generate("test prompt")

        assert result.lyrics.startswith("[Verse 1]")
        assert "```" not in result.lyrics

    def test_generate_uses_provided_title(self):
        anthropic = MagicMock()
        anthropic.generate_text.return_value = "[Verse]\nHello"
        client = ClaudeLyricsClient(anthropic)

        result = client.generate("test prompt", title="My Song")

        assert result.song_title == "My Song"

    def test_generate_derives_title_when_not_provided(self):
        anthropic = MagicMock()
        # First call returns lyrics, second call (for title) returns the title
        anthropic.generate_text.side_effect = [
            "[Verse]\nHello",
            "Midnight Plea",
        ]
        client = ClaudeLyricsClient(anthropic)

        result = client.generate("test prompt")

        assert result.song_title == "Midnight Plea"

    def test_generate_returns_empty_title_when_derivation_fails(self):
        anthropic = MagicMock()
        anthropic.generate_text.side_effect = [
            "[Verse]\nHello",
            Exception("title API failed"),
        ]
        client = ClaudeLyricsClient(anthropic)

        result = client.generate("test prompt")

        assert result.song_title == ""
        assert "[Verse]" in result.lyrics

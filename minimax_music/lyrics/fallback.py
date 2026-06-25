"""Fallback lyrics client: tries primary (MiniMax) first, falls back to Claude on failure."""

from typing import Optional

from ..api.lyrics import LyricsClient, LyricsResult
from .claude_lyrics import ClaudeLyricsClient


class FallbackLyricsClient:
    """Wraps a primary LyricsClient with an optional Claude fallback.

    If the primary raises any exception and a fallback is configured, the
    fallback is invoked and its result returned. If no fallback is configured,
    the original exception propagates (preserving upstream behavior).
    """

    def __init__(
        self,
        primary: LyricsClient,
        fallback: Optional[ClaudeLyricsClient] = None,
    ):
        self._primary = primary
        self._fallback = fallback

    def generate(
        self,
        prompt: str,
        mode: str = "write_full_song",
        title: str | None = None,
    ) -> LyricsResult:
        try:
            return self._primary.generate(prompt, mode=mode, title=title)
        except Exception as primary_err:
            if self._fallback is None:
                raise
            print(
                f"[fallback] MiniMax lyrics failed ({primary_err}); using Claude",
                flush=True,
            )
            return self._fallback.generate(prompt, mode=mode, title=title)

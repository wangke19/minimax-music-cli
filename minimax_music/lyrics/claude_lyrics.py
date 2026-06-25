"""Claude-based lyrics generator as fallback when MiniMax lyrics API fails.

Adapter that wraps AnthropicClient to produce LyricsResult (same interface as LyricsClient).
"""

import re

from ..api.anthropic_client import AnthropicClient
from ..api.lyrics import LyricsResult


_LYRICS_SYSTEM_PROMPT = """\
You are a professional songwriter. Generate complete, original song lyrics based on the user's style description.

Output rules (strict):
1. Use structural tags in square brackets: [Verse 1], [Pre-Chorus], [Chorus], [Verse 2], [Bridge], [Final Chorus].
2. Match the language implied by the prompt (English prompts → English lyrics; Chinese prompts → Chinese lyrics).
3. Length: 200-300 words total (about 4-5 minutes when sung).
4. Rhyme and meter must support singing. Avoid spoken-word or rap-style dense phrasing unless explicitly requested.
5. Output ONLY the lyrics. No preamble, no commentary, no title line outside the lyrics.
6. The first line of your output MUST be a tag like [Verse 1].
"""


_TITLE_SYSTEM_PROMPT = """\
You are a song titling expert. Given a song's style/scenario description, produce a short, evocative title.

Rules:
1. Output 2-4 words in Title Case (e.g., "Midnight Plea", "Fading Photographs", "Father's Waltz").
2. Match the language of the description (English description → English title).
3. Evoke the core emotion or scenario; avoid generic words like "Song" or "Music".
4. Output ONLY the title. No quotes, no punctuation at the end, no explanation.
"""


class ClaudeLyricsClient:
    """Lyrics generator backed by Anthropic Claude. Same generate() signature as LyricsClient."""

    def __init__(self, anthropic_client: AnthropicClient):
        self._client = anthropic_client

    def generate(
        self,
        prompt: str,
        mode: str = "write_full_song",
        title: str | None = None,
    ) -> LyricsResult:
        user_msg = f"Style/scenario description:\n{prompt}\n\nWrite the full song lyrics."
        if title:
            user_msg += f"\n\nUse this as the working title (do NOT include it in the lyrics output): {title}"

        lyrics = self._client.generate_text(
            system=_LYRICS_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=1500,
            temperature=0.8,
        )
        lyrics = _strip_fences(lyrics)

        song_title = title or self._derive_title(prompt)
        return LyricsResult(song_title=song_title or "", style_tags=[], lyrics=lyrics)

    def _derive_title(self, prompt: str) -> str:
        try:
            raw = self._client.generate_text(
                system=_TITLE_SYSTEM_PROMPT,
                user=f"Description:\n{prompt[:500]}\n\nTitle:",
                max_tokens=20,
                temperature=0.7,
                timeout=30,
            )
            return _clean_title(raw)
        except Exception:
            return ""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip()


def _clean_title(raw: str) -> str:
    raw = raw.strip().strip('"\'""''《》【】')
    raw = raw.splitlines()[0] if raw else ""
    raw = raw.strip().rstrip(".!?")
    return raw

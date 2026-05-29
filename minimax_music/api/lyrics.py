from dataclasses import dataclass, field

from .client import BaseClient


@dataclass
class LyricsResult:
    song_title: str
    style_tags: list[str] = field(default_factory=list)
    lyrics: str = ""


class LyricsClient(BaseClient):
    def generate(
        self,
        prompt: str,
        mode: str = "write_full_song",
        title: str | None = None,
    ) -> LyricsResult:
        payload = {"prompt": prompt, "mode": mode}
        if title:
            payload["title"] = title

        result = self._post("/lyrics_generation", payload, timeout=60)

        return LyricsResult(
            song_title=result.get("song_title", ""),
            style_tags=result.get("style_tags", []),
            lyrics=result.get("lyrics", ""),
        )

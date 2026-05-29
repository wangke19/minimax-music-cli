from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import requests

from ..api.music import MusicClient
from ..config import DownloadError


@dataclass
class GenerationResult:
    audio_path: Path
    lyrics_path: Path | None
    song_title: str | None
    duration_ms: int


class BaseGenerator(ABC):
    def __init__(self, music_client: MusicClient):
        self._music = music_client

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> GenerationResult: ...

    def _download_audio(self, url: str, path: Path) -> None:
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            path.write_bytes(resp.content)
        except Exception as e:
            raise DownloadError(f"Failed to download audio: {e}")

    @staticmethod
    def _validate_prompt(prompt: str, max_chars: int = 2000) -> None:
        if len(prompt) > max_chars:
            raise ValueError(f"Prompt ({len(prompt)} chars) exceeds limit of {max_chars}")

    @staticmethod
    def _save_lyrics(lyrics: str, path: Path) -> None:
        path.write_text(lyrics, encoding="utf-8")

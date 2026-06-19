from pathlib import Path

from ..api.lyrics import LyricsClient
from ..api.music import MusicClient
from ..naming import generate_name, resolve_filename_collision
from ..prompts import format_prompt_for_lyrics
from .base import BaseGenerator, GenerationResult


class VocalGenerator(BaseGenerator):
    def __init__(self, music_client: MusicClient, lyrics_client: LyricsClient):
        super().__init__(music_client)
        self._lyrics = lyrics_client

    def generate(
        self,
        prompt: str,
        use_ai_lyrics: bool = False,
        user_lyrics: str = "",
        song_title: str | None = None,
        output_dir: Path = Path("./mp3"),
        duration: int = 300,
        no_format_prompt: bool = False,
        model: str = "music-2.6",
        save_lyrics_file: bool = True,
        skip_collision_check: bool = False,
        **kwargs,
    ) -> GenerationResult:
        self._validate_prompt(prompt)
        output_dir.mkdir(parents=True, exist_ok=True)

        lyrics = user_lyrics
        title = song_title

        if use_ai_lyrics:
            lyrics_prompt = format_prompt_for_lyrics(prompt, duration_hint="约5分钟完整歌曲")
            lyrics_result = self._lyrics.generate(lyrics_prompt)
            lyrics = lyrics_result.lyrics
            title = title or lyrics_result.song_title

        if not lyrics:
            lyrics = "[Intro]\nLa la la"

        name = generate_name(prompt, song_title=title, is_instrumental=False)
        if skip_collision_check:
            final_audio_name = name
        else:
            final_audio_name = resolve_filename_collision(name, output_dir, ".mp3")
        audio_path = output_dir / f"{final_audio_name}.mp3"
        lyrics_path = output_dir / f"{final_audio_name}.txt"

        if save_lyrics_file:
            self._save_lyrics(lyrics, lyrics_path)

        final_prompt = prompt if no_format_prompt else prompt
        result = self._music.generate(
            prompt=final_prompt,
            lyrics=lyrics,
            is_instrumental=False,
            duration=duration,
            model=model,
        )

        self._download_audio(result.audio_url, audio_path)

        return GenerationResult(
            audio_path=audio_path,
            lyrics_path=lyrics_path if save_lyrics_file else None,
            song_title=title,
            duration_ms=result.duration_ms,
        )

from pathlib import Path

from ..api.music import MusicClient
from ..naming import generate_name, resolve_filename_collision
from .base import BaseGenerator, GenerationResult


class InstrumentalGenerator(BaseGenerator):
    def generate(
        self,
        prompt: str,
        output_dir: Path = Path("./mp3"),
        duration: int = 300,
        model: str = "music-2.6",
        song_title: str | None = None,
        skip_collision_check: bool = False,
        **kwargs,
    ) -> GenerationResult:
        self._validate_prompt(prompt)
        output_dir.mkdir(parents=True, exist_ok=True)

        name = generate_name(prompt, song_title=song_title, is_instrumental=True)
        if skip_collision_check:
            final_name = name
        else:
            final_name = resolve_filename_collision(name, output_dir, ".mp3")
        audio_path = output_dir / f"{final_name}.mp3"

        result = self._music.generate(
            prompt=prompt,
            is_instrumental=True,
            duration=duration,
            model=model,
        )

        self._download_audio(result.audio_url, audio_path)

        return GenerationResult(
            audio_path=audio_path,
            lyrics_path=None,
            song_title=song_title,
            duration_ms=result.duration_ms,
        )

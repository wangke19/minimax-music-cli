from dataclasses import dataclass

from ..config import (
    AUDIO_BITRATES,
    AUDIO_SAMPLE_RATES,
    MODEL_MUSIC_2_6,
)
from .client import BaseClient


@dataclass
class MusicResult:
    audio_url: str
    duration_ms: int
    sample_rate: int
    bitrate: int
    file_size: int


class MusicClient(BaseClient):
    def generate(
        self,
        prompt: str,
        lyrics: str = "",
        is_instrumental: bool = False,
        model: str = MODEL_MUSIC_2_6,
        sample_rate: int = 44100,
        bitrate: int = 256000,
        audio_format: str = "mp3",
        output_format: str = "url",
        stream: bool = False,
        aigc_watermark: bool = False,
        lyrics_optimizer: bool = False,
        ref_audio_url: str | None = None,
        audio_base64: str | None = None,
        cover_feature_id: str | None = None,
    ) -> MusicResult:
        if sample_rate not in AUDIO_SAMPLE_RATES:
            raise ValueError(f"Invalid sample_rate. Must be one of: {AUDIO_SAMPLE_RATES}")
        if bitrate not in AUDIO_BITRATES:
            raise ValueError(f"Invalid bitrate. Must be one of: {AUDIO_BITRATES}")

        payload: dict = {
            "model": model,
            "prompt": prompt,
            "is_instrumental": is_instrumental,
            "audio_setting": {
                "sample_rate": sample_rate,
                "bitrate": bitrate,
                "format": audio_format,
            },
            "output_format": output_format,
        }

        if not is_instrumental and lyrics:
            payload["lyrics"] = lyrics

        if stream:
            payload["stream"] = True

        if aigc_watermark:
            payload["aigc_watermark"] = True

        if lyrics_optimizer:
            payload["lyrics_optimizer"] = True

        if ref_audio_url:
            payload["audio_url"] = ref_audio_url

        if audio_base64:
            payload["audio_base64"] = audio_base64

        if cover_feature_id:
            payload["cover_feature_id"] = cover_feature_id

        result = self._post("/music_generation", payload, timeout=300)

        audio_url = result.get("data", {}).get("audio")
        if not audio_url:
            raise Exception("No audio URL in response")

        extra = result.get("extra_info", {})
        return MusicResult(
            audio_url=audio_url,
            duration_ms=extra.get("music_duration", 0),
            sample_rate=extra.get("music_sample_rate", sample_rate),
            bitrate=extra.get("bitrate", bitrate),
            file_size=0,
        )

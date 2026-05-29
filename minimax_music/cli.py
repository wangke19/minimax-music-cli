import argparse
import json
import os
import re
import sys
from pathlib import Path

from .config import (
    ALL_MODELS,
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    AUDIO_SAMPLE_RATES,
    MODEL_MUSIC_2_6,
    RateLimitError,
    check_concurrency_warning,
    detect_account_tier,
    get_api_key,
)
from .api.music import MusicClient
from .api.lyrics import LyricsClient
from .generators.vocal import VocalGenerator
from .generators.instrumental import InstrumentalGenerator
from .generators.base import GenerationResult
from .naming import generate_name, generate_name_with_llm
from .prompts import format_prompt_for_lyrics
from .evidence.recorder import Recorder
from .evidence.types import Action, Actor
from .report.markdown import generate_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="MiniMax Music Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Config file
    p.add_argument("--param-file", "-f", help="Load parameters from config file (JSON or TXT)")
    p.add_argument("--vars", "-v", help="Template variables (key=value,key=value)")

    # Direct parameters
    p.add_argument("--prompt", "-p", help="Music style/prompt (max 2000 chars)")
    p.add_argument("--lyrics", "-l", help="Song lyrics (max 3500 chars)")
    p.add_argument("--name", "-n", help="Output filename (without extension)")
    p.add_argument("--output", "-o", default="./mp3", help="Output directory")

    # Generation modes
    p.add_argument("--use-lyrics-gen", action="store_true", help="Generate lyrics via API first")
    p.add_argument("--instrumental", "-i", action="store_true", help="Pure instrumental (no vocals)")
    p.add_argument("--lyrics-optimizer", action="store_true", help="Auto-generate lyrics from prompt")
    p.add_argument("--no-format-prompt", action="store_true", help="Use raw prompt without formatting")

    # Samples
    p.add_argument("--samples", "-s", type=int, default=1, help="Number of samples to generate per prompt (default: 1)")

    # Model & audio settings
    p.add_argument("--model", default=MODEL_MUSIC_2_6, choices=ALL_MODELS)
    p.add_argument("--duration", "-d", type=int, default=300, help="Duration in seconds (max 300)")
    p.add_argument("--sample-rate", type=int, default=44100, choices=AUDIO_SAMPLE_RATES)
    p.add_argument("--bitrate", type=int, default=256000, choices=AUDIO_BITRATES)
    p.add_argument("--format", default="mp3", choices=AUDIO_FORMATS)

    # Advanced
    p.add_argument("--stream", action="store_true", help="Streaming mode")
    p.add_argument("--aigc-watermark", action="store_true", help="Add AIGC watermark")
    p.add_argument("--audio-url", default=None, help="Reference audio URL (for cover model)")
    p.add_argument("--audio-base64", default=None, help="Reference audio base64 (for cover model)")

    return p.parse_args(argv)


def _load_file_content(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def _parse_music_template(content: str) -> dict:
    result = {}
    pattern = r"(?:^|\n)\[(风格|歌词|歌名)\]\n"
    matches = list(re.finditer(pattern, content))
    for idx, match in enumerate(matches):
        header = match.group(1)
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        section = content[start:end].rstrip("\n")
        if header == "风格":
            result["prompt"] = section
        elif header == "歌词":
            result["lyrics"] = section
        elif header == "歌名":
            result["name"] = section.replace(" ", "_").replace("\n", "")
    return result


def parse_config_file(filepath: str) -> dict:
    content = _load_file_content(filepath).strip()
    if "[风格]" in content or "[歌词]" in content:
        return _parse_music_template(content)
    if content.startswith("{"):
        return json.loads(content)
    result = {}
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def fill_template(template: str, variables: dict) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
        result = result.replace(f"${key}", str(value))
    return result


def _generate_sample_suffix(sample_idx: int, total_samples: int) -> str:
    if total_samples > 1:
        return chr(ord('A') + sample_idx - 1)
    return ""


def run(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    # Build template variables
    variables = {}
    if args.vars:
        for kv in args.vars.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                variables[k.strip()] = v.strip()

    # Load from config file
    params = {}
    if args.param_file:
        params.update(parse_config_file(args.param_file))

    # Override with direct args
    if args.prompt:
        params["prompt"] = args.prompt
    if args.lyrics:
        params["lyrics"] = args.lyrics
    if args.name:
        params["name"] = args.name

    if "prompt" not in params:
        print("Error: --prompt is required (via -p or --param-file)")
        sys.exit(1)

    if "lyrics" not in params:
        params["lyrics"] = "[Intro]\nLa la la"

    prompt = fill_template(params["prompt"], variables)
    lyrics = fill_template(params.get("lyrics", ""), variables) if params.get("lyrics") else ""
    user_name = fill_template(params.get("name", ""), variables) if params.get("name") else None

    output_dir = Path(args.output)

    try:
        api_key = get_api_key()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Generate name: user-provided > LLM > rule-based
    base_name = user_name
    if not base_name:
        llm_name = generate_name_with_llm(api_key, prompt)
        if llm_name:
            print(f"Generated name: {llm_name}")
            base_name = llm_name.replace(" ", "_")
        else:
            base_name = generate_name(prompt, is_instrumental=args.instrumental).replace(" ", "_")

    music_client = MusicClient(api_key)
    lyrics_client = LyricsClient(api_key)

    # Setup evidence recorder
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = output_dir / "evidence"
    recorder = Recorder(evidence_dir)

    # Warn if samples may exceed API concurrency limits
    tier = detect_account_tier(api_key)
    warning = check_concurrency_warning(tier, args.samples, args.samples)
    if warning:
        print(f"\n{warning}")

    try:
        # Step 1: Record human prompt
        recorder.record(
            action=Action.PROMPT_CREATE,
            actor=Actor.HUMAN,
            input_data={"prompt": prompt[:200], "instrumental": args.instrumental},
        )

        # Step 2: Generate lyrics once (shared across all samples)
        song_lyrics = ""
        song_title = None

        if args.instrumental:
            lyrics_prompt = format_prompt_for_lyrics(prompt, duration_hint="纯音乐描述")
            lyrics_result = lyrics_client.generate(lyrics_prompt)
            song_lyrics = lyrics_result.lyrics
            song_title = lyrics_result.song_title
            recorder.record(
                action=Action.LYRICS_GENERATE,
                actor=Actor.AI,
                input_data={"prompt": lyrics_prompt[:100]},
                output_data={"title": song_title, "lyrics_length": len(song_lyrics or "")},
            )
        elif args.use_lyrics_gen:
            lyrics_prompt = format_prompt_for_lyrics(prompt, duration_hint="约5分钟完整歌曲")
            lyrics_result = lyrics_client.generate(lyrics_prompt)
            song_lyrics = lyrics_result.lyrics
            song_title = lyrics_result.song_title
            recorder.record(
                action=Action.LYRICS_GENERATE,
                actor=Actor.AI,
                input_data={"prompt": lyrics_prompt[:100]},
                output_data={"title": song_title, "lyrics_length": len(song_lyrics or "")},
            )
        else:
            song_lyrics = lyrics

        if not song_lyrics:
            song_lyrics = "[Intro]\nLa la la"

        # Step 2: Determine base name
        name = base_name or song_title
        if not name:
            name = generate_name(prompt, is_instrumental=args.instrumental).replace(" ", "_")

        # Step 3: Build file naming based on type
        # Instrumental: base-音乐.mp3, vocal: base.mp3
        # Multi-sample: baseA-音乐.mp3 / baseB-音乐.mp3 (inst), baseA.mp3 / baseB.mp3 (vocal)
        inst_tag = "-音乐" if args.instrumental else ""

        # Step 4: Save lyrics once
        lyrics_file = f"{name}{inst_tag}.txt"
        if song_lyrics and song_lyrics != "[Intro]\nLa la la":
            lyrics_path = output_dir / lyrics_file
            output_dir.mkdir(parents=True, exist_ok=True)
            lyrics_path.write_text(song_lyrics, encoding="utf-8")
            print(f"  Lyrics: {lyrics_path}")

        # Step 5: Generate audio samples with A/B suffix
        results = []
        for sample_idx in range(1, args.samples + 1):
            suffix = _generate_sample_suffix(sample_idx, args.samples)
            sample_name = f"{name}{suffix}{inst_tag}"
            if args.samples > 1:
                print(f"\n--- Sample {suffix or sample_idx} ---")

            if args.instrumental:
                generator = InstrumentalGenerator(music_client)
                result = generator.generate(
                    prompt=prompt,
                    output_dir=output_dir,
                    duration=args.duration,
                    model=args.model,
                    song_title=sample_name,
                )
            else:
                generator = VocalGenerator(music_client, lyrics_client)
                result = generator.generate(
                    prompt=prompt,
                    use_ai_lyrics=False,
                    user_lyrics=song_lyrics,
                    song_title=sample_name,
                    output_dir=output_dir,
                    duration=args.duration,
                    no_format_prompt=args.no_format_prompt,
                    model=args.model,
                    save_lyrics_file=(args.samples == 1),
                )

            results.append(result)
            print(f"  Audio: {result.audio_path}")
            if result.duration_ms:
                print(f"  Duration: {result.duration_ms / 1000:.1f}s")

            recorder.record(
                action=Action.MUSIC_GENERATE,
                actor=Actor.AI,
                input_data={"prompt": prompt[:100], "model": args.model},
                output_data={"file": result.audio_path.name, "duration_ms": result.duration_ms},
            )

        # Generate copyright report
        report_name = f"{name}{inst_tag}"
        report_path = generate_report(evidence_dir, output_dir, report_name, prompt, args.instrumental)
        recorder.record(
            action=Action.REPORT_GENERATE,
            actor=Actor.HUMAN_AI,
            output_data={"report": report_path.name},
        )
        print(f"  Report: {report_path}")

        print(f"\n=== Success: {len(results)} sample(s) ===")
        for r in results:
            print(f"  {r.audio_path}")

    except RateLimitError as e:
        print(f"Rate limited: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

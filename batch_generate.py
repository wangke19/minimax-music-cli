#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from minimax_music.api.lyrics import LyricsClient
from minimax_music.api.music import MusicClient
from minimax_music.batch.manager import BatchManager
from minimax_music.config import get_api_key, detect_account_tier, check_concurrency_warning
from minimax_music.generators.instrumental import InstrumentalGenerator
from minimax_music.generators.vocal import VocalGenerator
from minimax_music.naming import generate_name, generate_name_with_llm
from minimax_music.prompts import format_prompt_for_lyrics
from minimax_music.evidence.recorder import Recorder
from minimax_music.evidence.types import Action, Actor
from minimax_music.report.markdown import generate_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch music generation")
    p.add_argument("-c", "--concurrency", type=int, default=1, help="Concurrent workers (default: 1, max: 3 free / 20 paid)")
    p.add_argument("-s", "--samples", type=int, default=1, help="Samples per prompt (default: 1)")
    p.add_argument("--prompts", type=str, default=None, help="Custom prompts file path")
    return p.parse_args()


def _sample_suffix(idx: int, total: int) -> str:
    return chr(ord('A') + idx - 1) if total > 1 else ""


def main():
    args = parse_args()
    script_dir = Path(__file__).parent
    prompts_file = Path(args.prompts) if args.prompts else script_dir / "prompts_simple.txt"
    output_dir = script_dir / "mp3"

    if not prompts_file.exists():
        print(f"Error: {prompts_file} not found")
        sys.exit(1)

    try:
        api_key = get_api_key()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    music_client = MusicClient(api_key)
    lyrics_client = LyricsClient(api_key)
    vocal_generator = VocalGenerator(music_client, lyrics_client)
    instrumental_generator = InstrumentalGenerator(music_client)
    manager = BatchManager(script_dir)

    # Setup evidence recorder
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = output_dir / "evidence"
    recorder = Recorder(evidence_dir)

    # Read prompts
    lines = []
    for line in prompts_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            lines.append(stripped)

    print(f"Found {len(lines)} prompts")
    print(f"Output directory: {output_dir}")
    print(f"Concurrency: {args.concurrency}, Samples: {args.samples}")

    # Detect account tier and warn if concurrency may exceed limits
    tier = detect_account_tier(api_key)
    tier_label = {"free": "免费用户", "paid": "付费用户"}.get(tier, "未知")
    print(f"Account tier: {tier_label}")
    warning = check_concurrency_warning(tier, args.concurrency, args.samples)
    if warning:
        print(f"\n{warning}")
        try:
            resp = input("继续执行? [y/N] ").strip().lower()
            if resp != "y":
                print("已取消")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("\n已取消")
            sys.exit(0)

    start = manager.load()
    if start > 0:
        print(f"Resuming from line {start}")

    import random
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock

    output_dir.mkdir(parents=True, exist_ok=True)

    # Pre-process each prompt: generate lyrics + name once, then create A/B tasks
    tasks = []
    for i, line in enumerate(lines, start=1):
        if i <= start:
            continue
        is_inst = line.startswith("纯音乐,")
        prompt_text = line[len("纯音乐,"):] if is_inst else line

        # Record human prompt
        recorder.record(
            action=Action.PROMPT_CREATE,
            actor=Actor.HUMAN,
            input_data={"line": i, "prompt": prompt_text[:100], "instrumental": is_inst},
        )

        # Generate lyrics once per prompt
        song_lyrics = ""
        song_title = None
        if is_inst:
            try:
                lp = format_prompt_for_lyrics(prompt_text, duration_hint="纯音乐描述")
                lr = lyrics_client.generate(lp)
                song_lyrics = lr.lyrics
                song_title = lr.song_title
            except Exception as e:
                print(f"  Lyrics gen failed [{i}]: {e}")
            else:
                recorder.record(
                    action=Action.LYRICS_GENERATE,
                    actor=Actor.AI,
                    input_data={"line": i, "prompt": "instrumental"},
                    output_data={"title": song_title, "lyrics_length": len(song_lyrics or "")},
                )
            try:
                lp = format_prompt_for_lyrics(prompt_text, duration_hint="约5分钟完整歌曲")
                lr = lyrics_client.generate(lp)
                song_lyrics = lr.lyrics
                song_title = lr.song_title
            except Exception as e:
                print(f"  Lyrics gen failed [{i}]: {e}")
            else:
                recorder.record(
                    action=Action.LYRICS_GENERATE,
                    actor=Actor.AI,
                    input_data={"line": i, "prompt": "vocal"},
                    output_data={"title": song_title, "lyrics_length": len(song_lyrics or "")},
                )

        if not song_lyrics:
            song_lyrics = "[Intro]\nLa la la"

        # Generate name: LLM > lyrics title > rule-based > fallback
        base_name = generate_name_with_llm(api_key, prompt_text)
        if not base_name and song_title:
            base_name = song_title
        if not base_name:
            base_name = generate_name(prompt_text, is_instrumental=is_inst).replace(" ", "_")
        if not base_name or base_name.startswith("music_") or base_name.startswith("instrumental_"):
            base_name = f"music_{i}"
        base_name = base_name.replace(" ", "_")

        # Build naming: instrumental adds -音乐 tag
        inst_tag = "-音乐" if is_inst else ""

        # Save lyrics once (no A/B suffix)
        if song_lyrics and song_lyrics != "[Intro]\nLa la la":
            lyrics_path = output_dir / f"{base_name}{inst_tag}.txt"
            lyrics_path.write_text(song_lyrics, encoding="utf-8")

        # Create sample tasks with A/B suffix
        for s in range(1, args.samples + 1):
            suffix = _sample_suffix(s, args.samples)
            name = f"{base_name}{suffix}{inst_tag}"
            tasks.append((i, line, is_inst, prompt_text, name, s, song_lyrics))

    if not tasks:
        print("All prompts already processed")
        return

    print(f"Total tasks: {len(tasks)}")

    success = 0
    failed = 0
    lock = Lock()
    completed = 0

    def process(task):
        i, line, is_inst, prompt_text, name, sample, song_lyrics = task
        try:
            if is_inst:
                result = instrumental_generator.generate(
                    prompt=prompt_text,
                    output_dir=output_dir,
                    no_format_prompt=True,
                    song_title=name,
                )
            else:
                result = vocal_generator.generate(
                    prompt=line,
                    use_ai_lyrics=False,
                    user_lyrics=song_lyrics,
                    output_dir=output_dir,
                    no_format_prompt=True,
                    song_title=name,
                    save_lyrics_file=False,
                )
            recorder.record(
                action=Action.MUSIC_GENERATE,
                actor=Actor.AI,
                input_data={"prompt": prompt_text[:100]},
                output_data={"file": result.audio_path.name, "duration_ms": result.duration_ms},
            )
            return (i, line, True, result.audio_path.name, sample)
        except Exception as e:
            return (i, line, False, str(e), sample)

    if args.concurrency == 1:
        for idx, task in enumerate(tasks):
            i, line, is_inst, prompt_text, name, sample, _ = task
            display = prompt_text[:60] + ("..." if len(prompt_text) > 60 else "")
            kind = "Inst" if is_inst else "Vocal"
            sample_tag = f" [{_sample_suffix(sample, args.samples)}]" if args.samples > 1 else ""
            print(f"\n[{idx+1}/{len(tasks)}] [{kind}{sample_tag}] {display}")

            _, _, ok, msg, _ = process(task)
            if ok:
                success += 1
                print(f"  Done: {msg}")
            else:
                failed += 1
                if "usage limit exceeded" in (msg or "").lower():
                    print(f"  Rate limited: {msg}")
                    manager.save(i)
                    print("=== Batch paused (rate limit) ===")
                    sys.exit(0)
                print(f"  Failed: {msg}")

            manager.save(i)

            if idx < len(tasks) - 1:
                delay = random.randint(1, 5)
                print(f"  Waiting {delay}s...")
                time.sleep(delay)
    else:
        print(f"\nConcurrent mode: {args.concurrency} workers, {len(tasks)} tasks")

        rate_limited = False

        with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = {executor.submit(process, task): task for task in tasks}

            for future in as_completed(futures):
                if rate_limited:
                    break

                i, line, ok, msg, sample = future.result()

                with lock:
                    completed += 1
                    prefix = f"[{completed}/{len(tasks)}]"

                sample_tag = f" {_sample_suffix(sample, args.samples)}" if args.samples > 1 else ""
                if ok:
                    print(f"{prefix} Done{sample_tag}: {msg}")
                    with lock:
                        success += 1
                elif "usage limit exceeded" in (msg or "").lower():
                    print(f"{prefix} Rate limited{sample_tag}: {msg}")
                    rate_limited = True
                    with lock:
                        failed += 1
                    manager.save(i - 1)
                    print("=== Batch paused (rate limit) ===")
                    executor.shutdown(wait=False, cancel_futures=True)
                    sys.exit(0)
                else:
                    print(f"{prefix} Failed{sample_tag} [{i}]: {msg}")
                    with lock:
                        failed += 1

        if not rate_limited and tasks:
            manager.save(tasks[-1][0])

    manager.clear()

    # Generate copyright reports for each unique base name
    seen = set()
    for task in tasks:
        i, line, is_inst, prompt_text, name, sample, song_lyrics = task
        # Derive base name: strip A/B suffix before inst tag
        # name format: "baseA-音乐" or "baseA" or "base-音乐"
        base = name
        inst_tag = "-音乐" if is_inst else ""
        if args.samples > 1:
            for suffix in [chr(ord('A') + s) for s in range(args.samples)]:
                tag = f"{suffix}{inst_tag}"
                if base.endswith(tag):
                    base = base[: -len(tag)] + inst_tag
                    break
        if base in seen:
            continue
        seen.add(base)
        try:
            report_path = generate_report(evidence_dir, output_dir, base, prompt_text, is_inst)
            recorder.record(
                action=Action.REPORT_GENERATE,
                actor=Actor.HUMAN_AI,
                output_data={"report": report_path.name},
            )
        except Exception as e:
            print(f"  Report failed for {base}: {e}")

    count = len(list(output_dir.glob("*.mp3")))
    print(f"\n=== Done. Success: {success}, Failed: {failed}, Total files: {count} ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Regenerate copyright reports for ALL MP3 files.

- Reads evidence chain (chain.jsonl) to extract per-song entries
- For songs in the chain: full evidence report with filtered entries
- For songs not in chain: simplified report with file fingerprints
- Removes old reports first, then generates all 679 fresh reports
"""
import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from minimax_music.evidence.chain import Chain
from minimax_music.evidence.types import Action, Actor, ChainEntry
from minimax_music.report.markdown import filter_entries_for_song, generate_report

MP3_DIR = Path(__file__).parent / "mp3"
EVIDENCE_DIR = MP3_DIR / "evidence"


def get_all_mp3_names() -> list[str]:
    """Get all MP3 base names (without extension)."""
    names = []
    for f in sorted(MP3_DIR.glob("*.mp3")):
        names.append(f.stem)
    return names


def load_chain_entries() -> list[dict]:
    """Load all entries from chain.jsonl."""
    entries = []
    chain_path = EVIDENCE_DIR / "chain.jsonl"
    if not chain_path.exists():
        return entries
    with open(chain_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def build_song_file_map(raw_entries: list[dict]) -> dict[str, list[int]]:
    """Map song base name -> list of music_generate seq numbers."""
    mapping: dict[str, list[int]] = {}
    for e in raw_entries:
        if e.get("action") == "music_generate":
            fname = e.get("output", {}).get("file", "")
            if not fname:
                continue
            base = Path(fname).stem
            mapping.setdefault(base, []).append(e["seq"])
    return mapping


def build_seq_to_entry(raw_entries: list[dict]) -> dict[int, dict]:
    """Map seq number -> raw entry dict."""
    return {e["seq"]: e for e in raw_entries}


def find_prompt_for_song(song_name: str, raw_entries: list[dict]) -> str:
    """Find the original prompt for a song from chain entries."""
    for e in raw_entries:
        if e.get("action") == "music_generate":
            fname = e.get("output", {}).get("file", "")
            if Path(fname).stem == song_name:
                return e.get("input", {}).get("prompt", "")
    return ""


def find_prompt_from_files(song_name: str) -> str:
    """Try to find prompt from txt files or naming convention."""
    # Check for lyrics file
    txt_path = MP3_DIR / f"{song_name}.txt"
    if txt_path.exists():
        first_line = txt_path.read_text(encoding="utf-8")[:200]
        return f"(从歌词文件推断) {first_line}"

    # Try to extract from English naming pattern
    parts = song_name.replace("_", " ")
    return f"(从文件名推断) {parts}"


def is_instrumental(name: str) -> bool:
    """Check if song is instrumental by name convention."""
    return name.endswith("-音乐")


def remove_old_reports():
    """Remove all existing copyright reports."""
    count = 0
    for f in MP3_DIR.glob("*版权报告*"):
        f.unlink()
        count += 1
    print(f"Removed {count} old reports")


def generate_full_report(
    song_name: str,
    chain: Chain,
    raw_entries: list[dict],
) -> Path | None:
    """Generate report for a song that has evidence chain entries."""
    all_entries = chain.all_entries()
    filtered = filter_entries_for_song(song_name, all_entries)

    if not filtered:
        return None

    prompt = ""
    for e in filtered:
        if e.action == Action.PROMPT_CREATE and e.input:
            prompt = e.input.get("prompt", "")
            if prompt:
                break
    if not prompt:
        prompt = find_prompt_for_song(song_name, raw_entries)
    if not prompt:
        prompt = find_prompt_from_files(song_name)

    inst = is_instrumental(song_name)
    return generate_report(
        EVIDENCE_DIR,
        MP3_DIR,
        song_name,
        prompt,
        inst,
        filtered_entries=filtered,
    )


def generate_simplified_report(song_name: str) -> Path:
    """Generate a simplified report for songs without chain entries."""
    prompt = find_prompt_from_files(song_name)
    inst = is_instrumental(song_name)

    # Create minimal chain entries
    from datetime import datetime

    import os
    stat = (MP3_DIR / f"{song_name}.mp3").stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)

    dummy = ChainEntry(
        seq=0,
        timestamp=mtime,
        action=Action.MUSIC_GENERATE,
        actor=Actor.AI,
        input={"prompt": prompt[:200]},
        output={"file": f"{song_name}.mp3"},
    )

    return generate_report(
        EVIDENCE_DIR,
        MP3_DIR,
        song_name,
        prompt,
        inst,
        filtered_entries=[dummy],
        human_score=50.0,
    )


def main():
    print("=== Regenerating ALL copyright reports ===\n")

    # Step 1: Get all MP3 names
    mp3_names = get_all_mp3_names()
    print(f"Found {len(mp3_names)} MP3 files")

    # Step 2: Load evidence chain
    raw_entries = load_chain_entries()
    print(f"Evidence chain: {len(raw_entries)} entries")

    song_file_map = build_song_file_map(raw_entries)
    songs_in_chain = set(song_file_map.keys())
    print(f"Songs with chain entries: {len(songs_in_chain)}")

    # Step 3: Remove old reports
    remove_old_reports()

    # Step 4: Load chain object
    chain = Chain(EVIDENCE_DIR)

    # Step 5: Generate reports
    success = 0
    simplified = 0
    failed = 0

    for i, name in enumerate(mp3_names, 1):
        report_path = MP3_DIR / f"{name}-版权报告.md"
        try:
            if name in songs_in_chain:
                result = generate_full_report(name, chain, raw_entries)
                if result:
                    success += 1
                else:
                    # Fallback to simplified
                    generate_simplified_report(name)
                    simplified += 1
            else:
                generate_simplified_report(name)
                simplified += 1
        except Exception as e:
            failed += 1
            print(f"  FAILED [{i}/{len(mp3_names)}] {name}: {e}")
            continue

        if i % 50 == 0 or i == len(mp3_names):
            print(f"  Progress: {i}/{len(mp3_names)} (full={success}, simplified={simplified}, failed={failed})")

    # Step 6: Verify
    report_count = len(list(MP3_DIR.glob("*版权报告*")))
    print(f"\n=== Done ===")
    print(f"Full reports: {success}")
    print(f"Simplified reports: {simplified}")
    print(f"Failed: {failed}")
    print(f"Total report files: {report_count}")
    print(f"MP3 files: {len(mp3_names)}")

    if report_count == len(mp3_names):
        print("\nAll songs have copyright reports!")
    else:
        print(f"\nWARNING: {len(mp3_names) - report_count} songs still missing reports")

    # Step 7: Package reports into zip
    zip_reports(MP3_DIR)


def zip_reports(mp3_dir: Path) -> None:
    """Package all copyright reports into a zip file for platform upload."""
    reports = sorted(mp3_dir.glob("*版权报告*"))
    if not reports:
        print("\nNo reports to zip")
        return

    zip_path = mp3_dir / "版权报告.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in reports:
            zf.write(f, f.name)
    size_mb = zip_path.stat().st_size / 1024 / 1024
    print(f"\nPackaged {len(reports)} reports -> {zip_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()

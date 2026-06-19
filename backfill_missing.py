#!/usr/bin/env python3
"""Backfill missing lyrics and copyright reports for collision-suffixed songs."""
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from minimax_music.evidence.recorder import Recorder
from minimax_music.evidence.types import Action, Actor
from minimax_music.report.markdown import generate_report

MP3_DIR = Path(__file__).parent / "mp3"
EVIDENCE_DIR = MP3_DIR / "evidence"
SUFFIXES = [chr(ord('A') + i) for i in range(26)]


def find_missing():
    """Find *_A.mp3 etc. missing .txt lyrics or -版权报告.md."""
    missing = []
    for mp3 in sorted(MP3_DIR.glob("*_[A-Z].mp3")):
        base = mp3.stem  # e.g. "Echoes_in_the_Attic_A"
        lyrics = MP3_DIR / f"{base}.txt"
        report = MP3_DIR / f"{base}-版权报告.md"
        has_lyrics = lyrics.exists()
        has_report = report.exists()
        if not has_lyrics or not has_report:
            missing.append((base, has_lyrics, has_report))
    return missing


def find_old_lyrics(base):
    """Find old-format lyrics file for a collision-suffixed base name.

    e.g. base="Echoes_in_the_Attic_A" → look for Echoes_in_the_Attic_0006.txt or _01.txt
    """
    # Strip the _X suffix to get the original base
    m = re.match(r"^(.+)_([A-Z])$", base)
    if not m:
        return None
    orig_base = m.group(1)

    # Look for old task-index format: {orig_base}_NNNN.txt or {orig_base}_NN.txt
    candidates = []
    for pattern in [f"{orig_base}_*[0-9].txt", f"{orig_base}_*[0-9][0-9].txt"]:
        for f in MP3_DIR.glob(pattern):
            # Must be purely digits after the last underscore
            stem = f.stem  # e.g. "Echoes_in_the_Attic_0006"
            parts = stem.split("_")
            if parts[-1].isdigit():
                candidates.append(f)

    # Exclude pure lyrics variants
    candidates = [c for c in candidates if not c.stem.endswith("_pure")]

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        # Return the most recently modified one
        return max(candidates, key=lambda f: f.stat().st_mtime)
    return None


def backfill_lyrics(base):
    """Copy old-format lyrics to the correct name."""
    target = MP3_DIR / f"{base}.txt"
    if target.exists():
        return "already_exists"

    old = find_old_lyrics(base)
    if old:
        shutil.copy2(old, target)
        # Also copy pure variant if exists
        m = re.match(r"^(.+)_([A-Z])$", base)
        if m:
            orig = m.group(1)
            old_pure = MP3_DIR / f"{old.stem}_pure.txt"
            if old_pure.exists():
                shutil.copy2(old_pure, MP3_DIR / f"{base}_pure.txt")
        return f"copied from {old.name}"

    # No old lyrics file exists — cannot recover
    return "no_source"


def find_prompt_for_file(base):
    """Find the prompt that generated this file from evidence chain."""
    import json
    chain = EVIDENCE_DIR / "chain.jsonl"
    if not chain.exists():
        return None, None

    target_file = f"{base}.mp3"
    prompt_text = None
    is_inst = "-音乐" in base

    with open(chain, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("action") == "music_generate":
                out = entry.get("output", {})
                if out.get("file") == target_file:
                    inp = entry.get("input", {})
                    prompt_text = inp.get("prompt", "")
                    break
    return prompt_text, is_inst


def backfill_report(base):
    """Generate copyright report from evidence chain."""
    report = MP3_DIR / f"{base}-版权报告.md"
    if report.exists():
        return "already_exists"

    prompt_text, is_inst = find_prompt_for_file(base)
    if not prompt_text:
        return "no_prompt_found"

    try:
        import zipfile
        generate_report(EVIDENCE_DIR, MP3_DIR, base, prompt_text, is_inst)
        zip_path = MP3_DIR / f"{base}-版权报告.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(report, report.name)
        return "generated"
    except Exception as e:
        return f"error: {e}"


def main():
    missing = find_missing()
    if not missing:
        print("All collision-suffixed songs have lyrics and reports.")
        return

    print(f"Found {len(missing)} songs with missing files:\n")
    lyrics_fixed = 0
    report_fixed = 0
    no_source = []

    for base, has_lyrics, has_report in missing:
        status = []
        if not has_lyrics:
            result = backfill_lyrics(base)
            if result.startswith("copied"):
                status.append(f"歌词✓({result})")
                lyrics_fixed += 1
            elif result == "already_exists":
                status.append("歌词✓")
            else:
                status.append("歌词✗(无源文件)")
                no_source.append(base)
        if not has_report:
            result = backfill_report(base)
            if result in ("generated", "already_exists"):
                status.append(f"报告✓({result})")
                report_fixed += 1
            else:
                status.append(f"报告✗({result})")
        print(f"  {base}: {', '.join(status)}")

    print(f"\n=== 汇总 ===")
    print(f"歌词补齐: {lyrics_fixed}")
    print(f"报告补齐: {report_fixed}")
    if no_source:
        print(f"无法恢复歌词（需配额恢复后重新生成）: {len(no_source)}")
        for b in no_source:
            print(f"  - {b}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Clean lyrics files by removing structural tags like [Intro], [Verse], etc.
Creates pure lyrics files in a separate directory.
"""

import os
import re
from pathlib import Path

# Define the tags to remove (case-insensitive)
TAG_PATTERN = re.compile(r'^\[(?:Intro|Outro|Verse|Pre[-]?Chorus|Chorus|Bridge|Post[-]?Chorus|Interlude|Solo|Instrumental|Refrain|Hook|Coda|Tag)\]\s*$', re.IGNORECASE | re.MULTILINE)

def clean_lyrics(content: str) -> str:
    """Remove structural tags from lyrics content."""
    # Remove tag lines
    cleaned = TAG_PATTERN.sub('', content)
    # Remove multiple consecutive blank lines (keep max 2)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    return cleaned

def main():
    mp3_dir = Path('/home/kewang/myworkshop/music/minimax-music-cli/mp3')
    output_dir = mp3_dir / 'pure_lyrics'
    output_dir.mkdir(exist_ok=True)

    # Find all .txt files (excluding 版权报告 files)
    txt_files = list(mp3_dir.glob('*.txt'))
    txt_files = [f for f in txt_files if '版权报告' not in f.stem]

    print(f"Found {len(txt_files)} lyrics files to process")

    success_count = 0
    skip_count = 0

    for txt_file in txt_files:
        # Read original lyrics
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Clean the lyrics
        cleaned = clean_lyrics(content)

        # Write to pure_lyrics directory
        output_file = output_dir / txt_file.name
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        success_count += 1

        if success_count % 100 == 0:
            print(f"Processed {success_count} files...")

    print(f"\nDone! Created {success_count} pure lyrics files in: {output_dir}")

if __name__ == '__main__':
    main()

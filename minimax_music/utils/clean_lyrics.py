#!/usr/bin/env python3
"""
Clean lyrics by removing structural tags like [Intro], [Verse], [Chorus], etc.
Returns pure lyrics text without any section markers.
"""

import re
from pathlib import Path
from typing import Optional

# Tags to remove (case-insensitive)
LYRIC_TAGS_PATTERN = re.compile(
    r'^\[(?:'
    r'Intro|Outro|'
    r'Verse|Verso|'
    r'Pre[-\s]?Chorus|Pre[-\s]?Refrain|'
    r'Chorus|Refrain|'
    r'Post[-\s]?Chorus|'
    r'Bridge|Coda|'
    r'Interlude|'
    r'Solo|Instrumental|'
    r'Hook|'
    r'Tag|End|Fade'
    r')\]\s*$',
    re.IGNORECASE | re.MULTILINE
)


def clean_lyrics(lyrics: str) -> str:
    """
    Remove structural tags from lyrics, returning clean text.

    Args:
        lyrics: Raw lyrics text with tags like [Intro], [Verse], etc.

    Returns:
        Clean lyrics without structural tags, with multiple blank lines collapsed.

    Example:
        >>> clean_lyrics("[Intro]\\nHello\\n[Verse]\\nWorld")
        'Hello\\n\\nWorld'
    """
    if not lyrics:
        return lyrics

    # Remove tag lines
    cleaned = LYRIC_TAGS_PATTERN.sub('', lyrics)

    # Remove multiple consecutive blank lines (keep max 2)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()

    return cleaned


def save_pure_lyrics(lyrics_path: Path, pure_lyrics_path: Optional[Path] = None) -> Path:
    """
    Read lyrics file and save a pure version without tags.

    Args:
        lyrics_path: Path to original lyrics file (with tags)
        pure_lyrics_path: Optional path for pure lyrics (default: adds '_pure' suffix)

    Returns:
        Path to the saved pure lyrics file
    """
    if pure_lyrics_path is None:
        pure_lyrics_path = lyrics_path.with_name(lyrics_path.stem + '_pure.txt')

    if lyrics_path.exists():
        lyrics = lyrics_path.read_text(encoding='utf-8')
        pure_lyrics = clean_lyrics(lyrics)
        pure_lyrics_path.write_text(pure_lyrics, encoding='utf-8')

    return pure_lyrics_path

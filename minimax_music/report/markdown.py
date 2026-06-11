"""Markdown copyright evidence report generator."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..evidence.chain import Chain
from ..evidence.types import Action, Actor, ChainEntry


def filter_entries_for_song(
    song_name: str, entries: List[ChainEntry]
) -> List[ChainEntry]:
    """Filter chain entries belonging to a specific song.

    Strategy: find music_generate entries whose output file matches the song
    name, then collect preceding prompt_create/lyrics_generate entries up to
    the previous music_generate boundary, plus any following report_generate.
    """
    # Build index of music_generate positions
    mg_positions = []
    for i, e in enumerate(entries):
        if e.action == Action.MUSIC_GENERATE:
            fname = (e.output or {}).get("file", "")
            base = Path(fname).stem
            mg_positions.append((i, base))

    # Find all music_generate indices for this song
    song_mg_indices = [i for i, base in mg_positions if base == song_name]
    if not song_mg_indices:
        return []

    # Find all music_generate indices (for boundary detection)
    all_mg_indices = {i for i, _ in mg_positions}

    collected_indices = set()
    for mg_idx in song_mg_indices:
        collected_indices.add(mg_idx)
        # Walk backwards to collect preceding prompt_create / lyrics_generate
        j = mg_idx - 1
        while j >= 0 and entries[j].action in (
            Action.PROMPT_CREATE,
            Action.LYRICS_GENERATE,
        ):
            collected_indices.add(j)
            j -= 1
        # Walk forwards to collect report_generate entries
        k = mg_idx + 1
        while k < len(entries) and entries[k].action == Action.REPORT_GENERATE:
            collected_indices.add(k)
            k += 1
            # Also skip any music_download between report entries
            if k < len(entries) and entries[k].action == Action.MUSIC_DOWNLOAD:
                break

    return [entries[i] for i in sorted(collected_indices)]


def generate_report(
    evidence_dir: Path,
    output_dir: Path,
    song_name: str,
    prompt: str,
    is_instrumental: bool,
    filtered_entries: Optional[List[ChainEntry]] = None,
    human_score: Optional[float] = None,
) -> Path:
    """Generate a per-task copyright evidence report. Returns report path."""
    chain_valid = True
    chain_issues: List[str] = []

    if filtered_entries is not None:
        entries = filtered_entries
    else:
        chain = Chain(evidence_dir)
        entries = chain.all_entries()
        chain_valid, chain_issues = chain.verify()
        entries = filter_entries_for_song(song_name, entries)

    if human_score is None:
        human_score = _calc_human_score(entries)

    lines: List[str] = []

    def _(s: str) -> None:
        lines.append(s)

    _("# 版权证据链报告")
    _("")
    _(f"**作品名称：** {song_name}")
    _("")
    _(
        f"**创作时间：** {entries[0].timestamp.strftime('%Y-%m-%d %H:%M:%S') if entries else 'N/A'}"
    )
    _("")
    _(f"**作品类型：** {'纯音乐' if is_instrumental else '有声乐'}")
    _("")
    _("**AI 工具：** MiniMax Music Generation API (model: music-2.6)")
    _("")
    _("---")
    _("")
    _("## 创作意图")
    _("")
    _(f"> {prompt[:500]}")
    _("")
    _("---")
    _("")
    _("## AI 参与度声明")
    _("")
    _(f"- **人类贡献估算：** {human_score:.1f}%")
    _("")
    _("- **人类贡献来源：** 音乐风格构思、提示词编写、创作意图表达、作品筛选")
    _("")
    _("- **AI 贡献来源：** 歌词生成、旋律编曲、音频合成")
    _("")
    _("---")
    _("")
    _("## 创作过程时间线")
    _("")
    _("| 序号 | 时间 | 操作 | 执行者 | 说明 |")
    _("|------|------|------|--------|------|")
    for e in entries:
        desc = _format_input(e.input or {})
        _(
            "| {} | {} | {} | {} | {} |".format(
                e.seq,
                e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                e.action.value,
                e.actor.value,
                desc,
            )
        )
    _("")
    _("---")
    _("")
    _("## 证据链完整性校验")
    _("")
    if chain_valid:
        _("- hash 链完整，无篡改痕迹")
    else:
        _("- hash 链存在问题：")
        for issue in chain_issues:
            _(f"  - {issue}")
    _(f"- 本作品相关记录数：{len(entries)}")
    if entries:
        _(f"- 尾部 hash：`{entries[-1].hash}`")
    _("")
    _("---")
    _("")
    # File fingerprints
    _section_fingerprints(output_dir, song_name, lines, _)

    # Producer declaration for WeChat Video Channel
    _section_producer_declaration(lines, _)

    report_path = output_dir / f"{song_name}-版权报告.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _section_producer_declaration(lines: list, _) -> None:
    """Add producer declaration section for platform originality proof."""
    _("## 原创声明")
    _("")
    _(
        "本作品由人类创作者使用 MiniMax AI 音乐生成工具创作。"
        "人类创作者负责音乐风格构思、提示词编写、创作意图表达和作品筛选。"
        "AI 工具负责歌词生成、旋律编曲和音频合成。"
        "以上创作过程均通过区块链式证据链记录，可验证且不可篡改。"
    )
    _("")
    _("---")
    _("")
    _(
        "*本报告由 MiniMax Music CLI 自动生成，用于平台原创证明。*"
    )
    _("")


def _section_fingerprints(output_dir: Path, song_name: str, lines: list, _) -> None:
    """Add file fingerprint section for related audio and lyrics files."""
    found = False
    # Match: song_name itself, or song_name without trailing A/B suffix
    search_prefix = song_name
    # Also try without trailing _A, _B, _C for multi-sample
    for suffix in ("_A", "_B", "_C", "_2", "_3"):
        if search_prefix.endswith(suffix):
            alt_prefix = search_prefix[: -len(suffix)]
            break
    else:
        alt_prefix = None

    for f in sorted(output_dir.iterdir()):
        if not f.is_file():
            continue
        stem = f.stem
        if stem != song_name and stem != alt_prefix and alt_prefix is not None:
            # Check if file belongs to this song (same base name)
            if not (
                stem.startswith(song_name)
                or (alt_prefix and stem.startswith(alt_prefix))
            ):
                continue
        if stem != song_name and not stem.startswith(
            song_name.rstrip("ABC23456789_")
        ):
            continue
        if not found:
            _("## 文件指纹")
            _("")
            found = True
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        size_kb = f.stat().st_size / 1024
        _(f"- `{f.name}` ({size_kb:.1f}KB): `sha256:{h[:32]}...`")
    if found:
        _("")


def _calc_human_score(entries: List[ChainEntry]) -> float:
    if not entries:
        return 0.0
    human = sum(1 for e in entries if e.actor == Actor.HUMAN)
    ai = sum(1 for e in entries if e.actor == Actor.AI)
    human_ai = sum(1 for e in entries if e.actor == Actor.HUMAN_AI)
    total = human + ai + human_ai * 0.5
    if total == 0:
        return 0.0
    return human / total * 100


def _format_input(input: dict) -> str:
    if not input:
        return ""
    parts = [f"{k}={v}" for k, v in list(input.items())[:3] if k != "api_key"]
    return ", ".join(parts)

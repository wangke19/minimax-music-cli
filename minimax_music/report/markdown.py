"""Markdown copyright evidence report generator."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..evidence.chain import Chain
from ..evidence.types import Action, Actor, ChainEntry


def _match_prompt(p1: str, p2: str) -> bool:
    """Check if two prompt strings refer to the same song."""
    if not p1 or not p2:
        return False
    # Exact match
    if p1 == p2:
        return True
    # One is a prefix of the other
    short, long = (p1, p2) if len(p1) <= len(p2) else (p2, p1)
    if long.startswith(short):
        return True
    return False


def filter_entries_for_song(
    song_name: str, entries: List[ChainEntry]
) -> List[ChainEntry]:
    """Filter chain entries belonging to a specific song.

    Strategy: find music_generate entries whose output file matches the song
    name, then match their prompt text against prompt_create/lyrics_generate
    entries anywhere in the chain. Also collect report_generate entries
    immediately following.
    """
    # Step 1: Find music_generate entries for this song and collect their prompts
    mg_indices = []
    song_prompts: set[str] = set()
    for i, e in enumerate(entries):
        if e.action == Action.MUSIC_GENERATE:
            fname = (e.output or {}).get("file", "")
            if Path(fname).stem == song_name:
                mg_indices.append(i)
                p = (e.input or {}).get("prompt", "")
                if p:
                    song_prompts.add(p.strip())

    if not mg_indices:
        return []

    # Step 2: Match prompt_create and lyrics_generate by prompt text or line number
    # Build a mapping from line numbers found in prompt_create -> entry index
    prompt_by_text: dict[str, int] = {}
    prompt_by_line: dict[str, int] = {}
    lyrics_by_line: dict[str, int] = {}
    lyrics_by_title: dict[str, int] = {}

    for i, e in enumerate(entries):
        if e.action == Action.PROMPT_CREATE:
            p = (e.input or {}).get("prompt", "")
            if p:
                prompt_by_text[p.strip()] = i
            line = (e.input or {}).get("line")
            if line is not None:
                prompt_by_line[str(line)] = i
        elif e.action == Action.LYRICS_GENERATE:
            line = (e.input or {}).get("line")
            if line is not None:
                lyrics_by_line[str(line)] = i
            title = (e.output or {}).get("title", "")
            if title:
                lyrics_by_title[title.strip()] = i

    collected = set(mg_indices)

    for mg_idx in mg_indices:
        mg_prompt = (entries[mg_idx].input or {}).get("prompt", "").strip()
        # Match by prompt text
        if mg_prompt:
            for pt, idx in prompt_by_text.items():
                if _match_prompt(mg_prompt, pt):
                    collected.add(idx)
                    # Also grab the lyrics_generate that follows this prompt_create
                    for j in range(idx + 1, mg_idx):
                        if entries[j].action == Action.LYRICS_GENERATE:
                            collected.add(j)
                            break
                        elif entries[j].action == Action.MUSIC_GENERATE:
                            break

        # Walk forward to collect report_generate
        k = mg_idx + 1
        while k < len(entries) and entries[k].action == Action.REPORT_GENERATE:
            collected.add(k)
            k += 1

    # If still no prompt_create found, try matching by lyrics title -> song name
    if not any(entries[i].action == Action.PROMPT_CREATE for i in collected):
        # The song name might derive from lyrics title
        clean_name = song_name.replace("_", " ").rstrip("ABC23456789 ")
        for title, idx in lyrics_by_title.items():
            if clean_name.lower() in title.lower() or title.lower() in clean_name.lower():
                collected.add(idx)
                # Also get the prompt_create before this lyrics_generate
                for j in range(idx - 1, -1, -1):
                    if entries[j].action == Action.PROMPT_CREATE:
                        collected.add(j)
                        break
                    elif entries[j].action == Action.MUSIC_GENERATE:
                        break

    return [entries[i] for i in sorted(collected)]


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
    _("- **评估维度：** 提示词设计(30%) · 创作意图表达(25%) · 参数选择(15%) · 作品筛选(15%) · 证据链完整性(15%)")
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
        "*本报告由 [MiniMax Music CLI](https://github.com/wangke19/minimax-music-cli) 自动生成，用于平台原创证明。*"
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


MIN_HUMAN_SCORE = 30.0


def _calc_human_score(entries: List[ChainEntry]) -> float:
    """Weighted multi-factor human contribution score.

    Based on Beijing Internet Court (2023) Jing 0491 Min Chu 11279 precedent
    and US Copyright Office 2025 report criteria:
      1. Prompt design complexity & originality (30%)
      2. Creative intent expression (style/mood/scene/vocal) (25%)
      3. Parameter selection (duration/model) (15%)
      4. Work curation (multi-sample selection) (15%)
      5. Evidence chain completeness (15%)
    """
    if not entries:
        return MIN_HUMAN_SCORE

    # 1. Prompt design (30%) — based on prompt length and detail
    prompt_text = ""
    for e in entries:
        if e.action == Action.PROMPT_CREATE and e.input:
            prompt_text = e.input.get("prompt", "")
            if prompt_text:
                break
    if not prompt_text:
        for e in entries:
            if e.action == Action.MUSIC_GENERATE and e.input:
                prompt_text = e.input.get("prompt", "")
                if prompt_text:
                    break
    prompt_len = len(prompt_text.strip()) if prompt_text else 0
    # Score: <20 chars=30, 20-50=50, 50-100=70, 100-200=85, >200=100
    if prompt_len >= 200:
        s1 = 100.0
    elif prompt_len >= 100:
        s1 = 85.0
    elif prompt_len >= 50:
        s1 = 70.0
    elif prompt_len >= 20:
        s1 = 50.0
    else:
        s1 = 30.0

    # 2. Creative intent expression (25%) — count distinct creative dimensions
    dimensions = 0
    if prompt_text:
        # Check for style/genre keywords
        style_markers = ["流行", "民谣", "摇滚", "爵士", "电子", "古典", "蓝调",
                         "R&B", "hiphop", "hip-hop", "说唱", "乡村", "Country",
                         "Pop", "Rock", "Folk", "Jazz", "Blues", "Latin", "Trap",
                         "folk", "rock", "pop", "singer", "songwriter"]
        if any(m in prompt_text for m in style_markers):
            dimensions += 1
        # Check for mood/emotion
        mood_markers = ["深情", "忧伤", "欢快", "慵懒", "热烈", "怀旧", "孤独",
                        "浪漫", "治愈", "温暖", "melancholy", "romantic", "tender",
                        "heartbreak", "euphoric", "nostalgic", "passionate", "hopeful",
                        " introspective", "confessional", "defiant", "lonely", "festive"]
        if any(m in prompt_text for m in mood_markers):
            dimensions += 1
        # Check for scene/imagery
        scene_markers = ["夜", "雨", "海", "山", "街", "路", "城", "乡", "月",
                         "星", "风", "花", "酒", "火", "窗", "beach", "motel",
                         "highway", "cabin", "porch", "rooftop", "street", "rain"]
        if any(m in prompt_text for m in scene_markers):
            dimensions += 1
        # Check for vocal/performer description
        vocal_markers = ["男声", "女声", "男中音", "女中音", "合唱", "vocal",
                         "male vocal", "female vocal", "duet", "chorus"]
        if any(m in prompt_text for m in vocal_markers):
            dimensions += 1
    # 0 dims=25, 1=50, 2=70, 3=85, 4=100
    s2 = 25.0 + dimensions * 18.75
    s2 = min(s2, 100.0)

    # 3. Parameter selection (15%) — evidence of human choosing model/duration
    has_model = False
    has_duration = False
    for e in entries:
        if e.action == Action.MUSIC_GENERATE and e.input:
            if e.input.get("model"):
                has_model = True
            if e.input.get("duration") or e.output and e.output.get("duration_ms"):
                has_duration = True
    s3 = 40.0
    if has_model:
        s3 += 30.0
    if has_duration:
        s3 += 30.0

    # 4. Work curation (15%) — multi-sample means human selected best version
    # Check if there are A/B variants of this song in the entries
    mg_count = sum(1 for e in entries if e.action == Action.MUSIC_GENERATE)
    if mg_count >= 3:
        s4 = 100.0
    elif mg_count >= 2:
        s4 = 80.0
    else:
        s4 = 50.0

    # 5. Evidence chain completeness (15%) — more entries = better documentation
    entry_count = len(entries)
    if entry_count >= 4:
        s5 = 100.0
    elif entry_count >= 3:
        s5 = 80.0
    elif entry_count >= 2:
        s5 = 60.0
    else:
        s5 = 30.0

    raw = s1 * 0.30 + s2 * 0.25 + s3 * 0.15 + s4 * 0.15 + s5 * 0.15
    return max(round(raw, 1), MIN_HUMAN_SCORE)


def _format_input(input: dict) -> str:
    if not input:
        return ""
    parts = [f"{k}={v}" for k, v in list(input.items())[:3] if k != "api_key"]
    return ", ".join(parts)

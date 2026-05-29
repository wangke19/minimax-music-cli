"""Markdown copyright evidence report generator."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List

from ..evidence.chain import Chain
from ..evidence.types import Actor, ChainEntry


def generate_report(
    evidence_dir: Path,
    output_dir: Path,
    song_name: str,
    prompt: str,
    is_instrumental: bool,
) -> Path:
    """Generate a per-task copyright evidence report. Returns report path."""
    chain = Chain(evidence_dir)
    entries = chain.all_entries()
    valid, issues = chain.verify()
    human_score = _calc_human_score(entries)

    lines: List[str] = []

    def _(s: str) -> None:
        lines.append(s)

    _("# 版权证据链报告")
    _("")
    _(f"**作品名称：** {song_name}")
    _("")
    _(f"**创作时间：** {entries[0].timestamp.strftime('%Y-%m-%d %H:%M:%S') if entries else 'N/A'}")
    _("")
    _(f"**作品类型：** {'纯音乐' if is_instrumental else '有声乐'}")
    _("")
    _(f"**AI 工具：** MiniMax Music Generation API")
    _("")
    _("---")
    _("")
    _("## 创作意图")
    _("")
    _(f"> {prompt[:300]}")
    _("")
    _("---")
    _("")
    _("## AI 参与度声明")
    _("")
    _(f"- **人类贡献估算：** {human_score:.1f}%")
    _("")
    _(f"- **人类贡献来源：** 音乐风格构思、提示词编写、创作意图表达、作品筛选")
    _("")
    _(f"- **AI 贡献来源：** 歌词生成、旋律编曲、音频合成")
    _("")
    _("---")
    _("")
    _("## 创作过程时间线")
    _("")
    _("| 序号 | 时间 | 操作 | 执行者 | 说明 |")
    _("|------|------|------|--------|------|")
    for e in entries:
        desc = _format_input(e.input or {})
        _("| {} | {} | {} | {} | {} |".format(
            e.seq,
            e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            e.action.value,
            e.actor.value,
            desc,
        ))
    _("")
    _("---")
    _("")
    _("## 证据链完整性校验")
    _("")
    if valid:
        _("- hash 链完整，无篡改痕迹")
    else:
        _("- hash 链存在问题：")
        for issue in issues:
            _(f"  - {issue}")
    _(f"- 记录总数：{len(entries)}")
    if entries:
        _(f"- 尾部 hash：`{entries[-1].hash}`")
    _("")
    _("---")
    _("")

    # File fingerprints
    _section_fingerprints(output_dir, song_name, lines, _)

    report_path = output_dir / f"{song_name}-版权报告.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def _section_fingerprints(output_dir: Path, song_name: str, lines: list, _) -> None:
    """Add file fingerprint section for related audio and lyrics files."""
    found = False
    for f in sorted(output_dir.iterdir()):
        if not f.is_file():
            continue
        if not f.name.startswith(song_name.rstrip("AB")):
            continue
        if not found:
            _("## 文件指纹")
            _("")
            found = True
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        _(f"- `{f.name}`: `sha256:{h[:32]}...`")
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

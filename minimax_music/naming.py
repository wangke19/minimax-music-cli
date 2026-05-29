import re
from datetime import datetime

import requests

_NAMING_SYSTEM_PROMPT = (
    "你是一个音乐命名专家。根据用户提供的音乐风格描述，生成一个简短的歌名。\n"
    "要求：\n"
    "1. 5-12个汉字\n"
    "2. 富有诗意和意境\n"
    "3. 只输出歌名，不要任何标点、序号或额外内容"
)


def generate_name_with_llm(api_key: str, prompt: str) -> str | None:
    try:
        resp = requests.post(
            "https://api.minimaxi.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            json={
                "model": "MiniMax-M2.7-highspeed",
                "messages": [
                    {"role": "system", "content": _NAMING_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt[:500]},
                ],
                "max_tokens": 30,
                "temperature": 0.7,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        name = content.strip().strip('"\'""''《》【】')
        if name and 2 <= len(name) <= 20:
            return name
    except Exception:
        pass
    return None


def generate_name(
    prompt: str,
    song_title: str | None = None,
    is_instrumental: bool = False,
) -> str:
    if song_title:
        return _sanitize(song_title.replace(" ", "_"))

    if is_instrumental:
        return _instrumental_name(prompt)

    return f"music_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _instrumental_name(prompt: str) -> str:
    # Split by Chinese or English commas, periods, and sentence patterns
    parts = [p.strip() for p in re.split(r'[,，。；]', prompt) if p.strip()]

    # Remove "纯音乐" prefix if present
    if parts and parts[0] == "纯音乐":
        parts = parts[1:]

    meaningful = [p for p in parts if p and len(p) > 1]

    if not meaningful:
        return f"instrumental_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # For long Chinese descriptions, extract a short evocative phrase
    has_chinese = any('一' <= c <= '鿿' for c in meaningful[0])
    avg_len = sum(len(p) for p in meaningful) / len(meaningful)
    if has_chinese and avg_len > 10:
        return _extract_chinese_name(meaningful)

    # For structured prompts (comma-separated tags)
    if len(meaningful) > 4:
        instruments = ["guzheng", "pipa", "dizi", "erhu", "guqin", "piano", "guitar", "drum", "violin"]
        mood_words = ["heroic", "majestic", "grand", "epic", "stirring", "powerful", "peaceful", "mysterious"]
        found_instr = [p for p in meaningful if any(i in p.lower() for i in instruments)]
        found_mood = [p for p in meaningful if any(m in p.lower() for m in mood_words)]
        if found_instr and found_mood:
            name = f"{found_mood[0]}_{found_instr[0]}"
        elif found_instr:
            name = f"{meaningful[0]}_{found_instr[0]}"
        else:
            name = f"{meaningful[0]}_{meaningful[-1]}"
    elif len(meaningful) >= 3:
        name = f"{meaningful[-2]}_{meaningful[-1]}_{meaningful[0]}"
    elif len(meaningful) == 2:
        name = f"{meaningful[0]}_{meaningful[1]}"
    else:
        name = meaningful[0]

    return _sanitize(name)


def _extract_chinese_name(parts: list[str]) -> str:
    """Extract a short evocative name from Chinese music description parts."""
    scene_keywords = [
        # 4-char idioms/phrases (preferred, used directly)
        "大漠孤烟", "金戈铁马", "沙场点兵", "千军万马",
        "英雄末路", "王朝覆灭", "草原帝国", "丝绸之路",
        "江南水乡", "竹林深处", "月下独酌", "雪夜归人",
        "壮士断腕", "帝王登基", "开国盛世", "万马奔腾",
        "气吞山河", "荡气回肠", "排山倒海", "波澜壮阔",
        "气势恢宏", "苍凉悲壮", "气势磅礴", "气象万千",
        # 2-char keywords (extended with context)
        "大漠", "金戈", "沙场", "战场", "英雄", "王朝", "草原", "丝路",
        "江南", "竹林", "月下", "雪夜", "海洋", "森林",
        "废墟", "孤烟", "铁马", "冰河", "关山", "长安", "宫殿", "边塞",
        "王者", "编钟", "盛世", "登基", "悲歌",
    ]

    # Try to find a scene keyword and extract surrounding context
    for part in parts:
        for kw in scene_keywords:
            if kw in part:
                idx = part.index(kw)
                # For 4+ char keywords, use directly
                if len(kw) >= 4:
                    return _sanitize(kw)
                # For shorter keywords, extend forward for context
                end = min(len(part), idx + len(kw) + 4)
                phrase = part[idx:end].strip("，。、的了在从以和与")
                if 2 <= len(phrase) <= 12:
                    return _sanitize(phrase)

    # Fallback: take first 6 chars of the most descriptive part
    longest = max(parts, key=lambda p: len(p))
    name = longest[:6].strip("，。、的了在从以和与一首")
    if len(name) < 2:
        name = longest[:8]
    return _sanitize(name)


def _sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\']', "_", name)
    max_bytes = 200
    while len(name.encode("utf-8")) > max_bytes:
        name = name[:-1]
    return name

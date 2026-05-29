import re


def format_prompt_for_music(raw_prompt: str, user_lyrics: str = "") -> str:
    """Format raw prompt for music generation API with style-specific enhancements."""
    clean = raw_prompt.strip()
    parts = []

    parts.append("迷幻乡村摇滚")

    if "12弦吉他" in clean:
        parts.append("12弦吉他分解和弦")
    if "前奏" in clean:
        intro_match = re.search(r"\[Intro\][^\]]*?(\d+)[秒]", user_lyrics) if user_lyrics else None
        if intro_match:
            parts.append(f"前奏{intro_match.group(1)}秒")
        elif "45" in clean:
            parts.append("前奏45秒")
        elif "30" in clean:
            parts.append("前奏30秒")
    if "B多利亚" in clean or "多利亚" in clean:
        parts.append("B Dorian调式")
    if "4/4" in clean:
        parts.append("4/4与6/8混合拍")
    if "雷鬼" in clean:
        parts.append("雷鬼切分节奏")
    if "双吉他" in clean:
        parts.append("双吉他分声道")
    if "Fender Rhodes" in clean or "电钢琴" in clean:
        parts.append("Fender Rhodes钢琴")
    if "胸腔" in clean or "砂砾" in clean or "沧桑" in clean:
        parts.append("人声：胸腔共鸣、沧桑粗粝")
    if "禁止" in clean:
        forbids = re.findall(r"禁止[：:]([^。，,\n]+)", clean)
        if forbids:
            parts.append(f"禁止：{','.join(forbids)}")
    if "颓废" in clean or "公路" in clean:
        parts.append("氛围：颓废奢华、公路感")

    return "；".join(parts)


def format_prompt_for_lyrics(raw_prompt: str, duration_hint: str = "约5分钟") -> str:
    """Format raw prompt into a lyrics generation prompt."""
    clean = " ".join(raw_prompt.strip().split())

    elements = []
    if "迷幻乡村摇滚" in clean or "Psychedelic country rock" in clean:
        elements.append("迷幻乡村摇滚")
    if "12弦吉他" in clean:
        elements.append("12弦吉他开场")
    if "前奏" in clean:
        m = re.search(r"前奏[^。，,]*?(\d+)[秒]", clean)
        if m:
            elements.append(f"前奏{m.group(1)}秒")
    if "双吉他" in clean:
        elements.append("双吉他对话式尾奏")
    if "胸腔" in clean or "砂砾" in clean or "沧桑" in clean:
        elements.append("人声：胸腔共鸣、沧桑粗粝、禁止说唱")
    elif "禁止" in clean:
        elements.append("人声：醇厚自然，禁止说唱/Rap")
    if "颓废" in clean:
        elements.append("氛围：颓废奢华")
    if "公路" in clean or " highway" in clean.lower():
        elements.append("公路孤独感")

    style = "，".join(elements)
    formatted = (
        f"{clean}。{style}。重要：请生成{duration_hint}时长的长篇完整歌曲，"
        "包含[Intro]、[Verse]、[Pre-Chorus]、[Chorus]、[Bridge]、[Outro]等完整结构。"
        "请确保歌词内容与提供的风格描述相符。"
    )

    if len(formatted) > 1900:
        formatted = formatted[:1900] + "..."
    return formatted

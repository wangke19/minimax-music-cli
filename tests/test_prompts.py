from minimax_music.prompts import format_prompt_for_music, format_prompt_for_lyrics


class TestFormatPromptForMusic:
    def test_base_style_always_present(self):
        result = format_prompt_for_music("anything")
        assert "迷幻乡村摇滚" in result

    def test_12_string_guitar(self):
        result = format_prompt_for_music("12弦吉他 test")
        assert "12弦吉他分解和弦" in result

    def test_dorian_mode(self):
        result = format_prompt_for_music("B多利亚 something")
        assert "B Dorian调式" in result

    def test_reggae(self):
        result = format_prompt_for_music("雷鬼 beat")
        assert "雷鬼切分节奏" in result

    def test_dual_guitar(self):
        result = format_prompt_for_music("双吉他 solo")
        assert "双吉他分声道" in result

    def test_forbidden_keywords(self):
        result = format_prompt_for_music("禁止：rap和说唱 stuff")
        assert "禁止：" in result

    def test_vocal_style(self):
        result = format_prompt_for_music("胸腔 voice")
        assert "人声：胸腔共鸣、沧桑粗粝" in result

    def test_atmosphere(self):
        result = format_prompt_for_music("颓废 mood")
        assert "氛围：颓废奢华、公路感" in result

    def test_joined_with_semicolons(self):
        result = format_prompt_for_music("12弦吉他 test")
        assert "；" in result

    def test_intro_from_lyrics(self):
        lyrics = "[Intro] something 30秒 rest"
        result = format_prompt_for_music("前奏 part", user_lyrics=lyrics)
        assert "前奏30秒" in result


class TestFormatPromptForLyrics:
    def test_includes_duration(self):
        result = format_prompt_for_lyrics("test prompt", duration_hint="约3分钟")
        assert "约3分钟" in result

    def test_includes_structure_tags(self):
        result = format_prompt_for_lyrics("test prompt")
        assert "[Intro]" in result
        assert "[Verse]" in result
        assert "[Chorus]" in result

    def test_truncates_long_prompt(self):
        result = format_prompt_for_lyrics("x" * 3000)
        assert len(result) <= 1903  # 1900 + "..."

    def test_psychedelic_style(self):
        result = format_prompt_for_lyrics("迷幻乡村摇滚 style")
        assert "迷幻乡村摇滚" in result

    def test_highway_keyword(self):
        result = format_prompt_for_lyrics("公路 driving")
        assert "公路孤独感" in result

from minimax_music.naming import generate_name


class TestVocalNaming:
    def test_uses_song_title(self):
        assert generate_name("anything", song_title="星河入梦") == "星河入梦"

    def test_title_spaces_to_underscores(self):
        assert generate_name("x", song_title="hello world") == "hello_world"

    def test_title_sanitized(self):
        assert generate_name("x", song_title='bad<>:file') == "bad___file"

    def test_title_truncated_by_bytes(self):
        long_title = "a" * 200
        result = generate_name("x", song_title=long_title)
        assert len(result.encode("utf-8")) <= 200

    def test_chinese_title_truncated_by_bytes(self):
        # Chinese chars are 3 bytes each, must fit in 200 bytes
        long_title = "测试" * 100  # 200 chars = 600 bytes
        result = generate_name("x", song_title=long_title)
        assert len(result.encode("utf-8")) <= 200

    def test_fallback_timestamp(self):
        result = generate_name("anything", is_instrumental=False)
        assert result.startswith("music_")
        assert len(result) >= len("music_20260528_120000")


class TestInstrumentalNaming:
    def test_strips_chinese_marker(self):
        result = generate_name("纯音乐, 钢琴, 雨夜, 静谧", is_instrumental=True)
        assert "纯音乐" not in result
        assert "钢琴" in result

    def test_three_parts(self):
        result = generate_name("纯音乐, 古筝, 深海, 神秘", is_instrumental=True)
        assert "深海" in result
        assert "神秘" in result
        assert "古筝" in result

    def test_two_parts(self):
        result = generate_name("纯音乐, 钢琴, 宁静", is_instrumental=True)
        assert "钢琴" in result
        assert "宁静" in result

    def test_single_part(self):
        result = generate_name("纯音乐, piano solo", is_instrumental=True)
        assert result == "piano solo"

    def test_complex_prompt_with_instruments(self):
        result = generate_name(
            "纯音乐, epic, orchestral, guzheng, powerful, dramatic",
            is_instrumental=True,
        )
        assert "guzheng" in result

    def test_empty_after_stripping(self):
        result = generate_name("纯音乐,", is_instrumental=True)
        assert "instrumental_" in result

    def test_sanitizes_special_chars(self):
        result = generate_name("纯音乐, test<>:file", is_instrumental=True)
        assert "<" not in result
        assert ">" not in result

from pathlib import Path

from minimax_music.naming import generate_name, resolve_filename_collision


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

    def test_short_prompt_generates_name(self):
        result = generate_name("梦幻流行, 迷离, 夕阳, 气声女声", is_instrumental=False)
        assert "梦幻流行" in result

    def test_single_part_prompt(self):
        result = generate_name("anything", is_instrumental=False)
        assert result == "anything"

    def test_fallback_empty_prompt(self):
        result = generate_name("", is_instrumental=False)
        assert result.startswith("music_")


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


class TestFilenameCollision:
    def test_no_collision_returns_original(self, tmp_path):
        result = resolve_filename_collision("song", tmp_path, ".mp3")
        assert result == "song"

    def test_collision_adds_a_suffix(self, tmp_path):
        (tmp_path / "song.mp3").write_text("fake")
        result = resolve_filename_collision("song", tmp_path, ".mp3")
        assert result == "song_A"

    def test_multiple_collisions_adds_b_c(self, tmp_path):
        (tmp_path / "song.mp3").write_text("fake")
        (tmp_path / "song_A.mp3").write_text("fake")
        (tmp_path / "song_B.mp3").write_text("fake")
        result = resolve_filename_collision("song", tmp_path, ".mp3")
        assert result == "song_C"

    def test_all_a_z_taken_falls_back_to_timestamp(self, tmp_path):
        # Create base file and A-Z files
        (tmp_path / "song.mp3").write_text("fake")
        for i in range(26):
            suffix = chr(ord('A') + i)
            (tmp_path / f"song_{suffix}.mp3").write_text("fake")
        result = resolve_filename_collision("song", tmp_path, ".mp3")
        # Should fall back to timestamp
        assert "song_" in result
        assert "_A" not in result  # Not a simple letter suffix

    def test_custom_extension(self, tmp_path):
        (tmp_path / "song.txt").write_text("fake")
        result = resolve_filename_collision("song", tmp_path, ".txt")
        assert result == "song_A"

    def test_chinese_filename_collision(self, tmp_path):
        (tmp_path / "烟雨江南梦.mp3").write_text("fake")
        result = resolve_filename_collision("烟雨江南梦", tmp_path, ".mp3")
        assert result == "烟雨江南梦_A"

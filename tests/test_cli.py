import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from minimax_music.cli import fill_template, parse_args, parse_config_file, run


class TestParseArgs:
    def test_prompt_only(self):
        args = parse_args(["-p", "Pop music"])
        assert args.prompt == "Pop music"

    def test_all_basic_args(self):
        args = parse_args([
            "-p", "test", "-l", "lyrics", "-n", "song", "-o", "./out"
        ])
        assert args.prompt == "test"
        assert args.lyrics == "lyrics"
        assert args.name == "song"
        assert args.output == "./out"

    def test_use_lyrics_gen_flag(self):
        args = parse_args(["-p", "test", "--use-lyrics-gen"])
        assert args.use_lyrics_gen is True

    def test_instrumental_flag(self):
        args = parse_args(["-p", "test", "--instrumental"])
        assert args.instrumental is True

    def test_default_model(self):
        args = parse_args(["-p", "test"])
        assert args.model == "music-2.6"

    def test_custom_model(self):
        args = parse_args(["-p", "test", "--model", "music-cover"])
        assert args.model == "music-cover"

    def test_audio_settings(self):
        args = parse_args(["-p", "test", "--sample-rate", "32000", "--bitrate", "128000"])
        assert args.sample_rate == 32000
        assert args.bitrate == 128000

    def test_param_file(self):
        args = parse_args(["--param-file", "config.txt"])
        assert args.param_file == "config.txt"

    def test_vars(self):
        args = parse_args(["-p", "test", "--vars", "style=Pop,mood=Happy"])
        assert args.vars == "style=Pop,mood=Happy"


class TestParseConfigFile:
    def test_json_format(self, tmp_path):
        config = {"prompt": "Pop", "lyrics": "verse1", "name": "song"}
        f = tmp_path / "config.json"
        f.write_text(json.dumps(config))
        result = parse_config_file(str(f))
        assert result == config

    def test_key_value_format(self, tmp_path):
        f = tmp_path / "config.txt"
        f.write_text("prompt=Pop\nlyrics=verse1\nname=song\n")
        result = parse_config_file(str(f))
        assert result == {"prompt": "Pop", "lyrics": "verse1", "name": "song"}

    def test_music_template_format(self, tmp_path):
        f = tmp_path / "music.txt"
        f.write_text("[风格]\nPop, happy\n\n[歌词]\n[Intro]\nLa la\n\n[歌名]\nmy_song\n")
        result = parse_config_file(str(f))
        assert result["prompt"] == "Pop, happy"
        assert result["lyrics"] == "[Intro]\nLa la"
        assert result["name"] == "my_song"

    def test_skips_comments(self, tmp_path):
        f = tmp_path / "config.txt"
        f.write_text("# comment\nprompt=test\n# another\n")
        result = parse_config_file(str(f))
        assert result == {"prompt": "test"}

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_config_file("/nonexistent/path.txt")

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{invalid json}")
        with pytest.raises(Exception):
            parse_config_file(str(f))


class TestFillTemplate:
    def test_replaces_braces(self):
        assert fill_template("{style}, {mood}", {"style": "Pop", "mood": "Happy"}) == "Pop, Happy"

    def test_replaces_dollar_sign(self):
        assert fill_template("$style", {"style": "Pop"}) == "Pop"

    def test_mixed_placeholders(self):
        result = fill_template("{a} and $b", {"a": "X", "b": "Y"})
        assert result == "X and Y"

    def test_missing_variable_kept(self):
        assert fill_template("{missing}", {}) == "{missing}"


class TestRun:
    def test_missing_prompt_exits(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            run([])

    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            run(["-p", "test"])

    def test_instrumental_run(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

        mock_result = MagicMock()
        mock_result.audio_path = tmp_path / "test.mp3"
        mock_result.lyrics_path = None
        mock_result.song_title = None
        mock_result.duration_ms = 180000

        mock_lyrics_result = MagicMock()
        mock_lyrics_result.lyrics = ""
        mock_lyrics_result.song_title = ""

        with patch("minimax_music.cli.InstrumentalGenerator") as MockGen:
            MockGen.return_value.generate.return_value = mock_result
            with patch("minimax_music.cli.MusicClient"), \
                 patch("minimax_music.cli.LyricsClient") as MockLC:
                MockLC.return_value.generate.return_value = mock_lyrics_result
                run(["-p", "piano calm", "--instrumental", "-o", str(tmp_path)])

        MockGen.return_value.generate.assert_called_once()

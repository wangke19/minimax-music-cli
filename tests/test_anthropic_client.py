from unittest.mock import MagicMock, patch

import pytest
import requests

from minimax_music.api.anthropic_client import AnthropicClient


@pytest.fixture
def client():
    return AnthropicClient("test-key")


def _mock_response(status_code=200, body=None):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = body or {}
    mock.text = "" if body else "no body"
    return mock


class TestAnthropicClient:
    def test_sets_required_headers(self, client):
        assert client._session.headers["x-api-key"] == "test-key"
        assert client._session.headers["anthropic-version"] == "2023-06-01"
        assert client._session.headers["content-type"] == "application/json"

    def test_generate_text_success(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={
            "content": [{"type": "text", "text": "Hello world"}],
        }))

        text = client.generate_text(system="sys", user="usr")
        assert text == "Hello world"

    def test_generate_text_concatenates_multiple_blocks(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={
            "content": [
                {"type": "text", "text": "Part 1. "},
                {"type": "text", "text": "Part 2."},
            ],
        }))
        text = client.generate_text(system="sys", user="usr")
        assert text == "Part 1. Part 2."

    def test_generate_text_api_error_raises(self, client):
        client._session.post = MagicMock(return_value=_mock_response(
            status_code=500, body={"error": "server error"}
        ))
        client._session.post.return_value.text = "internal error"
        with pytest.raises(Exception, match="Anthropic API error 500"):
            client.generate_text(system="sys", user="usr")

    def test_generate_text_empty_content_raises(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={"content": []}))
        with pytest.raises(Exception, match="empty content"):
            client.generate_text(system="sys", user="usr")

    def test_generate_text_ignores_non_text_blocks(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={
            "content": [
                {"type": "tool_use", "text": "ignored"},
                {"type": "text", "text": "kept"},
            ],
        }))
        text = client.generate_text(system="sys", user="usr")
        assert text == "kept"

    def test_url_construction(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={
            "content": [{"type": "text", "text": "ok"}],
        }))
        client.generate_text(system="sys", user="usr")
        args, _ = client._session.post.call_args
        assert args[0] == "https://api.anthropic.com/v1/messages"

    def test_payload_shape(self, client):
        client._session.post = MagicMock(return_value=_mock_response(body={
            "content": [{"type": "text", "text": "ok"}],
        }))
        client.generate_text(
            system="my-system",
            user="my-user",
            max_tokens=512,
            temperature=0.3,
            model="claude-haiku-4-5",
        )
        _, kwargs = client._session.post.call_args
        payload = kwargs["json"]
        assert payload["system"] == "my-system"
        assert payload["messages"] == [{"role": "user", "content": "my-user"}]
        assert payload["max_tokens"] == 512
        assert payload["temperature"] == 0.3
        assert payload["model"] == "claude-haiku-4-5"

    def test_timeout_raises_when_network_fails(self, client):
        client._session.post = MagicMock(side_effect=requests.exceptions.Timeout())
        with pytest.raises(requests.exceptions.Timeout):
            client.generate_text(system="sys", user="usr")

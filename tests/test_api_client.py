from unittest.mock import MagicMock, patch

import pytest
import requests

from minimax_music.api.client import BaseClient
from minimax_music.config import AuthError, NetworkError, RateLimitError


@pytest.fixture
def client():
    return BaseClient("test-api-key")


class TestBaseClient:
    def test_sets_auth_header(self, client):
        assert client._session.headers["Authorization"] == "Bearer test-api-key"

    def test_sets_content_type(self, client):
        assert client._session.headers["Content-Type"] == "application/json"

    def test_post_success(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"base_resp": {"status_code": 0}, "data": "ok"}
        client._session.post = MagicMock(return_value=mock_resp)

        result = client._post("/test", {"key": "val"})
        assert result == {"base_resp": {"status_code": 0}, "data": "ok"}
        client._session.post.assert_called_once()

    def test_post_timeout_raises_network_error(self, client):
        client._session.post = MagicMock(side_effect=requests.exceptions.Timeout())
        with pytest.raises(NetworkError, match="timed out"):
            client._post("/test", {})

    def test_post_connection_error(self, client):
        client._session.post = MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
        with pytest.raises(NetworkError, match="Connection error"):
            client._post("/test", {})

    def test_auth_error_1004(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "base_resp": {"status_code": 1004, "status_msg": "invalid key"}
        }
        client._session.post = MagicMock(return_value=mock_resp)
        with pytest.raises(AuthError, match="1004"):
            client._post("/test", {})

    def test_auth_error_2049(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "base_resp": {"status_code": 2049, "status_msg": "unauthorized"}
        }
        client._session.post = MagicMock(return_value=mock_resp)
        with pytest.raises(AuthError, match="2049"):
            client._post("/test", {})

    def test_rate_limit_error(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "base_resp": {"status_code": 1, "status_msg": "usage limit exceeded for today"}
        }
        client._session.post = MagicMock(return_value=mock_resp)
        with pytest.raises(RateLimitError, match="usage limit exceeded"):
            client._post("/test", {})

    def test_generic_api_error(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "base_resp": {"status_code": 500, "status_msg": "server error"}
        }
        client._session.post = MagicMock(return_value=mock_resp)
        with pytest.raises(Exception, match="500"):
            client._post("/test", {})

    def test_passes_timeout(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"base_resp": {"status_code": 0}}
        client._session.post = MagicMock(return_value=mock_resp)
        client._post("/test", {}, timeout=120)
        _, kwargs = client._session.post.call_args
        assert kwargs["timeout"] == 120

    def test_url_construction(self, client):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"base_resp": {"status_code": 0}}
        client._session.post = MagicMock(return_value=mock_resp)
        client._post("/music_generation", {})
        args, _ = client._session.post.call_args
        assert args[0] == "https://api.minimaxi.com/v1/music_generation"

import requests

from ..config import API_BASE_URL, AuthError, NetworkError, RateLimitError


class BaseClient:
    def __init__(self, api_key: str, base_url: str = API_BASE_URL):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        })

    def _post(self, endpoint: str, payload: dict, timeout: int = 60) -> dict:
        url = f"{self._base_url}{endpoint}"
        try:
            resp = self._session.post(url, json=payload, timeout=timeout)
            result = resp.json()
        except requests.exceptions.Timeout:
            raise NetworkError(f"Request timed out: {url}")
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {e}")

        self._handle_error(result)
        return result

    @staticmethod
    def _handle_error(response: dict) -> None:
        base = response.get("base_resp", {})
        status_code = base.get("status_code", 0)
        if status_code == 0:
            return

        msg = base.get("status_msg", "Unknown error")

        if status_code in (1004, 2049):
            raise AuthError(f"Authentication failed ({status_code}): {msg}")

        if "usage limit exceeded" in msg.lower():
            raise RateLimitError(msg)

        raise Exception(f"API Error ({status_code}): {msg}")

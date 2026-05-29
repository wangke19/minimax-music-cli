import os

API_BASE_URL = "https://api.minimaxi.com/v1"
MUSIC_ENDPOINT = "/music_generation"
LYRICS_ENDPOINT = "/lyrics_generation"

MODEL_MUSIC_2_6 = "music-2.6"
MODEL_MUSIC_COVER = "music-cover"
MODEL_MUSIC_2_6_FREE = "music-2.6-free"
MODEL_MUSIC_COVER_FREE = "music-cover-free"
ALL_MODELS = [MODEL_MUSIC_2_6, MODEL_MUSIC_COVER, MODEL_MUSIC_2_6_FREE, MODEL_MUSIC_COVER_FREE]

PROMPT_MAX_CHARS = 2000
LYRICS_MAX_CHARS = 3500

AUDIO_SAMPLE_RATES = [16000, 24000, 32000, 44100]
AUDIO_BITRATES = [32000, 64000, 128000, 256000]
AUDIO_FORMATS = ["mp3", "wav", "pcm"]

LYRICS_TAGS = [
    "Intro", "Verse", "Pre Chorus", "Chorus", "Interlude", "Bridge",
    "Outro", "Post Chorus", "Transition", "Break", "Hook", "Build Up", "Inst", "Solo",
]


def get_api_key() -> str:
    key = os.environ.get("MINIMAX_API_KEY", "")
    if not key:
        raise AuthError("MINIMAX_API_KEY environment variable is not set")
    return key


class MiniMaxError(Exception):
    pass


class AuthError(MiniMaxError):
    pass


class RateLimitError(MiniMaxError):
    pass


class NetworkError(MiniMaxError):
    pass


class DownloadError(MiniMaxError):
    pass


# Account tier rate limits for music API
TIER_LIMITS = {
    "free": {"rpm": 3, "conn": 3},
    "paid": {"rpm": 120, "conn": 20},
}


def detect_account_tier(api_key: str) -> str:
    """Detect account tier by probing the text API. Returns 'free', 'paid', or 'unknown'."""
    import requests
    try:
        resp = requests.post(
            f"{API_BASE_URL}/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
            json={"model": "MiniMax-M2.7-highspeed", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
            timeout=10,
        )
        if resp.status_code == 429:
            body = resp.text
            if "Token Plan Starter" in body or "Free" in body:
                return "free"
            return "paid"  # rate limited but not free-tier
        return "unknown"
    except Exception:
        return "unknown"


def check_concurrency_warning(tier: str, concurrency: int, samples: int) -> str | None:
    """Return warning message if concurrency may exceed limits, or None if OK."""
    limits = TIER_LIMITS.get(tier)
    if not limits:
        if concurrency > 20:
            return f"并发数 {concurrency} 超过 API 最大限制 (CONN=20)，部分请求可能失败"
        return None

    max_conn = limits["conn"]
    max_rpm = limits["rpm"]
    tier_label = "免费用户" if tier == "free" else "付费用户"

    if concurrency > max_conn:
        return (
            f"[警告] {tier_label}最大并行数(CONN)为 {max_conn}，当前设置 {concurrency}。\n"
            f"  超出部分会被排队或拒绝，导致音乐生成超时失败。\n"
            f"  建议使用 -c {max_conn}"
        )

    total_tasks = concurrency  # roughly, first batch
    if total_tasks > max_rpm:
        return (
            f"[警告] {tier_label}每分钟请求数(RPM)为 {max_rpm}，当前并发 {concurrency}。\n"
            f"  短时间内可能触发频率限制。"
        )

    return None

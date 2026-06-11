import hashlib
from pathlib import Path


class BatchManager:
    PROGRESS_FILE = ".batch_progress"

    def __init__(self, base_dir: Path | None = None):
        self._base_dir = base_dir or Path(".")

    def _progress_path(self, prompts_file: Path) -> Path:
        """Per-prompts-file progress file to allow resuming across different prompts files."""
        stem = prompts_file.stem.replace(" ", "_")[:30]
        # Use MD5 for stable hash across Python runs (hash() is randomized)
        content_hash = hashlib.md5(prompts_file.read_bytes()).hexdigest()[:4]
        return self._base_dir / f".batch_progress_{stem}_{content_hash}"

    def load(self, prompts_file: Path | None = None) -> set[int]:
        """Load set of completed line numbers (1-based). Falls back to legacy int."""
        if prompts_file is None:
            return set()
        path = self._progress_path(prompts_file)
        if not path.exists():
            return set()
        try:
            return {int(x) for x in path.read_text().strip().split(",") if x.strip()}
        except (ValueError, OSError):
            return set()

    def save(self, line_number: int, prompts_file: Path | None = None) -> None:
        """Add a completed line number."""
        if prompts_file is None:
            return
        path = self._progress_path(prompts_file)
        existing = self.load(prompts_file)
        existing.add(line_number)
        path.write_text(",".join(str(x) for x in sorted(existing)))

    def clear(self, prompts_file: Path | None = None) -> None:
        if prompts_file is None:
            return
        path = self._progress_path(prompts_file)
        if path.exists():
            path.unlink()

    @staticmethod
    def is_rate_limit_error(error_msg: str) -> bool:
        return "usage limit exceeded" in error_msg.lower()

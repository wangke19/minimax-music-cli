from pathlib import Path


class BatchManager:
    PROGRESS_FILE = ".batch_progress"

    def __init__(self, base_dir: Path | None = None):
        self._path = (base_dir or Path(".")) / self.PROGRESS_FILE

    def load(self) -> int:
        if not self._path.exists():
            return 0
        try:
            return int(self._path.read_text().strip())
        except (ValueError, OSError):
            return 0

    def save(self, line_number: int) -> None:
        self._path.write_text(str(line_number))

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()

    @staticmethod
    def is_rate_limit_error(error_msg: str) -> bool:
        return "usage limit exceeded" in error_msg.lower()

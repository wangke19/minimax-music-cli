import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from ..config import RateLimitError
from ..generators.base import BaseGenerator
from .manager import BatchManager


@dataclass
class BatchResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class BatchRunner:
    def __init__(
        self,
        generator: BaseGenerator,
        batch_manager: BatchManager,
        prompts_file: Path,
        output_dir: Path,
        delay_range: tuple[int, int] = (1, 5),
        is_instrumental: bool = False,
        concurrency: int = 1,
    ):
        self._generator = generator
        self._manager = batch_manager
        self._prompts_file = prompts_file
        self._output_dir = output_dir
        self._delay_range = delay_range
        self._is_instrumental = is_instrumental
        self._concurrency = max(1, concurrency)

    def run(self) -> BatchResult:
        lines = self._read_prompts()
        if not lines:
            print("No prompts to process")
            return BatchResult()

        start = self._manager.load(self._prompts_file)
        pending = [(i, line) for i, line in enumerate(lines, start=1) if i not in start]

        if not pending:
            print("All prompts already processed")
            return BatchResult(total=len(lines), success=len(lines))

        if start:
            print(f"Resuming from line(s): {sorted(start)}")

        result = BatchResult(total=len(lines))

        if self._concurrency == 1:
            result = self._run_sequential(pending, result)
        else:
            result = self._run_concurrent(pending, result)

        self._manager.clear(self._prompts_file)
        return result

    def _run_sequential(self, pending: list, result: BatchResult) -> BatchResult:
        for idx, (i, line) in enumerate(pending):
            print(f"\n[{i}/{result.total}] {line[:80]}{'...' if len(line) > 80 else ''}")

            if self._process_line(line, i):
                result.success += 1
            else:
                result.failed += 1

            self._manager.save(i, self._prompts_file)

            if idx < len(pending) - 1:
                delay = random.randint(*self._delay_range)
                print(f"  Waiting {delay}s...")
                time.sleep(delay)

        return result

    def _run_concurrent(self, pending: list, result: BatchResult) -> BatchResult:
        print(f"\nConcurrent mode: {self._concurrency} workers, {len(pending)} tasks")

        lock = Lock()
        completed_count = 0
        rate_limited = False

        def task(i: int, line: str) -> tuple[int, str, bool, str | None]:
            try:
                gen_result = self._generator.generate(
                    prompt=line,
                    output_dir=self._output_dir,
                    is_instrumental=self._is_instrumental,
                    no_format_prompt=True,
                )
                return (i, line, True, gen_result.audio_path.name)
            except RateLimitError as e:
                return (i, line, False, f"RATE_LIMIT:{e}")
            except Exception as e:
                return (i, line, False, str(e))

        with ThreadPoolExecutor(max_workers=self._concurrency) as executor:
            futures = {}
            task_iter = iter(pending)

            # Submit initial batch
            for _ in range(min(self._concurrency, len(pending))):
                i, line = next(task_iter)
                futures[executor.submit(task, i, line)] = i

            for future in as_completed(futures):
                if rate_limited:
                    break

                i, line, ok, msg = future.result()

                with lock:
                    completed_count += 1
                    prefix = f"[{completed_count}/{len(pending)}]"
                    display = line[:60] + ("..." if len(line) > 60 else "")

                if ok:
                    print(f"{prefix} Done: {msg}")
                    with lock:
                        result.success += 1
                    self._manager.save(i, self._prompts_file)
                elif msg and msg.startswith("RATE_LIMIT:"):
                    print(f"{prefix} Rate limited: {msg[12:]}")
                    rate_limited = True
                    with lock:
                        result.failed += 1
                        result.errors.append(msg[12:])
                    self._manager.save(i - 1, self._prompts_file)
                    print("=== Batch paused (rate limit) ===")
                    executor.shutdown(wait=False, cancel_futures=True)
                    sys.exit(0)
                else:
                    print(f"{prefix} Failed [{i}]: {msg}")
                    with lock:
                        result.failed += 1
                        result.errors.append(f"Line {i}: {msg}")

                # Submit next task
                try:
                    ni, nline = next(task_iter)
                    futures[executor.submit(task, ni, nline)] = ni
                except StopIteration:
                    pass

        # Save progress to last completed
        if not rate_limited and pending:
            with lock:
                self._manager.save(pending[-1][0], self._prompts_file)
            self._manager.clear(self._prompts_file)

    def _process_line(self, line: str, line_num: int) -> bool:
        try:
            gen_result = self._generator.generate(
                prompt=line,
                output_dir=self._output_dir,
                is_instrumental=self._is_instrumental,
                no_format_prompt=True,
            )
            print(f"  Done: {gen_result.audio_path.name}")
            return True
        except RateLimitError as e:
            print(f"  Rate limited: {e}")
            self._manager.save(line_num, self._prompts_file)
            print("=== Batch paused (rate limit) ===")
            sys.exit(0)
        except Exception as e:
            print(f"  Failed: {e}")
            return False

    def _read_prompts(self) -> list[str]:
        if not self._prompts_file.exists():
            raise FileNotFoundError(f"Prompts file not found: {self._prompts_file}")
        lines = []
        for line in self._prompts_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                lines.append(stripped)
        return lines

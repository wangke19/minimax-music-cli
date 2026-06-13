#!/usr/bin/env python3
"""Create missing ZIP files for existing copyright reports."""
import zipfile
from pathlib import Path

MP3_DIR = Path(__file__).parent / "mp3"

def main():
    reports = sorted(MP3_DIR.glob("*-版权报告.md"))
    print(f"Found {len(reports)} copyright reports")

    created = 0
    skipped = 0

    for report in reports:
        zip_path = report.with_suffix(".zip")
        if zip_path.exists():
            skipped += 1
            continue

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(report, report.name)
            created += 1
            print(f"  Created: {zip_path.name}")
        except Exception as e:
            print(f"  FAILED: {report.name}: {e}")

    print(f"\n=== Done ===")
    print(f"Created: {created} ZIP files")
    print(f"Skipped (already exist): {skipped}")

if __name__ == "__main__":
    main()

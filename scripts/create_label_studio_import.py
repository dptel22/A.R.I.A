"""Create Label Studio import tasks for local BLR pothole images.

Run via:
  python -m scripts.create_label_studio_import
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SOURCE_ROOT = Path("data") / "demo" / "blr_potholes"
DEFAULT_DOCUMENT_ROOT = Path("data") / "demo"
DEFAULT_OUTPUT = DEFAULT_SOURCE_ROOT / "label_studio_tasks.jsonl"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Label Studio JSONL tasks for BLR pothole images."
    )
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Folder containing manifest.jsonl and the images directory.",
    )
    parser.add_argument(
        "--document-root",
        default=str(DEFAULT_DOCUMENT_ROOT),
        help="Folder configured as LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output JSONL path for Label Studio import.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of tasks to write for a small test import.",
    )
    return parser


def read_manifest(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} line {line_number}") from exc
    return records


def make_task(record: dict[str, Any], document_root: Path) -> dict[str, Any] | None:
    local_image_path = record.get("local_image_path")
    if not isinstance(local_image_path, str) or not local_image_path:
        return None

    image_path = Path(local_image_path)
    if not image_path.is_absolute():
        image_path = Path.cwd() / image_path

    if not image_path.exists():
        return None

    relative_path = image_path.resolve().relative_to(document_root.resolve())
    label_studio_path = relative_path.as_posix()

    return {
        "data": {
            "image": f"/data/local-files/?d={label_studio_path}",
            "issue_number": record.get("issue_number"),
            "issue_url": record.get("issue_url"),
            "uuid": record.get("uuid"),
            "lat": record.get("lat"),
            "long": record.get("long"),
            "created_at": record.get("created_at"),
            "source_image_url": record.get("source_image_url"),
        }
    }


def main() -> None:
    args = build_parser().parse_args()
    source_root = Path(args.source_root)
    document_root = Path(args.document_root)
    output_path = Path(args.output)
    manifest_path = source_root / "manifest.jsonl"

    tasks: list[dict[str, Any]] = []
    for record in read_manifest(manifest_path):
        task = make_task(record, document_root)
        if task is None:
            continue
        tasks.append(task)
        if args.limit is not None and len(tasks) >= args.limit:
            break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for task in tasks:
            handle.write(json.dumps(task, ensure_ascii=True) + "\n")

    print(f"Wrote {len(tasks)} Label Studio tasks to {output_path}")
    print(f"Use LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT={document_root.resolve()}")


if __name__ == "__main__":
    main()

"""Download the A.R.I.A. YOLO weights from the latest GitHub Release."""
# Run via:
#   python -m scripts.download_model
#   python -m scripts.download_model --output models/aria_stage1.pt
#   python -m scripts.download_model --url https://github.com/<owner>/<repo>/releases/latest/download/aria_stage1.pt

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


DEFAULT_MODEL_URL = os.environ.get(
    "ARIA_MODEL_RELEASE_URL",
    "https://github.com/dptel22/A.R.I.A/releases/latest/download/aria_stage1.pt",
)
DEFAULT_OUTPUT = Path(os.environ.get("ARIA_MODEL_PATH", "./models/aria_stage1.pt"))
CHUNK_SIZE = 1024 * 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the A.R.I.A. model weights from the GitHub release asset."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_MODEL_URL,
        help="Release asset URL for the model weights.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Local path where the model file should be written.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser


def download_file(url: str, output_path: Path, force: bool) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not force:
        print(f"Model already exists at {output_path}. Use --force to overwrite.")
        return 0

    try:
        with urlopen(url) as response, output_path.open("wb") as handle:
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
    except HTTPError as exc:
        print(f"Failed to download model: HTTP {exc.code} from {url}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Failed to download model: {exc.reason}", file=sys.stderr)
        return 1

    print(f"Downloaded model to {output_path}")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    return download_file(args.url, Path(args.output), args.force)


if __name__ == "__main__":
    raise SystemExit(main())

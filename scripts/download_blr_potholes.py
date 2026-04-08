"""
One-time BLR potholes dataset downloader for local A.R.I.A. testing.

Usage:
    python -m scripts.download_blr_potholes
    python -m scripts.download_blr_potholes --limit 25
    python -m scripts.download_blr_potholes --out-dir data/demo/blr_potholes --force
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

REPO_OWNER = "warlockdn"
REPO_NAME = "blr-potholes-data"
GITHUB_API_BASE = "https://api.github.com"
DEFAULT_OUT_DIR = Path("data") / "demo" / "blr_potholes"
PER_PAGE = 100
REQUEST_TIMEOUT = (10, 60)
FRONT_MATTER_DELIMITER = "---"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
CONTENT_TYPE_EXTENSION_MAP = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}
EXPECTED_FIELDS = {
    "uuid",
    "lat",
    "long",
    "image",
    "image_thumb",
    "category",
    "created_at",
}
FIELD_ALIASES = {
    "latitude": "lat",
    "longitude": "long",
    "lng": "long",
    "lon": "long",
    "image_thumb_url": "image_thumb",
    "image_thumb": "image_thumb",
    "image_thumbs": "image_thumb",
    "image_url": "image",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download BLR potholes issue images and metadata for local testing."
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory where images and manifest files will be written.",
    )
    parser.add_argument(
        "--state",
        default="all",
        choices=["open", "closed", "all"],
        help="Issue state filter for the GitHub API.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for smoke-testing the downloader.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if a local copy already exists.",
    )
    parser.add_argument(
        "--github-token-env",
        default="GITHUB_TOKEN",
        help="Environment variable name that stores an optional GitHub token.",
    )
    return parser


def build_session(token_env: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "User-Agent": "A.R.I.A-BLR-Potholes-Downloader",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    token = os.environ.get(token_env, "").strip()
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def iter_issues(
    session: requests.Session,
    owner: str,
    repo: str,
    state: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    next_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues"
    params: dict[str, Any] | None = {"state": state, "per_page": PER_PAGE, "page": 1}

    while next_url:
        response = session.get(next_url, params=params, timeout=REQUEST_TIMEOUT)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            if response.status_code == 422:
                raise RuntimeError(
                    "GitHub rejected an issues page request with HTTP 422. "
                    "This commonly happens when pagination walks past the last "
                    "available page or when the API is rate-limiting/spam-protecting "
                    "the client. The downloader now follows GitHub's Link headers, "
                    "so if this still happens, retry with a GITHUB_TOKEN."
                ) from exc
            raise
        payload = response.json()

        if not payload:
            break

        for issue in payload:
            if "pull_request" in issue:
                continue
            issues.append(issue)
            if limit is not None and len(issues) >= limit:
                return issues

        next_url = response.links.get("next", {}).get("url")
        params = None

    return issues


def extract_metadata_block(body: str) -> str:
    text = (body or "").strip()
    if not text:
        raise ValueError("Issue body is empty.")

    lines = text.splitlines()
    if lines and lines[0].strip() == FRONT_MATTER_DELIMITER:
        for idx in range(1, len(lines)):
            if lines[idx].strip() == FRONT_MATTER_DELIMITER:
                return "\n".join(lines[1:idx]).strip()
        raise ValueError("Front matter block is not terminated.")

    metadata_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if metadata_lines:
                break
            continue
        if ":" not in stripped:
            if metadata_lines:
                break
            continue
        metadata_lines.append(stripped)

    if not metadata_lines:
        raise ValueError("No metadata block found in issue body.")

    return "\n".join(metadata_lines)


def parse_metadata_block(block: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"Malformed metadata line: {raw_line!r}")
        key, value = line.split(":", 1)
        normalized_key = normalize_field_name(key)
        if normalized_key in EXPECTED_FIELDS:
            parsed[normalized_key] = value.strip()
    return parsed


def normalize_field_name(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
    return FIELD_ALIASES.get(normalized, normalized)


def parse_issue_form_body(body: str) -> dict[str, Any]:
    """
    Parse GitHub issue-form style markdown bodies.

    Expected shape is usually:
        ### uuid
        value

        ### lat
        value
    """
    parsed: dict[str, Any] = {}
    current_key: str | None = None
    buffer: list[str] = []

    def flush_current() -> None:
        nonlocal current_key, buffer
        if current_key is None:
            return
        value = "\n".join(line for line in buffer if line.strip()).strip()
        parsed[current_key] = value
        current_key = None
        buffer = []

    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("### "):
            flush_current()
            candidate = normalize_field_name(stripped[4:].strip())
            if candidate in EXPECTED_FIELDS:
                current_key = candidate
            else:
                current_key = None
            continue

        if current_key is None:
            continue

        if stripped in {"```", "~~~"}:
            continue

        buffer.append(stripped)

    flush_current()
    return parsed


def parse_inline_key_value_body(body: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        normalized_key = normalize_field_name(key)
        if normalized_key not in EXPECTED_FIELDS:
            continue
        value = value.strip()
        if value:
            parsed[normalized_key] = value
    return parsed


def extract_record_metadata(issue: dict[str, Any]) -> dict[str, Any]:
    body = issue.get("body", "") or ""

    try:
        metadata_block = extract_metadata_block(body)
        metadata = parse_metadata_block(metadata_block)
        if metadata.get("uuid", "").strip():
            return metadata
    except ValueError:
        pass

    metadata = parse_issue_form_body(body)
    if metadata:
        return metadata

    metadata = parse_inline_key_value_body(body)
    if metadata:
        return metadata

    raise ValueError("No supported metadata format found in issue body.")


def normalize_record(issue: dict[str, Any]) -> dict[str, Any]:
    metadata = extract_record_metadata(issue)

    uuid = metadata.get("uuid", "").strip()
    if not uuid:
        raise ValueError("Missing uuid.")

    lat_raw = metadata.get("lat", "").strip()
    long_raw = metadata.get("long", "").strip()
    if not lat_raw or not long_raw:
        raise ValueError("Missing latitude or longitude.")

    try:
        lat = float(lat_raw)
        long_value = float(long_raw)
    except ValueError as exc:
        raise ValueError("Latitude or longitude is not a valid float.") from exc

    image_url = metadata.get("image", "").strip()
    thumb_url = metadata.get("image_thumb", "").strip()
    if not image_url and not thumb_url:
        raise ValueError("Missing both image and image_thumb URLs.")

    category = metadata.get("category", "").strip() or None
    created_at = metadata.get("created_at", "").strip() or issue.get("created_at")

    return {
        "issue_number": issue["number"],
        "issue_url": issue.get("html_url", ""),
        "uuid": uuid,
        "lat": lat,
        "long": long_value,
        "category": category,
        "created_at": created_at,
        "source_image_url": image_url or None,
        "source_thumb_url": thumb_url or None,
    }


def find_existing_file(images_dir: Path, uuid: str) -> Path | None:
    matches = sorted(images_dir.glob(f"{uuid}.*"))
    return matches[0] if matches else None


def extension_from_url(url: str) -> str | None:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        return suffix
    return None


def extension_from_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    mapped = CONTENT_TYPE_EXTENSION_MAP.get(normalized)
    if mapped:
        return mapped
    guessed = mimetypes.guess_extension(normalized)
    if guessed and guessed.lower() in ALLOWED_IMAGE_EXTENSIONS:
        return guessed.lower()
    return None


def safe_error_message(exc: Exception) -> str:
    return re.sub(r"\s+", " ", str(exc)).strip() or exc.__class__.__name__


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def download_image(
    session: requests.Session,
    url: str,
    destination_stem: Path,
) -> tuple[Path, str | None]:
    response = session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type")
    extension = extension_from_content_type(content_type) or extension_from_url(url) or ".bin"
    destination = destination_stem.with_suffix(extension)

    with destination.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                handle.write(chunk)

    return destination, content_type


def process_issue(
    session: requests.Session,
    issue: dict[str, Any],
    images_dir: Path,
    force: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    base_failure = {
        "issue_number": issue.get("number"),
        "issue_url": issue.get("html_url"),
    }

    try:
        record = normalize_record(issue)
    except Exception as exc:
        return None, {
            **base_failure,
            "reason": safe_error_message(exc),
            "stage": "metadata_parse",
        }

    existing_file = find_existing_file(images_dir, record["uuid"])
    if existing_file is not None and not force:
        manifest_row = {
            **record,
            "local_image_path": str(existing_file.as_posix()),
            "download_status": "skipped_existing",
            "content_type": mimetypes.guess_type(existing_file.name)[0],
        }
        return manifest_row, None

    preferred_url = record["source_image_url"] or record["source_thumb_url"]
    fallback_url = (
        record["source_thumb_url"]
        if preferred_url == record["source_image_url"]
        else None
    )

    try:
        downloaded_path, content_type = download_image(
            session,
            preferred_url,
            images_dir / record["uuid"],
        )
    except Exception as primary_exc:
        if fallback_url:
            try:
                downloaded_path, content_type = download_image(
                    session,
                    fallback_url,
                    images_dir / record["uuid"],
                )
                record["source_image_url"] = fallback_url
            except Exception as fallback_exc:
                return None, {
                    **base_failure,
                    "uuid": record["uuid"],
                    "reason": f"primary={safe_error_message(primary_exc)}; fallback={safe_error_message(fallback_exc)}",
                    "stage": "image_download",
                }
        else:
            return None, {
                **base_failure,
                "uuid": record["uuid"],
                "reason": safe_error_message(primary_exc),
                "stage": "image_download",
            }

    manifest_row = {
        **record,
        "local_image_path": str(downloaded_path.as_posix()),
        "download_status": "downloaded",
        "content_type": content_type,
    }
    return manifest_row, None


def main() -> None:
    args = build_parser().parse_args()
    out_dir = Path(args.out_dir)
    images_dir = out_dir / "images"
    manifest_path = out_dir / "manifest.jsonl"
    failures_path = out_dir / "download_failures.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    session = build_session(args.github_token_env)
    issues = iter_issues(session, REPO_OWNER, REPO_NAME, args.state, args.limit)

    manifest_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []

    for issue in issues:
        manifest_row, failure_row = process_issue(session, issue, images_dir, args.force)
        if manifest_row is not None:
            manifest_rows.append(manifest_row)
        if failure_row is not None:
            failure_rows.append(failure_row)

    write_jsonl(manifest_path, manifest_rows)
    write_jsonl(failures_path, failure_rows)

    downloaded = sum(1 for row in manifest_rows if row["download_status"] == "downloaded")
    skipped = sum(1 for row in manifest_rows if row["download_status"] == "skipped_existing")

    print(f"Processed issues: {len(issues)}")
    print(f"Manifest rows: {len(manifest_rows)}")
    print(f"Downloaded images: {downloaded}")
    print(f"Skipped existing images: {skipped}")
    print(f"Failures logged: {len(failure_rows)}")
    print(f"Images directory: {images_dir.as_posix()}")
    print(f"Manifest file: {manifest_path.as_posix()}")
    print(f"Failures file: {failures_path.as_posix()}")


if __name__ == "__main__":
    main()

"""Project-wide Python startup tweaks for local development."""
from __future__ import annotations

import os
from pathlib import Path


# Keep Ultralytics settings inside the repo to avoid blocked AppData writes.
_config_home = Path(__file__).resolve().parent / ".yolo-config"
_config_home.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(_config_home))
